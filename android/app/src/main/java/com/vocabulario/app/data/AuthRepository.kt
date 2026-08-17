package com.vocabulario.app.data

import com.vocabulario.app.data.api.GoogleAuthRequest
import com.vocabulario.app.data.api.LoginRequest
import com.vocabulario.app.data.api.RegisterRequest
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val offlineStore: OfflineStore,
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

    suspend fun hasProfile(): Boolean {
        if (offlineStore.cachedActiveProfile() != null) return true
        if (offlineStore.cachedProfiles().isNotEmpty()) return true
        return runCatching { api.listProfiles() }
            .onSuccess { offlineStore.cacheProfiles(it) }
            .getOrElse { emptyList() }
            .isNotEmpty()
    }

    suspend fun ensureActiveProfile() {
        val storedId = tokenStore.activeProfileId.value
            ?: offlineStore.cachedActiveProfile()?.id
        val profiles = runCatching { api.listProfiles() }.getOrNull()
        if (profiles != null) {
            offlineStore.cacheProfiles(profiles)
            val chosen = resolveActiveProfile(storedId, profiles) ?: return
            tokenStore.saveActiveProfile(chosen.id)
            if (tokenStore.peekAppLang().isBlank()) {
                tokenStore.saveAppLang(chosen.app_lang)
            }
            offlineStore.cacheProfile(chosen)
            return
        }
        offlineStore.cachedActiveProfile()?.let {
            tokenStore.saveActiveProfile(it.id)
            if (tokenStore.peekAppLang().isBlank()) {
                tokenStore.saveAppLang(it.app_lang)
            }
        }
    }
}
