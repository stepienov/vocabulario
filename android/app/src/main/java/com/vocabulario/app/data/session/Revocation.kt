package com.vocabulario.app.data.session

import com.vocabulario.app.data.UPDATE_REQUIRED_STATUS
import com.vocabulario.app.data.api.parseApiError
import kotlinx.serialization.Serializable

const val REVOCATION_QUEUE_VERSION = 1

/** Miejsca na zlecenia z sekretem, łącznie z rezerwacjami i miejscem aktywnej sesji (T-002 §5). */
const val REVOCATION_CAPACITY = 32

/** Ile zakończonych bez potwierdzenia wpisów (bez sekretów) trzymamy do pokazania użytkownikowi. */
internal const val REVOCATION_UNCONFIRMED_KEPT = 32

internal const val DEFAULT_RETRY_AFTER_MS = 60_000L
private const val MAX_RETRY_AFTER_MS = 60L * 60 * 1000

@Serializable
enum class RevocationState { PENDING, UNCONFIRMED }

/**
 * Zlecenie odwołania sesji na serwerze. Służy wyłącznie do `POST /auth/logout`
 * (i odzyskania rotacji tym samym pending ID) — nigdy do sync ani przywrócenia logowania.
 */
@Serializable
data class RevocationRequest(
    val id: String,
    val ownerUserId: String? = null,
    val sessionId: String? = null,
    val refreshToken: String? = null,
    val pendingRefresh: PendingRefresh? = null,
    val createdAtMs: Long,
    val state: RevocationState = RevocationState.PENDING,
    val notBeforeMs: Long = 0,
    val reason: String? = null,
) {
    val hasSecret: Boolean get() = !refreshToken.isNullOrBlank() || pendingRefresh != null

    fun unconfirmed(reason: String): RevocationRequest =
        copy(refreshToken = null, pendingRefresh = null, state = RevocationState.UNCONFIRMED, notBeforeMs = 0, reason = reason)
}

@Serializable
data class RevocationQueue(
    val version: Int = REVOCATION_QUEUE_VERSION,
    val requests: List<RevocationRequest> = emptyList(),
) {
    val pendingCount: Int get() = requests.count { it.state == RevocationState.PENDING }
    val unconfirmedCount: Int get() = requests.count { it.state == RevocationState.UNCONFIRMED }
}

data class RevocationSummary(val pending: Int = 0, val unconfirmed: Int = 0)

internal fun RevocationQueue.summary() = RevocationSummary(pendingCount, unconfirmedCount)

/** Materiał przenoszony z rekordu sesji do zlecenia przed usunięciem poświadczeń. */
data class RevocationMaterial(
    val ownerUserId: String?,
    val sessionId: String?,
    val refreshToken: String?,
    val pendingRefresh: PendingRefresh?,
)

internal fun SessionRecord.revocationMaterial(): RevocationMaterial? {
    if (status != SessionStatus.ACTIVE) return null
    if (refreshToken.isNullOrBlank() && pendingRefresh == null) return null
    return RevocationMaterial(ownerUserId, sessionId, refreshToken, pendingRefresh)
}

/** Usuwa tylko najstarsze wpisy bez sekretu; oczekujących zleceń nigdy nie wyrzucamy. */
internal fun trimUnconfirmed(requests: List<RevocationRequest>): List<RevocationRequest> {
    val unconfirmed = requests.filter { it.state == RevocationState.UNCONFIRMED }
    if (unconfirmed.size <= REVOCATION_UNCONFIRMED_KEPT) return requests
    val dropped = unconfirmed.sortedBy { it.createdAtMs }
        .take(unconfirmed.size - REVOCATION_UNCONFIRMED_KEPT)
        .map { it.id }
        .toSet()
    return requests.filterNot { it.id in dropped }
}

/** Rezerwacja dla kandydata: po sukcesie kandydat staje się aktywną sesją z własnym miejscem. */
internal fun canReserve(pending: Int, reservations: Int, activeSession: Boolean): Boolean {
    val used = pending + reservations + if (activeSession) 1 else 0
    return used + 1 <= REVOCATION_CAPACITY
}

internal const val REVOCATION_REASON_INVALID = "invalid_proof"

sealed interface LogoutHttpResult {
    /** 204: serwer odwołał sesję albo była już odwołana. */
    data object Revoked : LogoutHttpResult

    /** Definitywnie nieważny dowód; nie oznacza, że sesja została odwołana. */
    data class Invalid(val code: String) : LogoutHttpResult

    data class RetryAfter(val delayMs: Long) : LogoutHttpResult

    /** Timeout, brak sieci, 5xx lub nieoczekiwana odpowiedź. */
    data class Transient(val detail: String) : LogoutHttpResult
}

internal fun classifyLogoutResponse(httpStatus: Int, body: String, retryAfter: String?): LogoutHttpResult = when {
    httpStatus == 204 || httpStatus == 200 -> LogoutHttpResult.Revoked
    httpStatus == 429 -> LogoutHttpResult.RetryAfter(parseRetryAfterMs(retryAfter))
    httpStatus == 408 || httpStatus == UPDATE_REQUIRED_STATUS -> LogoutHttpResult.Transient("http_$httpStatus")
    httpStatus in 400..499 ->
        LogoutHttpResult.Invalid(parseApiError(body)?.code?.trim()?.lowercase() ?: "http_$httpStatus")
    else -> LogoutHttpResult.Transient("http_$httpStatus")
}

/** Obsługujemy sekundy (format backendu); brak lub data HTTP daje bezpieczny domyślny odstęp. */
internal fun parseRetryAfterMs(header: String?): Long {
    val seconds = header?.trim()?.toLongOrNull() ?: return DEFAULT_RETRY_AFTER_MS
    return (seconds * 1000).coerceIn(1_000L, MAX_RETRY_AFTER_MS)
}
