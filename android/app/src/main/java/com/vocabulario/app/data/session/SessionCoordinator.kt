package com.vocabulario.app.data.session

import com.vocabulario.app.data.api.TokenResponse
import com.vocabulario.app.data.api.jwtIsExpiringSoon
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

sealed interface RefreshOutcome {
    data class Refreshed(val accessToken: String) : RefreshOutcome
    data class Rejected(val reason: String) : RefreshOutcome
    data class Failed(val detail: String) : RefreshOutcome
    data object NoSession : RefreshOutcome
}

class SessionInstallException(message: String) : IllegalStateException(message)

/**
 * Jedno źródło prawdy o sesji (E-001/F-003/T-002). Wszystkie zmiany idą pod jedną blokadą
 * (interceptor, authenticator, repozytorium) i są trwale zapisane, zanim trafią do pamięci.
 */
@Singleton
class SessionCoordinator @Inject constructor(
    private val persistence: SessionPersistence,
    private val transport: RefreshTransport,
    private val legacyTokens: LegacyTokenSource,
) {
    private val lock = Any()

    @Volatile
    private var loaded = false

    @Volatile
    private var current: SessionRecord? = null

    private val _state = MutableStateFlow<SessionState>(SessionState.Loading)
    val state: StateFlow<SessionState> = _state.asStateFlow()

    suspend fun awaitLoaded(): SessionState = withContext(Dispatchers.IO) {
        ensureLoaded()
        state.value
    }

    fun ensureLoaded() {
        if (loaded) return
        synchronized(lock) {
            if (loaded) return
            loadLocked()
            loaded = true
        }
    }

    /** Tylko pamięć — nie blokuje wątku. */
    fun peekAccessToken(): String? = current?.takeIf { it.status == SessionStatus.ACTIVE }?.accessToken

    /** Dla interceptora: proaktywny refresh, gdy access zaraz wygaśnie. Błąd przejściowy zostawia stary access. */
    fun accessTokenForRequest(): String? {
        ensureLoaded()
        val token = peekAccessToken() ?: return null
        if (!jwtIsExpiringSoon(token)) return token
        return synchronized(lock) {
            val newest = peekAccessToken() ?: return@synchronized null
            if (!jwtIsExpiringSoon(newest)) return@synchronized newest
            when (val outcome = refreshLocked()) {
                is RefreshOutcome.Refreshed -> outcome.accessToken
                else -> peekAccessToken()
            }
        }
    }

    /** Dla authenticatora po 401: co najwyżej jeden refresh na wspólnej blokadzie. */
    fun refreshAfterUnauthorized(failedAccessToken: String?): String? {
        ensureLoaded()
        return synchronized(lock) {
            val newest = peekAccessToken()
            if (!newest.isNullOrBlank() && newest != failedAccessToken) return@synchronized newest
            (refreshLocked() as? RefreshOutcome.Refreshed)?.accessToken
        }
    }

    fun refreshNow(): RefreshOutcome {
        ensureLoaded()
        return synchronized(lock) { refreshLocked() }
    }

    /** Instaluje parę z loginu/rejestracji; rzuca, gdy odpowiedź jest niekompletna lub zapis zawiódł. */
    suspend fun install(tokens: TokenResponse) = withContext(Dispatchers.IO) {
        val record = completeRecordOrNull(tokens)
            ?: throw SessionInstallException("incomplete token response")
        ensureLoaded()
        synchronized(lock) {
            persistence.write(record)
            current = record
            publish()
        }
    }

    /**
     * Lokalne usunięcie rekordu sesji; rzuca, gdy zapis zawiódł (pamięć zostaje bez zmian).
     * [beforeClear] dostaje materiał odwołania pod tą samą blokadą co refresh, więc nie przegapi
     * rotacji; jego wyjątek przerywa wylogowanie, zanim znikną poświadczenia.
     */
    suspend fun signOutLocally(beforeClear: (RevocationMaterial) -> Unit = {}) = withContext(Dispatchers.IO) {
        ensureLoaded()
        synchronized(lock) {
            current?.revocationMaterial()?.let(beforeClear)
            persistence.write(null)
            current = null
            publish()
        }
    }

    /** Aktywna sesja nie pasuje do właściciela danych lokalnych: wymagany ponowny login. */
    suspend fun requireReauth(reason: String) = withContext(Dispatchers.IO) {
        ensureLoaded()
        synchronized(lock) {
            if (current?.status == SessionStatus.ACTIVE) requireReauthLocked(reason)
        }
    }

    /** Ponowny odczyt po nieczytelnym magazynie (np. chwilowo niedostępny klucz); niczego nie kasuje. */
    suspend fun retryLoad(): SessionState = withContext(Dispatchers.IO) {
        ensureLoaded()
        synchronized(lock) {
            if (_state.value is SessionState.RecoveryRequired) loadLocked()
        }
        state.value
    }

    private fun loadLocked() {
        val stored = try {
            persistence.read()
        } catch (e: Exception) {
            StoredSession.Unreadable(RECOVERY_STORAGE)
        }
        when (stored) {
            is StoredSession.Present -> {
                current = stored.record
                runCatching { legacyTokens.removeLegacyTokens() }
                publish()
            }
            is StoredSession.Unreadable -> {
                current = null
                _state.value = SessionState.RecoveryRequired(stored.reason)
            }
            StoredSession.Empty -> {
                current = migrateLegacyLocked()
                publish()
            }
        }
    }

    private fun migrateLegacyLocked(): SessionRecord? {
        val (access, refresh) = runCatching { legacyTokens.readLegacyTokens() }.getOrNull() ?: return null
        val record = SessionRecord(accessToken = access, refreshToken = refresh)
        val persisted = runCatching { persistence.write(record) }.isSuccess
        // Jawne tokeny usuwamy dopiero po trwałym zapisie zaszyfrowanego rekordu.
        if (persisted) runCatching { legacyTokens.removeLegacyTokens() }
        return record
    }

    private fun refreshLocked(): RefreshOutcome {
        val record = current?.takeIf { it.status == SessionStatus.ACTIVE } ?: return RefreshOutcome.NoSession
        val input = record.refreshToken?.takeIf { it.isNotBlank() } ?: return RefreshOutcome.NoSession
        val pending = record.pendingRefresh?.takeIf { it.inputRefresh == input }
            ?: PendingRefresh(UUID.randomUUID().toString(), input).also { fresh ->
                val withPending = record.copy(pendingRefresh = fresh)
                try {
                    persistence.write(withPending)
                } catch (e: Exception) {
                    return RefreshOutcome.Failed("storage")
                }
                current = withPending
            }

        val result = try {
            transport.refresh(pending.inputRefresh, pending.requestId)
        } catch (e: Exception) {
            RefreshHttpResult.Transient("transport")
        }
        return when (result) {
            is RefreshHttpResult.Ok -> installRefreshedLocked(result.tokens)
            is RefreshHttpResult.Transient -> RefreshOutcome.Failed(result.detail)
            is RefreshHttpResult.Rejected ->
                if (result.code == CODE_REFRESH_CONFLICT) resolveConflictLocked(pending) else requireReauthLocked(result.code)
        }
    }

    private fun installRefreshedLocked(tokens: TokenResponse): RefreshOutcome {
        val record = current ?: return RefreshOutcome.NoSession
        val complete = completeRecordOrNull(tokens) ?: return RefreshOutcome.Failed("incomplete_response")
        val ownerChanged = record.ownerUserId != null && record.ownerUserId != complete.ownerUserId
        val sessionChanged = record.sessionId != null && record.sessionId != complete.sessionId
        if (ownerChanged || sessionChanged) return requireReauthLocked(REAUTH_REASON_SESSION_MISMATCH)
        try {
            persistence.write(complete)
        } catch (e: Exception) {
            // Pending zostaje: kolejna próba z tym samym ID odzyska tę samą parę w oknie retry.
            return RefreshOutcome.Failed("storage")
        }
        current = complete
        publish()
        return RefreshOutcome.Refreshed(complete.accessToken!!)
    }

    /** 409: jednorazowo porównaj z trwałym snapshotem; bez pętli ponowień. */
    private fun resolveConflictLocked(pending: PendingRefresh): RefreshOutcome {
        val stored = (runCatching { persistence.read() }.getOrNull() as? StoredSession.Present)?.record
        val adopted = stored?.takeIf {
            it.status == SessionStatus.ACTIVE &&
                !it.accessToken.isNullOrBlank() &&
                !it.refreshToken.isNullOrBlank() &&
                it.refreshToken != pending.inputRefresh
        }
        if (adopted != null) {
            current = adopted
            publish()
            return RefreshOutcome.Refreshed(adopted.accessToken!!)
        }
        return requireReauthLocked(CODE_REFRESH_CONFLICT)
    }

    /** Odrzucona sesja: bez tokenów, ale z właścicielem; danych lokalnych nie dotykamy. */
    private fun requireReauthLocked(reason: String): RefreshOutcome {
        val record = current ?: return RefreshOutcome.NoSession
        val reauth = record.copy(
            accessToken = null,
            refreshToken = null,
            pendingRefresh = null,
            status = SessionStatus.REAUTH_REQUIRED,
            reauthReason = reason,
        )
        // Nieudany zapis nie wskrzesza sesji: po restarcie serwer odrzuci ją ponownie.
        runCatching { persistence.write(reauth) }
        current = reauth
        publish()
        return RefreshOutcome.Rejected(reason)
    }

    private fun publish() {
        _state.value = current.toState()
    }

    private fun completeRecordOrNull(tokens: TokenResponse): SessionRecord? {
        val userId = tokens.user_id?.takeIf { it.isNotBlank() } ?: return null
        val sessionId = tokens.session_id?.takeIf { it.isNotBlank() } ?: return null
        if (tokens.access_token.isBlank() || tokens.refresh_token.isBlank()) return null
        return SessionRecord(
            ownerUserId = userId,
            sessionId = sessionId,
            accessToken = tokens.access_token,
            refreshToken = tokens.refresh_token,
        )
    }
}
