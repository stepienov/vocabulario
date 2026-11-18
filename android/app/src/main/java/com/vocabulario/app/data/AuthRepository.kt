package com.vocabulario.app.data

import com.vocabulario.app.data.api.GoogleAuthRequest
import com.vocabulario.app.data.api.LoginRequest
import com.vocabulario.app.data.api.LogoutRequest
import com.vocabulario.app.data.api.RegisterRequest
import com.vocabulario.app.data.api.TokenResponse
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.imports.ImportStatePersistence
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.LoginDecision
import com.vocabulario.app.data.session.OwnerSnapshot
import com.vocabulario.app.data.session.REAUTH_REASON_SESSION_MISMATCH
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionInstallException
import com.vocabulario.app.data.session.SessionState
import com.vocabulario.app.data.session.StartupAction
import com.vocabulario.app.data.session.decideStartup
import kotlinx.coroutines.CancellationException
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/** Login na konto inne niż właściciel danych na urządzeniu; zmiana konta wymaga jawnego logout. */
class OtherAccountDataException(val unsentCount: Int) : Exception("other_account_data")

/** Dane bez wiarygodnego właściciela; wymagają świadomego odrzucenia przed loginem. */
class UnclaimedLocalDataException(val unsentCount: Int) : Exception("unclaimed_local_data")

@Singleton
class AuthRepository @Inject constructor(
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val offlineStore: OfflineStore,
    private val importStatePersistence: ImportStatePersistence,
    private val sessionCoordinator: SessionCoordinator,
) {
    suspend fun register(email: String, password: String) {
        installCandidate(api.register(RegisterRequest(email, password)))
    }

    suspend fun login(email: String, password: String) {
        installCandidate(api.login(LoginRequest(email, password)))
    }

    suspend fun googleLogin(idToken: String) {
        installCandidate(api.googleAuth(GoogleAuthRequest(idToken)))
    }

    /**
     * Odpowiedź loginu jest kandydatem: dopiero po porównaniu `user_id` z właścicielem danych
     * zostaje zapisana. Błąd lub odmowa zostawia poprzednie dane nietknięte (T-002 §4).
     */
    private suspend fun installCandidate(tokens: TokenResponse) {
        val candidateUserId = tokens.user_id?.takeIf { it.isNotBlank() }
            ?: throw SessionInstallException("missing user_id")
        val transitionId = UUID.randomUUID().toString()
        when (val decision = offlineStore.beginInstall(candidateUserId, transitionId)) {
            is LoginDecision.OtherAccount -> {
                revokeCandidate(tokens)
                throw OtherAccountDataException(decision.unsentCount)
            }
            is LoginDecision.LegacyQuarantine -> {
                revokeCandidate(tokens)
                throw UnclaimedLocalDataException(decision.unsentCount)
            }
            LoginDecision.Claim -> {
                tokenStore.clear()
                importStatePersistence.saveJobId(null)
            }
            LoginDecision.SameOwner -> Unit
        }
        sessionCoordinator.install(tokens)
        offlineStore.completeInstall(transitionId)
    }

    // TODO(E-001/F-003/T-002 §5): trwałe zlecenie odwołania zamiast jednej próby.
    private suspend fun revokeCandidate(tokens: TokenResponse) {
        try {
            api.logout(LogoutRequest(tokens.refresh_token))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Kandydat nie został zapisany; awaria odwołania nie zmienia decyzji loginu.
        }
    }

    /**
     * Zamiar wylogowania trafia do Room przed usunięciem sesji, więc restart dokończy
     * cleanup zamiast wskrzesić dane poprzedniego konta.
     */
    suspend fun logout() {
        val transitionId = UUID.randomUUID().toString()
        offlineStore.beginLogout(transitionId)
        try {
            sessionCoordinator.signOutLocally()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            offlineStore.abortLogout(transitionId)
            throw e
        }
        finishLogoutLocally()
    }

    /** Świadome odrzucenie danych, których nie można przypisać do konta (stara instalacja). */
    suspend fun discardUnclaimedLocalData(): Boolean {
        val discarded = offlineStore.discardUnclaimedData()
        if (discarded) {
            tokenStore.clear()
            importStatePersistence.saveJobId(null)
        }
        return discarded
    }

    suspend fun ownerSnapshot(): OwnerSnapshot = offlineStore.ownerSnapshot()

    /** Ponowienie odczytu nieczytelnej sesji; true, gdy sesja jest znów aktywna i zgodna z danymi. */
    suspend fun retrySessionRecovery(): Boolean {
        if (sessionCoordinator.retryLoad() !is SessionState.Active) return false
        reconcileOwnerOnStart()
        return sessionCoordinator.state.value is SessionState.Active
    }

    /** Uzgodnienie sesji z właścicielem danych po starcie procesu (przed wyborem ekranu). */
    suspend fun reconcileOwnerOnStart() {
        val state = sessionCoordinator.awaitLoaded()
        val snapshot = offlineStore.ownerSnapshot()
        when (val action = decideStartup(snapshot, state)) {
            StartupAction.None -> Unit
            StartupAction.CompleteInstall ->
                snapshot.transitionId?.let { offlineStore.completeInstall(it) }
            StartupAction.CompleteLogout -> {
                if (state !is SessionState.SignedOut) sessionCoordinator.signOutLocally()
                finishLogoutLocally()
            }
            is StartupAction.ClaimEmpty ->
                if (!offlineStore.claimEmpty(action.ownerUserId)) {
                    sessionCoordinator.requireReauth(REAUTH_REASON_SESSION_MISMATCH)
                }
            is StartupAction.RequireReauth -> sessionCoordinator.requireReauth(action.reason)
        }
    }

    private suspend fun finishLogoutLocally() {
        offlineStore.completeLogout()
        tokenStore.clear()
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
