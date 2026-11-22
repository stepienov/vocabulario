package com.vocabulario.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.data.AccountRepository
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.EmailVerificationGate
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.LegalGate
import com.vocabulario.app.data.UpdateGate
import com.vocabulario.app.data.deletion.AccountDeletionRepository
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
import com.vocabulario.app.data.session.sessionLost
import com.vocabulario.app.data.sync.ProfileResolution
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

private data class RouteInputs(
    val route: AppStartRoute,
    val state: SessionState,
    val required: Boolean,
    val legalRequired: Boolean,
    val deletionPending: Boolean,
)
enum class AppStartRoute {
    LOADING,
    AUTH,
    /** Bramka F-004: konto bez potwierdzonego adresu; nauka/import/sync zablokowane, dane zostają. */
    VERIFY_EMAIL,
    /** Bramka F-007/T-003: aktualne warunki czekają na akceptację; dane lokalne zostają. */
    LEGAL,
    /** Konto czeka na usunięcie (F-006/T-002): biblioteka ukryta, sesji nie ma, dane lokalne zostają. */
    DELETION_PENDING,
    ONBOARDING,
    HOME,
}

@HiltViewModel
class AppViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val accountRepository: AccountRepository,
    private val verificationGate: EmailVerificationGate,
    private val legalGate: LegalGate,
    private val updateGate: UpdateGate,
    private val deletionRepository: AccountDeletionRepository,
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
    private var resumeJob: Job? = null

    /** 426: ta wersja aplikacji nie jest już obsługiwana; ekran blokuje UI, dane i sesja zostają. */
    val updateRequired: StateFlow<Boolean> = updateGate.required

    fun recheckUpdate() = updateGate.clear()

    init {
        // Utrata sesji w trakcie pracy prowadzi na logowanie; dane lokalne zostają.
        // Wymóg potwierdzenia adresu zmienia uprawnienie (ekran weryfikacji), nie właściciela.
        viewModelScope.launch {
            combine(
                _startRoute,
                sessionCoordinator.state,
                verificationGate.required,
                legalGate.required,
                deletionRepository.receipt,
            ) { route, state, required, legalRequired, receipt ->
                RouteInputs(route, state, required, legalRequired, receipt?.deletion != null)
            }.collect { (route, state, required, legalRequired, deletionPending) ->
                val signedInRoute = route == AppStartRoute.HOME ||
                    route == AppStartRoute.ONBOARDING ||
                    route == AppStartRoute.VERIFY_EMAIL ||
                    route == AppStartRoute.LEGAL
                when {
                    deletionPending && route != AppStartRoute.LOADING && route != AppStartRoute.DELETION_PENDING ->
                        _startRoute.value = AppStartRoute.DELETION_PENDING
                    !deletionPending && route == AppStartRoute.DELETION_PENDING ->
                        _startRoute.value = AppStartRoute.AUTH
                    signedInRoute && sessionLost(state) -> _startRoute.value = AppStartRoute.AUTH
                    required && (route == AppStartRoute.HOME || route == AppStartRoute.ONBOARDING ||
                        route == AppStartRoute.LEGAL) ->
                        _startRoute.value = AppStartRoute.VERIFY_EMAIL
                    legalRequired && !required && (route == AppStartRoute.HOME || route == AppStartRoute.ONBOARDING) ->
                        _startRoute.value = AppStartRoute.LEGAL
                    !required && route == AppStartRoute.VERIFY_EMAIL && state is SessionState.Active -> {
                        if (legalRequired) {
                            _startRoute.value = AppStartRoute.LEGAL
                        } else {
                            resumeAfterGate()
                        }
                    }
                    !legalRequired && route == AppStartRoute.LEGAL && state is SessionState.Active ->
                        resumeAfterGate()
                }
            }
        }
    }

    /** Bramka zdjęta (adres potwierdzony lub warunki przyjęte): ta sama ścieżka co po loginie. */
    private fun resumeAfterGate() {
        if (resumeJob?.isActive == true) return
        resumeJob = viewModelScope.launch {
            val resolution = try {
                authRepository.ensureActiveProfile()
                runCatching { learningRepository.applyAppLocaleFromActiveProfile() }
                runCatching { learningRepository.syncThemeFromSettings() }
                authRepository.resolveProfiles()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                null
            }
            if (_startRoute.value != AppStartRoute.VERIFY_EMAIL && _startRoute.value != AppStartRoute.LEGAL) {
                return@launch
            }
            when (val route = routeFor(resolution)) {
                null -> retryBootstrap()
                AppStartRoute.HOME -> {
                    _startRoute.value = AppStartRoute.HOME
                    syncInBackground()
                }
                else -> _startRoute.value = route
            }
        }
    }

    /** Trasa po rozpoznaniu profili; null = brak pewności, zostajemy na LOADING z ponowieniem. */
    private fun routeFor(resolution: ProfileResolution?): AppStartRoute? = when (resolution) {
        is ProfileResolution.Found -> AppStartRoute.HOME
        ProfileResolution.ConfirmedEmpty -> AppStartRoute.ONBOARDING
        is ProfileResolution.AuthRequired, ProfileResolution.Superseded -> AppStartRoute.AUTH
        ProfileResolution.VerificationRequired -> AppStartRoute.VERIFY_EMAIL
        ProfileResolution.LegalAcceptanceRequired -> AppStartRoute.LEGAL
        is ProfileResolution.Unavailable, null -> null
    }

    private suspend fun refreshAccountQuietly() {
        try {
            accountRepository.refreshAccount()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            // Offline/5xx: zostaje ostatni znany stan weryfikacji.
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

        // Wniosek o usunięcie ma pierwszeństwo przed sesją: konta nie wolno używać, nawet offline.
        deletionRepository.load()?.let { receipt ->
            if (receipt.deletion == null) runCatching { deletionRepository.refreshStatus() }
            if (deletionRepository.receipt.value?.deletion != null) {
                _startRoute.value = AppStartRoute.DELETION_PENDING
                return
            }
        }

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

        // Ostatni znany stan: bez potwierdzenia nie ma pełnego dostępu także offline.
        if (verificationGate.isRequired()) {
            _startRoute.value = AppStartRoute.VERIFY_EMAIL
            refreshAccountQuietly()
            return
        }
        if (legalGate.isRequired()) {
            _startRoute.value = AppStartRoute.LEGAL
            refreshAccountQuietly()
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

        val resolution = withTimeoutOrNull(8_000) {
            try {
                authRepository.ensureActiveProfile()
                learningRepository.applyAppLocaleFromActiveProfile()
                learningRepository.syncThemeFromSettings()
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // Locale i motyw są kosmetyką; o trasie decyduje wyłącznie rozpoznanie profili.
            }
            authRepository.resolveProfiles()
        }

        when (val route = routeFor(resolution)) {
            null -> {
                // Bez cache i bez potwierdzenia z serwera nie zgadujemy ani HOME, ani onboardingu.
                if (sessionCoordinator.state.value !is SessionState.Active) {
                    _startRoute.value = AppStartRoute.AUTH
                } else {
                    _loadingSlow.value = true
                }
            }
            AppStartRoute.HOME -> {
                _startRoute.value = AppStartRoute.HOME
                syncInBackground()
            }
            else -> _startRoute.value = route
        }
    }

    private fun syncInBackground() {
        viewModelScope.launch {
            refreshAccountQuietly()
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
        refreshAccountQuietly()
        if (verificationGate.isRequired()) {
            _startRoute.value = AppStartRoute.VERIFY_EMAIL
            return
        }
        if (legalGate.isRequired()) {
            _startRoute.value = AppStartRoute.LEGAL
            return
        }
        if (needsOnboarding) {
            _startRoute.value = AppStartRoute.ONBOARDING
            return
        }
        // Logowanie nie potwierdziło profilu (serwer niedostępny): decyduje start, nie zgadywanie.
        if (!learningRepository.hasCachedProfile()) {
            retryBootstrap()
            return
        }
        blockingBusy.run(strings.get(R.string.syncing_with_server)) {
            runCatching {
                authRepository.ensureActiveProfile()
                learningRepository.applyAppLocaleFromActiveProfile()
                learningRepository.syncThemeFromSettings()
            }
            learningRepository.syncNow(awaitLock = true)
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
