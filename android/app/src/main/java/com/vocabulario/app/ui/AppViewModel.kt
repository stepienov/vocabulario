package com.vocabulario.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.sync.SyncScheduler
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import retrofit2.HttpException
import javax.inject.Inject

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
    private val syncScheduler: SyncScheduler,
    private val blockingBusy: BlockingBusy,
    private val strings: UiStrings,
) : ViewModel() {

    val isLoggedIn: StateFlow<Boolean> = tokenStore.accessToken
        .map { !it.isNullOrBlank() }
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    private val _startRoute = MutableStateFlow(AppStartRoute.LOADING)
    val startRoute: StateFlow<AppStartRoute> = _startRoute.asStateFlow()

    private val _restoreSettings = MutableStateFlow(false)
    val restoreSettings: StateFlow<Boolean> = _restoreSettings.asStateFlow()

    fun onSettingsRestored() {
        _restoreSettings.value = false
    }

    fun bootstrap() {
        viewModelScope.launch {
            withTimeoutOrNull(1_500) { tokenStore.awaitReady() }

            val token = tokenStore.peekAccessToken()
            if (token.isNullOrBlank()) {
                _startRoute.value = AppStartRoute.AUTH
                return@launch
            }

            if (learningRepository.hasCachedProfile()) {
                runCatching { learningRepository.applyAppLocaleFromActiveProfile() }
                runCatching { learningRepository.syncThemeFromSettings() }
                _restoreSettings.value = tokenStore.consumeReopenSettings()
                _startRoute.value = AppStartRoute.HOME
                syncInBackground()
                return@launch
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
                    val err = result.exceptionOrNull()
                    val unauthorized = err is HttpException && err.code() == 401
                    if (unauthorized || tokenStore.peekAccessToken().isNullOrBlank()) {
                        runCatching { authRepository.logout() }
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
