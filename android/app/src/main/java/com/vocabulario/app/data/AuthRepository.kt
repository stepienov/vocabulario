package com.vocabulario.app.data

import com.vocabulario.app.auth.GoogleIdTokenProvider
import com.vocabulario.app.data.api.GoogleAuthRequest
import com.vocabulario.app.data.api.LoginRequest
import com.vocabulario.app.data.api.LogoutRequest
import com.vocabulario.app.data.api.RegisterRequest
import com.vocabulario.app.data.api.TokenResponse
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.imports.ImportStatePersistence
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.AccountSignOutCleanup
import com.vocabulario.app.data.session.LoginDecision
import com.vocabulario.app.data.session.LogoutConsent
import com.vocabulario.app.data.session.OwnerSnapshot
import com.vocabulario.app.data.session.REAUTH_REASON_SESSION_MISMATCH
import com.vocabulario.app.data.session.RevocationMaterial
import com.vocabulario.app.data.session.RevocationQueueFullException
import com.vocabulario.app.data.session.RevocationRequest
import com.vocabulario.app.data.session.RevocationReservation
import com.vocabulario.app.data.session.RevocationScheduler
import com.vocabulario.app.data.session.RevocationStore
import com.vocabulario.app.data.session.RevocationSummary
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionInstallException
import com.vocabulario.app.data.session.SessionState
import com.vocabulario.app.data.session.StartupAction
import com.vocabulario.app.data.session.SupersededException
import com.vocabulario.app.data.session.decideStartup
import com.vocabulario.app.data.sync.ProfileResolution
import com.vocabulario.app.data.sync.resolveProfileFailure
import com.vocabulario.app.data.sync.toSyncFailure
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
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
    private val revocationStore: RevocationStore,
    private val revocationScheduler: RevocationScheduler,
    private val signOutCleanup: AccountSignOutCleanup,
) {
    suspend fun register(email: String, password: String) = withCandidateSlot { slot ->
        installCandidate(api.register(RegisterRequest(email, password, tokenStore.mailLocale())), slot)
    }

    suspend fun login(email: String, password: String) = withCandidateSlot { slot ->
        installCandidate(api.login(LoginRequest(email, password)), slot)
    }

    /** Challenge i wybór konta poprzedzają rezerwację slotu; anulowanie selektora kończy bez żądania. */
    suspend fun googleLogin(provider: GoogleIdTokenProvider) {
        val challenge = api.googleChallenge()
        val idToken = provider.idToken(challenge.nonce)
        withCandidateSlot { slot ->
            installCandidate(
                api.googleAuth(GoogleAuthRequest(challenge.challenge_id, idToken, tokenStore.mailLocale())),
                slot,
            )
        }
    }

    /** Miejsce na ewentualne odwołanie kandydata rezerwujemy przed HTTP (T-002 §5). */
    private suspend fun withCandidateSlot(block: suspend (RevocationReservation) -> Unit) {
        val reservation = try {
            withContext(Dispatchers.IO) {
                revocationStore.reserve(activeSession = sessionCoordinator.state.value is SessionState.Active)
            }
        } catch (e: RevocationQueueFullException) {
            revocationScheduler.runNow()
            throw e
        }
        try {
            block(reservation)
        } finally {
            revocationStore.release(reservation)
        }
    }

    /**
     * Odpowiedź loginu jest kandydatem: dopiero po porównaniu `user_id` z właścicielem danych
     * zostaje zapisana. Błąd lub odmowa zostawia poprzednie dane nietknięte (T-002 §4).
     */
    private suspend fun installCandidate(tokens: TokenResponse, slot: RevocationReservation) {
        val candidateUserId = tokens.user_id?.takeIf { it.isNotBlank() } ?: run {
            revokeCandidate(tokens, slot)
            throw SessionInstallException("missing user_id")
        }
        val transitionId = UUID.randomUUID().toString()
        when (val decision = offlineStore.beginInstall(candidateUserId, transitionId)) {
            is LoginDecision.OtherAccount -> {
                revokeCandidate(tokens, slot)
                throw OtherAccountDataException(decision.unsentCount)
            }
            is LoginDecision.LegacyQuarantine -> {
                revokeCandidate(tokens, slot)
                throw UnclaimedLocalDataException(decision.unsentCount)
            }
            LoginDecision.Claim -> {
                tokenStore.clear()
                importStatePersistence.saveJobId(null)
                signOutCleanup.afterOwnerDataRemoved()
            }
            LoginDecision.SameOwner -> Unit
        }
        try {
            sessionCoordinator.install(tokens)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            revokeCandidate(tokens, slot)
            throw e
        }
        offlineStore.completeInstall(transitionId)
    }

    /** Niezapisany kandydat dostaje własne trwałe zlecenie; nie zastępuje sesji A. */
    private suspend fun revokeCandidate(tokens: TokenResponse, slot: RevocationReservation) {
        val material = RevocationMaterial(
            ownerUserId = tokens.user_id,
            sessionId = tokens.session_id,
            refreshToken = tokens.refresh_token,
            pendingRefresh = null,
        )
        try {
            withContext(Dispatchers.IO) { revocationStore.add(material, slot) }
            revocationScheduler.runNow()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Bez trwałego zlecenia zostaje jedna próba; awaria nie zmienia decyzji loginu.
            runCatching { api.logout(LogoutRequest(tokens.refresh_token)) }
        }
    }

    /**
     * Zamiar wylogowania trafia do Room, a zlecenie odwołania do zaszyfrowanej kolejki, zanim
     * znikną poświadczenia; restart dokończy cleanup zamiast wskrzesić dane poprzedniego konta.
     * Niewysłana praca spoza [consent] przerywa logout przed zmianą sesji
     * ([com.vocabulario.app.data.session.UnsentChangesException]).
     * Zwraca true, gdy odwołanie na serwerze czeka na wysłanie.
     */
    suspend fun logout(consent: LogoutConsent = LogoutConsent.RequireEmpty): Boolean {
        val transitionId = UUID.randomUUID().toString()
        offlineStore.beginLogout(transitionId, consent)
        var queued: RevocationRequest? = null
        try {
            sessionCoordinator.signOutLocally { material -> queued = revocationStore.add(material) }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // Sesja zostaje, więc zlecenie nie może jej odwołać za plecami użytkownika.
            queued?.let { request ->
                runCatching { withContext(Dispatchers.IO) { revocationStore.update(request.id) { null } } }
            }
            offlineStore.abortLogout(transitionId)
            throw e
        }
        finishLogoutLocally()
        if (queued != null) revocationScheduler.runNow()
        return queued != null
    }

    val revocationSummary: StateFlow<RevocationSummary> get() = revocationStore.summary

    suspend fun dismissUnconfirmedRevocations() {
        withContext(Dispatchers.IO) { runCatching { revocationStore.dismissUnconfirmed() } }
    }

    /** Świadome odrzucenie danych, których nie można przypisać do konta (stara instalacja). */
    suspend fun discardUnclaimedLocalData(): Boolean {
        val discarded = offlineStore.discardUnclaimedData()
        if (discarded) {
            tokenStore.clear()
            importStatePersistence.saveJobId(null)
            signOutCleanup.afterOwnerDataRemoved()
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
                if (state !is SessionState.SignedOut) {
                    var queued = false
                    sessionCoordinator.signOutLocally { material ->
                        // Przy przerwanym logout prywatność ma pierwszeństwo: brak zlecenia nie blokuje cleanupu.
                        queued = runCatching { revocationStore.add(material) }.isSuccess
                    }
                    if (queued) revocationScheduler.runNow()
                }
                finishLogoutLocally()
            }
            StartupAction.AbortLogout -> {
                // Zgoda nie obejmuje obecnych kolejek: dane zostają, sesja (jeśli jest) też.
                val aborted = snapshot.transitionId?.let { offlineStore.abortLogout(it) } ?: false
                if (aborted) reconcileOwnerOnStart()
            }
            is StartupAction.ClaimEmpty ->
                if (!offlineStore.claimEmpty(action.ownerUserId)) {
                    sessionCoordinator.requireReauth(REAUTH_REASON_SESSION_MISMATCH)
                }
            is StartupAction.RequireReauth -> sessionCoordinator.requireReauth(action.reason)
        }
    }

    /**
     * Bez pełnego czyszczenia (praca spoza zgody) zostają też ustawienia lokalne właściciela.
     * Spóźniona praca A nie zapisze nic po tym kroku: generacja i faza nie pasują do jej zakresu.
     */
    private suspend fun finishLogoutLocally() {
        if (!offlineStore.completeLogout()) return
        tokenStore.clear()
        importStatePersistence.saveJobId(null)
        signOutCleanup.afterOwnerDataRemoved()
    }

    /**
     * Pusta lista jest „brak profilu" wyłącznie po poprawnym 200 serwera; błąd sieci, 5xx czy
     * auth nigdy nie wysyła użytkownika do onboardingu.
     */
    suspend fun resolveProfiles(): ProfileResolution {
        val cachedActive = offlineStore.cachedActiveProfile()
        val cached = offlineStore.cachedProfiles()
        if (cachedActive != null || cached.isNotEmpty()) {
            return ProfileResolution.Found(cached, cachedActive?.id, ProfileResolution.Source.CACHE)
        }
        val profiles = try {
            api.listProfiles()
        } catch (e: SupersededException) {
            return ProfileResolution.Superseded
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            return resolveProfileFailure(e.toSyncFailure(), hasCache = false)
        }
        if (profiles.isEmpty()) return ProfileResolution.ConfirmedEmpty
        return try {
            offlineStore.cacheProfiles(profiles)
            ProfileResolution.Found(profiles, profiles.firstOrNull { it.is_active }?.id, ProfileResolution.Source.SERVER)
        } catch (e: SupersededException) {
            ProfileResolution.Superseded
        }
    }

    suspend fun ensureActiveProfile() {
        val localActive = offlineStore.cachedActiveProfile()
        val storedId = tokenStore.activeProfileId.value ?: localActive?.id
        val profiles = runCatching { api.listProfiles() }.getOrNull()
        if (profiles != null) {
            val merged = mergeRemoteProfiles(
                remote = profiles,
                local = offlineStore.cachedProfiles(),
                drafts = offlineStore.profileDrafts(),
                protectedIds = offlineStore.profilesWithPendingWork(),
                chosenId = storedId,
            )
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
