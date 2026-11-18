package com.vocabulario.app.data.session

import com.vocabulario.app.data.local.db.OwnerPhase

/** Odczyt rekordu właściciela Room razem z informacją, czy baza zawiera dane. */
data class OwnerSnapshot(
    val ownerUserId: String?,
    val generation: Long,
    val phase: String,
    val transitionId: String?,
    val hasOwnedData: Boolean,
    val unsentCount: Int,
)

sealed interface LoginDecision {
    /** Baza bez danych: kandydat staje się właścicielem. */
    data object Claim : LoginDecision

    /** Ten sam `user_id`: reauth bez usuwania danych i kolejek. */
    data object SameOwner : LoginDecision

    /** Dane innego konta: bez podpięcia jego kolejki; zmiana konta tylko przez jawny logout. */
    data class OtherAccount(val unsentCount: Int) : LoginDecision

    /** Dane bez wiarygodnego właściciela: nie przypisujemy ich automatycznie żadnemu kontu. */
    data class LegacyQuarantine(val unsentCount: Int) : LoginDecision
}

fun decideLogin(snapshot: OwnerSnapshot, candidateUserId: String): LoginDecision = when {
    snapshot.phase == OwnerPhase.LEGACY_UNCLAIMED && snapshot.hasOwnedData ->
        LoginDecision.LegacyQuarantine(snapshot.unsentCount)
    snapshot.ownerUserId == null && snapshot.hasOwnedData ->
        LoginDecision.LegacyQuarantine(snapshot.unsentCount)
    snapshot.ownerUserId == candidateUserId -> LoginDecision.SameOwner
    !snapshot.hasOwnedData -> LoginDecision.Claim
    else -> LoginDecision.OtherAccount(snapshot.unsentCount)
}

sealed interface StartupAction {
    data object None : StartupAction

    /** Restart po zapisie sesji, ale przed zakończeniem przejścia w Room. */
    data object CompleteInstall : StartupAction

    /** Zapisany zamiar wylogowania jest kontynuowany po restarcie. */
    data object CompleteLogout : StartupAction

    /** Aktywna sesja bez danych (np. świeża baza po migracji) przejmuje pustą bazę. */
    data class ClaimEmpty(val ownerUserId: String) : StartupAction

    /** Aktywna sesja nie pasuje do właściciela danych: bez wysyłki kolejek, wymagany login. */
    data class RequireReauth(val reason: String) : StartupAction
}

fun decideStartup(snapshot: OwnerSnapshot, state: SessionState): StartupAction {
    if (snapshot.phase == OwnerPhase.LOGGING_OUT) return StartupAction.CompleteLogout
    if (state !is SessionState.Active) return StartupAction.None
    val sessionOwner = state.ownerUserId ?: return StartupAction.RequireReauth(REAUTH_REASON_OWNER_UNKNOWN)
    if (snapshot.phase == OwnerPhase.LEGACY_UNCLAIMED && snapshot.hasOwnedData) {
        return StartupAction.RequireReauth(REAUTH_REASON_LEGACY_DATA)
    }
    if (snapshot.ownerUserId == sessionOwner) {
        return when (snapshot.phase) {
            OwnerPhase.ACTIVE -> StartupAction.None
            OwnerPhase.INSTALLING -> StartupAction.CompleteInstall
            else -> StartupAction.ClaimEmpty(sessionOwner).takeIf { !snapshot.hasOwnedData }
                ?: StartupAction.RequireReauth(REAUTH_REASON_SESSION_MISMATCH)
        }
    }
    if (!snapshot.hasOwnedData) return StartupAction.ClaimEmpty(sessionOwner)
    return StartupAction.RequireReauth(REAUTH_REASON_SESSION_MISMATCH)
}
