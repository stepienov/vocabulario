package com.vocabulario.app.data

import com.vocabulario.app.data.api.GoogleAuthRequest
import com.vocabulario.app.data.api.LanguageProfileCreate
import com.vocabulario.app.data.api.LoginRequest
import com.vocabulario.app.data.api.RegisterRequest
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.local.TokenStore
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
) {
    suspend fun register(email: String, password: String) {
        val tokens = api.register(RegisterRequest(email, password))
        tokenStore.saveTokens(tokens.access_token, tokens.refresh_token)
    }

    suspend fun login(email: String, password: String) {
        val tokens = api.login(LoginRequest(email, password))
        tokenStore.saveTokens(tokens.access_token, tokens.refresh_token)
    }

    suspend fun googleLogin(idToken: String) {
        val tokens = api.googleAuth(GoogleAuthRequest(idToken))
        tokenStore.saveTokens(tokens.access_token, tokens.refresh_token)
    }

    suspend fun logout() {
        tokenStore.clear()
    }

    suspend fun hasProfile(): Boolean = api.listProfiles().isNotEmpty()

    suspend fun ensureActiveProfile() {
        val profiles = api.listProfiles()
        val active = profiles.firstOrNull { it.is_active } ?: profiles.firstOrNull() ?: return
        tokenStore.saveActiveProfile(active.id)
    }
}
