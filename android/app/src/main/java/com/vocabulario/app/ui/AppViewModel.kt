package com.vocabulario.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.sync.SyncScheduler
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
) : ViewModel() {

    val isLoggedIn: StateFlow<Boolean> = tokenStore.accessToken
        .map { !it.isNullOrBlank() }
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    private val _startRoute = MutableStateFlow(AppStartRoute.LOADING)
    val startRoute: StateFlow<AppStartRoute> = _startRoute.asStateFlow()

    fun bootstrap() {
        viewModelScope.launch {
            // DataStore — krótko; UI nie może wisieć na sieci.
            withTimeoutOrNull(1_500) { tokenStore.awaitReady() }

            val token = tokenStore.peekAccessToken()
            if (token.isNullOrBlank()) {
                _startRoute.value = AppStartRoute.AUTH
                return@launch
            }

            // Od razu pokaż Home — profil doprecyzujemy w tle.
            _startRoute.value = AppStartRoute.HOME

            val result = withTimeoutOrNull(5_000) {
                runCatching { authRepository.hasProfile() }
            }

            when {
                result == null -> syncInBackground()
                result.isFailure -> {
                    val err = result.exceptionOrNull()
                    val unauthorized = err is HttpException && err.code() == 401
                    if (unauthorized || tokenStore.peekAccessToken().isNullOrBlank()) {
                        runCatching { authRepository.logout() }
                        _startRoute.value = AppStartRoute.AUTH
                    } else {
                        syncInBackground()
                    }
                }
                result.getOrNull() == true -> syncInBackground()
                else -> _startRoute.value = AppStartRoute.ONBOARDING
            }
        }
    }

    private fun syncInBackground() {
        viewModelScope.launch {
            runCatching { authRepository.ensureActiveProfile() }
            runCatching { learningRepository.syncPendingReviews() }
            runCatching { learningRepository.syncThemeFromSettings() }
            syncScheduler.schedulePeriodic()
            syncScheduler.requestNow()
        }
    }

    fun onAuthenticated(needsOnboarding: Boolean) {
        _startRoute.value = if (needsOnboarding) AppStartRoute.ONBOARDING else AppStartRoute.HOME
        if (!needsOnboarding) syncInBackground()
    }

    fun onOnboardingComplete() {
        _startRoute.value = AppStartRoute.HOME
    }

    fun onLogout() {
        _startRoute.value = AppStartRoute.AUTH
    }
}
