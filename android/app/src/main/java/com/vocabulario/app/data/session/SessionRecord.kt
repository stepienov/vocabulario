package com.vocabulario.app.data.session

import kotlinx.serialization.Serializable

const val SESSION_RECORD_VERSION = 1

/** Refresh, którego wynik mógł zaginąć; ponawiany z tym samym ID (kontrakt F-003/T-001). */
@Serializable
data class PendingRefresh(
    val requestId: String,
    val inputRefresh: String,
)

/** Jedyny trwały rekord sesji; zapisywany w całości przed publikacją w pamięci. */
@Serializable
data class SessionRecord(
    val version: Int = SESSION_RECORD_VERSION,
    val ownerUserId: String? = null,
    val sessionId: String? = null,
    val accessToken: String? = null,
    val refreshToken: String? = null,
    val pendingRefresh: PendingRefresh? = null,
    val status: SessionStatus = SessionStatus.ACTIVE,
    val reauthReason: String? = null,
)

@Serializable
enum class SessionStatus { ACTIVE, REAUTH_REQUIRED }

sealed interface SessionState {
    data object Loading : SessionState
    data object SignedOut : SessionState
    data class Active(val ownerUserId: String?, val sessionId: String?) : SessionState
    data class ReauthRequired(val ownerUserId: String?, val reason: String) : SessionState
    data class RecoveryRequired(val reason: String) : SessionState
}

internal fun SessionRecord?.toState(): SessionState = when {
    this == null -> SessionState.SignedOut
    status == SessionStatus.REAUTH_REQUIRED ->
        SessionState.ReauthRequired(ownerUserId, reauthReason ?: REAUTH_REASON_UNKNOWN)
    accessToken.isNullOrBlank() || refreshToken.isNullOrBlank() ->
        SessionState.ReauthRequired(ownerUserId, REAUTH_REASON_UNKNOWN)
    else -> SessionState.Active(ownerUserId, sessionId)
}

internal const val REAUTH_REASON_UNKNOWN = "unknown"
internal const val REAUTH_REASON_SESSION_MISMATCH = "session_mismatch"
internal const val REAUTH_REASON_OWNER_UNKNOWN = "owner_unknown"
internal const val REAUTH_REASON_LEGACY_DATA = "legacy_unclaimed"
internal const val RECOVERY_UNREADABLE = "session_unreadable"
internal const val RECOVERY_STORAGE = "session_storage_unavailable"
