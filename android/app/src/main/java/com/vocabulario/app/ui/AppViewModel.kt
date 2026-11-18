package com.vocabulario.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
import com.vocabulario.app.data.session.sessionLost
import com.vocabulario.app.data.sync.SyncScheduler
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import javax.inject.Inject

/** Po tym czasie start pokazuje stan i ponowienie zamiast samego spinnera (T-002 §7: 10 s). */
private const val LOADING_SLOW_MS = 10_000L

enum class AppStartRoute {
    LOADING,
    AUTH,
    ONBOARDING,
    HOME,
}

@HiltViewModel
class AppViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val learningRepository: LearningRepository,
    private val tokenStore: TokenStore,
    private val sessionCoordinator: SessionCoordinator,
    private val syncScheduler: SyncScheduler,
    private val blockingBusy: BlockingBusy,
    private val strings: UiStrings,
) : ViewModel() {

    private val _startRoute = MutableStateFlow(AppStartRoute.LOADING)
    val startRoute: StateFlow<AppStartRoute> = _startRoute.asStateFlow()

    private val _restoreSettings = MutableStateFlow(false)
    val restoreSettings: StateFlow<Boolean> = _restoreSettings.asStateFlow()

    /** Start trwa dłużej niż zwykle: ekran ponowienia zamiast samego spinnera (bez domyślnego AUTH/HOME). */
    private val _loadingSlow = MutableStateFlow(false)
    val loadingSlow: StateFlow<Boolean> = _loadingSlow.asStateFlow()

    private var bootstrapJob: Job? = null

    init {
        // Utrata sesji w trakcie pracy prowadzi na logowanie; dane lokalne zostają.
        viewModelScope.launch {
            combine(_startRoute, sessionCoordinator.state) { route, state -> route to state }
                .collect { (route, state) ->
                    if ((route == AppStartRoute.HOME || route == AppStartRoute.ONBOARDING) && sessionLost(state)) {
                        _startRoute.value = AppStartRoute.AUTH
                    }
                }
        }
    }

    fun onSettingsRestored() {
        _restoreSettings.value = false
    }

    fun retryBootstrap() {
        bootstrapJob?.cancel()
        bootstrapJob = null
        _startRoute.value = AppStartRoute.LOADING
        bootstrap()
    }

    fun bootstrap() {
        if (bootstrapJob?.isActive == true) return
        _loadingSlow.value = false
        val job = viewModelScope.launch { runBootstrap() }
        bootstrapJob = job
        viewModelScope.launch {
            delay(LOADING_SLOW_MS)
            if (job.isActive && _startRoute.value == AppStartRoute.LOADING) _loadingSlow.value = true
        }
    }

    private suspend fun runBootstrap() {
        withTimeoutOrNull(1_500) { tokenStore.awaitReady() }

        // Błąd uzgodnienia nie wylogowuje; sesja niepasująca do danych przechodzi w reauth.
        try {
            authRepository.reconcileOwnerOnStart()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
        }

        if (sessionCoordinator.awaitLoaded() !is SessionState.Active) {
            _startRoute.value = AppStartRoute.AUTH
            return
        }

        if (learningRepository.hasCachedProfile()) {
            runCatching { learningRepository.applyAppLocaleFromActiveProfile() }
            runCatching { learningRepository.syncThemeFromSettings() }
            _restoreSettings.value = tokenStore.consumeReopenSettings()
            _startRoute.value = AppStartRoute.HOME
            syncInBackground()
            return
        }

        val result = withTimeoutOrNull(8_000) {
            runCatching {
                authRepository.ensureActiveProfile()
                learningRepository.applyAppLocaleFromActiveProfile()
                learningRepository.syncThemeFromSettings()
                authRepository.hasProfile()
            }
        }

        when {
            result == null -> {
                _startRoute.value = AppStartRoute.HOME
                syncInBackground()
            }
            result.isFailure -> {
                // Błąd sieci/serwera nie jest wylogowaniem; o końcu sesji decyduje koordynator.
                if (sessionCoordinator.state.value !is SessionState.Active) {
                    _startRoute.value = AppStartRoute.AUTH
                } else {
                    _startRoute.value = AppStartRoute.HOME
                    syncInBackground()
                }
            }
            result.getOrNull() == false -> _startRoute.value = AppStartRoute.ONBOARDING
            else -> {
                _startRoute.value = AppStartRoute.HOME
                syncInBackground()
            }
        }
    }

    private fun syncInBackground() {
        viewModelScope.launch {
            runCatching { authRepository.ensureActiveProfile() }
            syncScheduler.schedulePeriodic()
            syncScheduler.requestNow()
        }
    }

    fun onAuthenticated(needsOnboarding: Boolean) {
        viewModelScope.launch {
            completeAuthenticated(needsOnboarding)
        }
    }

    suspend fun completeAuthenticated(needsOnboarding: Boolean) {
        if (needsOnboarding) {
            _startRoute.value = AppStartRoute.ONBOARDING
            return
        }
        blockingBusy.run(strings.get(R.string.syncing_with_server)) {
            runCatching {
                authRepository.ensureActiveProfile()
                learningRepository.applyAppLocaleFromActiveProfile()
                learningRepository.syncThemeFromSettings()
            }
            runCatching { learningRepository.syncNow(awaitLock = true) }
            _startRoute.value = AppStartRoute.HOME
        }
        syncScheduler.schedulePeriodic()
    }

    fun onOnboardingComplete() {
        viewModelScope.launch {
            runCatching { learningRepository.applyAppLocaleFromActiveProfile() }
            _startRoute.value = AppStartRoute.HOME
            syncInBackground()
        }
    }

    fun onLogout() {
        _startRoute.value = AppStartRoute.AUTH
    }
}
