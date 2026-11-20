package com.vocabulario.app.data.session

import com.vocabulario.app.data.local.db.LogoutDisposition
import com.vocabulario.app.data.local.db.OwnerPhase
import java.security.MessageDigest

/** Odczyt rekordu właściciela Room razem z informacją, czy baza zawiera dane. */
data class OwnerSnapshot(
    val ownerUserId: String?,
    val generation: Long,
    val phase: String,
    val transitionId: String?,
    val hasOwnedData: Boolean,
    val unsentCount: Int,
    val unsentFingerprint: String = "",
    val logoutDisposition: String? = null,
    val acceptedUnsentFingerprint: String? = null,
)

/** Stabilny skrót zbioru niewysłanych operacji; pusta kolejka = pusty napis. */
fun unsentFingerprint(ids: Collection<String>): String {
    if (ids.isEmpty()) return ""
    val digest = MessageDigest.getInstance("SHA-256")
    ids.sorted().forEach { id ->
        digest.update(id.toByteArray(Charsets.UTF_8))
        digest.update(0)
    }
    return digest.digest().joinToString("") { byte -> (byte.toInt() and 0xff).toString(16).padStart(2, '0') }
}

/** Decyzja użytkownika o niewysłanych zmianach przy wylogowaniu (T-002 §5). */
sealed interface LogoutConsent {
    /** Wyloguj tylko przy pustych kolejkach. */
    data object RequireEmpty : LogoutConsent

    /** Odrzuć dokładnie ten snapshot kolejek, który użytkownik widział w ostrzeżeniu. */
    data class DiscardConfirmed(val fingerprint: String) : LogoutConsent

    val disposition: String
        get() = when (this) {
            RequireEmpty -> LogoutDisposition.REQUIRE_EMPTY
            is DiscardConfirmed -> LogoutDisposition.DISCARD_CONFIRMED
        }

    val acceptedFingerprint: String?
        get() = (this as? DiscardConfirmed)?.fingerprint
}

/** Kolejki zawierają pracę nieobjętą zgodą; wymagane (ponowne) potwierdzenie użytkownika. */
class UnsentChangesException(val unsentCount: Int, val fingerprint: String) : Exception("unsent_changes")

fun consentCovers(disposition: String?, accepted: String?, unsentCount: Int, fingerprint: String): Boolean =
    unsentCount == 0 ||
        (disposition == LogoutDisposition.DISCARD_CONFIRMED && accepted == fingerprint)

/** Czy zapisana zgoda obejmuje obecne kolejki; brak dyspozycji traktujemy jak `require_empty`. */
fun logoutCovered(snapshot: OwnerSnapshot): Boolean = consentCovers(
    snapshot.logoutDisposition,
    snapshot.acceptedUnsentFingerprint,
    snapshot.unsentCount,
    snapshot.unsentFingerprint,
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

    /** Przerwany logout, którego zgoda nie obejmuje obecnych kolejek: dane zostają. */
    data object AbortLogout : StartupAction

    /** Aktywna sesja bez danych (np. świeża baza po migracji) przejmuje pustą bazę. */
    data class ClaimEmpty(val ownerUserId: String) : StartupAction

    /** Aktywna sesja nie pasuje do właściciela danych: bez wysyłki kolejek, wymagany login. */
    data class RequireReauth(val reason: String) : StartupAction
}

fun decideStartup(snapshot: OwnerSnapshot, state: SessionState): StartupAction {
    if (snapshot.phase == OwnerPhase.LOGGING_OUT) {
        return if (logoutCovered(snapshot)) StartupAction.CompleteLogout else StartupAction.AbortLogout
    }
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

enum class AuthNoticeKind {
    /** Sesja odwołana/wygasła: login tego samego konta zachowuje dane. */
    REAUTH,

    /** Zapisanej sesji nie da się odczytać: ponowienie albo login tego samego konta. */
    RECOVERY,

    /** Brak sesji, ale na urządzeniu zostały dane konta (np. przerwane wylogowanie). */
    LOCAL_DATA,
}

/** Informacja na ekranie logowania; wyjście „wyloguj na tym urządzeniu” usuwa [hasLocalData]. */
data class AuthNotice(
    val kind: AuthNoticeKind,
    val hasLocalData: Boolean,
    val unsentCount: Int,
    /** Snapshot pokazany w ostrzeżeniu; wyjście odrzuca tylko te zmiany. */
    val unsentFingerprint: String = "",
)

fun authNotice(state: SessionState, snapshot: OwnerSnapshot): AuthNotice? {
    // Trwające wylogowanie zaraz usunie dane; karta byłaby nieaktualna.
    if (snapshot.phase == OwnerPhase.LOGGING_OUT) return null
    val kind = when (state) {
        is SessionState.ReauthRequired -> AuthNoticeKind.REAUTH
        is SessionState.RecoveryRequired -> AuthNoticeKind.RECOVERY
        // Dane bez właściciela obsługuje osobny dialog kwarantanny przy próbie loginu.
        SessionState.SignedOut ->
            AuthNoticeKind.LOCAL_DATA.takeIf { snapshot.hasOwnedData && snapshot.ownerUserId != null }
        else -> null
    } ?: return null
    return AuthNotice(
        kind = kind,
        hasLocalData = snapshot.hasOwnedData,
        unsentCount = if (snapshot.hasOwnedData) snapshot.unsentCount else 0,
        unsentFingerprint = if (snapshot.hasOwnedData) snapshot.unsentFingerprint else "",
    )
}

/** Utrata sesji w trakcie pracy przenosi z ekranów konta na logowanie, bez kasowania danych. */
fun sessionLost(state: SessionState): Boolean =
    state is SessionState.SignedOut ||
        state is SessionState.ReauthRequired ||
        state is SessionState.RecoveryRequired