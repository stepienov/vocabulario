package com.vocabulario.app.data

import com.vocabulario.app.data.api.GoogleAuthRequest
import com.vocabulario.app.data.api.LoginRequest
import com.vocabulario.app.data.api.RegisterRequest
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.imports.ImportStatePersistence
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.SessionCoordinator
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val offlineStore: OfflineStore,
    private val importStatePersistence: ImportStatePersistence,
    private val sessionCoordinator: SessionCoordinator,
) {
    suspend fun register(email: String, password: String) {
        beginNewSession()
        val tokens = api.register(RegisterRequest(email, password))
        sessionCoordinator.install(tokens)
    }

    suspend fun login(email: String, password: String) {
        beginNewSession()
        val tokens = api.login(LoginRequest(email, password))
        sessionCoordinator.install(tokens)
    }

    suspend fun googleLogin(idToken: String) {
        beginNewSession()
        val tokens = api.googleAuth(GoogleAuthRequest(idToken))
        sessionCoordinator.install(tokens)
    }

    suspend fun logout() {
        beginNewSession()
    }

    /** Najpierw trwałe usunięcie sesji; jeśli zawiedzie, dane lokalne zostają nietknięte. */
    private suspend fun beginNewSession() {
        sessionCoordinator.signOutLocally()
        tokenStore.clear()
        offlineStore.clearAll()
        importStatePersistence.saveJobId(null)
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
        val localActive = offlineStore.cachedActiveProfile()
        val storedId = tokenStore.activeProfileId.value ?: localActive?.id
        val profiles = runCatching { api.listProfiles() }.getOrNull()
        if (profiles != null) {
            val merged = mergeRemoteProfiles(profiles, localActive, storedId)
            offlineStore.cacheProfiles(merged)
            val chosen = merged.firstOrNull { it.is_active } ?: return
            tokenStore.saveActiveProfile(chosen.id)
            tokenStore.saveAppLang(chosen.app_lang)
            offlineStore.cacheProfile(chosen.copy(is_active = true))
            return
        }
        localActive?.let {
            tokenStore.saveActiveProfile(it.id)
            tokenStore.saveAppLang(it.app_lang)
        }
    }
}
