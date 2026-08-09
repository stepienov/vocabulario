package com.vocabulario.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.R
import com.vocabulario.app.auth.GoogleAuthHelper
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.userMessage
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.i18n.UiStrings
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val learningRepository: LearningRepository,
    private val tokenStore: TokenStore,
    private val googleAuthHelper: GoogleAuthHelper,
    private val strings: UiStrings,
) : ViewModel() {

    val isLoggedIn: StateFlow<Boolean> = tokenStore.accessToken
        .map { !it.isNullOrBlank() }
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    fun clearError() {
        _errorMessage.value = null
    }

    private fun validate(email: String, password: String, isRegister: Boolean): String? {
        val trimmedEmail = email.trim()
        if (trimmedEmail.isBlank()) return strings.get(R.string.err_email_required)
        if (!trimmedEmail.contains("@")) return strings.get(R.string.err_email_invalid)
        if (password.isBlank()) return strings.get(R.string.err_password_required)
        if (isRegister && password.length < 8) return strings.get(R.string.err_password_short)
        return null
    }

    fun login(email: String, password: String, onSuccess: (needsOnboarding: Boolean) -> Unit) {
        validate(email, password, isRegister = false)?.let {
            _errorMessage.value = it
            return
        }
        viewModelScope.launch {
            _errorMessage.value = null
            runCatching {
                authRepository.login(email.trim(), password)
                !authRepository.hasProfile()
            }.onSuccess { needsOnboarding ->
                if (!needsOnboarding) {
                    authRepository.ensureActiveProfile()
                    learningRepository.applyAppLocaleFromActiveProfile()
                }
                learningRepository.syncThemeFromSettings()
                onSuccess(needsOnboarding)
            }.onFailure {
                _errorMessage.value = it.userMessage(strings.get(R.string.err_login))
            }
        }
    }

    fun register(email: String, password: String, onSuccess: () -> Unit) {
        validate(email, password, isRegister = true)?.let {
            _errorMessage.value = it
            return
        }
        viewModelScope.launch {
            _errorMessage.value = null
            runCatching {
                authRepository.register(email.trim(), password)
            }.onSuccess { onSuccess() }
                .onFailure {
                    _errorMessage.value = it.userMessage(strings.get(R.string.err_register))
                }
        }
    }

    fun googleSignIn(activityContext: android.content.Context, onSuccess: (needsOnboarding: Boolean) -> Unit) {
        viewModelScope.launch {
            _errorMessage.value = null
            runCatching {
                val idToken = googleAuthHelper.signIn(activityContext)
                authRepository.googleLogin(idToken)
                !authRepository.hasProfile()
            }.onSuccess { needsOnboarding ->
                if (!needsOnboarding) {
                    authRepository.ensureActiveProfile()
                    learningRepository.applyAppLocaleFromActiveProfile()
                }
                learningRepository.syncThemeFromSettings()
                onSuccess(needsOnboarding)
            }.onFailure {
                _errorMessage.value = it.userMessage(strings.get(R.string.err_google_login))
            }
        }
    }

    fun logout(onDone: () -> Unit) {
        viewModelScope.launch {
            authRepository.logout()
            onDone()
        }
    }
}
