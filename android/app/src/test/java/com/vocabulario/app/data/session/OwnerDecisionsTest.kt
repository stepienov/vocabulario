package com.vocabulario.app.data.session

import com.vocabulario.app.data.local.db.LogoutDisposition
import com.vocabulario.app.data.local.db.OwnerPhase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OwnerDecisionsTest {

    private fun snapshot(
        owner: String? = null,
        phase: String = OwnerPhase.SIGNED_OUT,
        hasData: Boolean = false,
        unsent: Int = 0,
        transitionId: String? = null,
        fingerprint: String = "",
        disposition: String? = null,
        accepted: String? = null,
    ) = OwnerSnapshot(
        owner,
        generation = 3,
        phase = phase,
        transitionId = transitionId,
        hasOwnedData = hasData,
        unsentCount = unsent,
        unsentFingerprint = fingerprint,
        logoutDisposition = disposition,
        acceptedUnsentFingerprint = accepted,
    )

    private fun active(owner: String?) = SessionState.Active(owner, "s1")

    @Test
    fun loginOnEmptyDatabaseClaimsIt() {
        assertEquals(LoginDecision.Claim, decideLogin(snapshot(), "B"))
        // Pusta baza poprzedniego właściciela (np. nieudana instalacja) nie blokuje innego konta.
        assertEquals(LoginDecision.Claim, decideLogin(snapshot(owner = "A", phase = OwnerPhase.INSTALLING), "B"))
    }

    @Test
    fun loginOfSameOwnerKeepsData() {
        val s = snapshot(owner = "A", phase = OwnerPhase.ACTIVE, hasData = true, unsent = 4)
        assertEquals(LoginDecision.SameOwner, decideLogin(s, "A"))
    }

    @Test
    fun loginOfOtherAccountWithDataIsRefused() {
        val s = snapshot(owner = "A", phase = OwnerPhase.ACTIVE, hasData = true, unsent = 2)
        assertEquals(LoginDecision.OtherAccount(2), decideLogin(s, "B"))
    }

    @Test
    fun legacyDataIsNeverAssignedAutomatically() {
        val legacy = snapshot(phase = OwnerPhase.LEGACY_UNCLAIMED, hasData = true, unsent = 5)
        assertEquals(LoginDecision.LegacyQuarantine(5), decideLogin(legacy, "A"))
        val ownerless = snapshot(phase = OwnerPhase.SIGNED_OUT, hasData = true, unsent = 0)
        assertEquals(LoginDecision.LegacyQuarantine(0), decideLogin(ownerless, "A"))
    }

    @Test
    fun startupContinuesInterruptedLogoutInAnySessionState() {
        val s = snapshot(owner = "A", phase = OwnerPhase.LOGGING_OUT, hasData = true)
        assertEquals(StartupAction.CompleteLogout, decideStartup(s, active("A")))
        assertEquals(StartupAction.CompleteLogout, decideStartup(s, SessionState.SignedOut))
    }

    @Test
    fun interruptedLogoutNeverDerivesDiscardConsentFromPhaseAlone() {
        val fp = unsentFingerprint(listOf("r:1", "o:7"))
        fun loggingOut(disposition: String?, accepted: String?) = snapshot(
            owner = "A",
            phase = OwnerPhase.LOGGING_OUT,
            hasData = true,
            unsent = 2,
            fingerprint = fp,
            disposition = disposition,
            accepted = accepted,
        )
        assertEquals(StartupAction.AbortLogout, decideStartup(loggingOut(null, null), SessionState.SignedOut))
        assertEquals(
            StartupAction.AbortLogout,
            decideStartup(loggingOut(LogoutDisposition.REQUIRE_EMPTY, null), active("A")),
        )
        assertEquals(
            StartupAction.CompleteLogout,
            decideStartup(loggingOut(LogoutDisposition.DISCARD_CONFIRMED, fp), SessionState.SignedOut),
        )
        // Praca dopisana po potwierdzeniu zmienia fingerprint: zgoda jej nie obejmuje.
        val older = unsentFingerprint(listOf("r:1"))
        assertEquals(
            StartupAction.AbortLogout,
            decideStartup(loggingOut(LogoutDisposition.DISCARD_CONFIRMED, older), SessionState.SignedOut),
        )
    }

    @Test
    fun fingerprintIdentifiesExactSetOfUnsentOperations() {
        assertEquals("", unsentFingerprint(emptyList()))
        assertEquals(unsentFingerprint(listOf("r:a", "m:b")), unsentFingerprint(listOf("m:b", "r:a")))
        assertNotEquals(unsentFingerprint(listOf("r:a")), unsentFingerprint(listOf("r:a", "o:1")))
        // Separator: sklejenie identyfikatorów nie daje kolizji.
        assertNotEquals(unsentFingerprint(listOf("r:ab")), unsentFingerprint(listOf("r:a", "b")))
    }

    @Test
    fun logoutConsentCoversOnlyEmptyQueuesOrTheConfirmedSnapshot() {
        val fp = unsentFingerprint(listOf("l:x"))
        val requireEmpty = LogoutConsent.RequireEmpty
        val discard = LogoutConsent.DiscardConfirmed(fp)
        assertTrue(consentCovers(requireEmpty.disposition, requireEmpty.acceptedFingerprint, 0, ""))
        assertFalse(consentCovers(requireEmpty.disposition, requireEmpty.acceptedFingerprint, 1, fp))
        assertTrue(consentCovers(discard.disposition, discard.acceptedFingerprint, 1, fp))
        assertFalse(consentCovers(discard.disposition, discard.acceptedFingerprint, 2, unsentFingerprint(listOf("l:x", "l:y"))))
        // Inny zbiór tej samej wielkości też wymaga nowej decyzji; pusta kolejka zawsze wystarcza.
        assertFalse(consentCovers(discard.disposition, discard.acceptedFingerprint, 1, unsentFingerprint(listOf("l:z"))))
        assertTrue(consentCovers(discard.disposition, discard.acceptedFingerprint, 0, ""))
    }

    @Test
    fun startupCompletesInstallOnlyForMatchingOwner() {
        val installing = snapshot(owner = "A", phase = OwnerPhase.INSTALLING, hasData = true, transitionId = "t")
        assertEquals(StartupAction.CompleteInstall, decideStartup(installing, active("A")))
        assertEquals(
            StartupAction.RequireReauth(REAUTH_REASON_SESSION_MISMATCH),
            decideStartup(installing, active("B")),
        )
    }

    @Test
    fun startupWithoutActiveSessionChangesNothing() {
        val s = snapshot(owner = "A", phase = OwnerPhase.INSTALLING, hasData = true)
        assertEquals(StartupAction.None, decideStartup(s, SessionState.ReauthRequired("A", "x")))
        assertEquals(StartupAction.None, decideStartup(s, SessionState.SignedOut))
    }

    @Test
    fun startupMatchingActiveOwnerIsNoop() {
        val s = snapshot(owner = "A", phase = OwnerPhase.ACTIVE, hasData = true)
        assertEquals(StartupAction.None, decideStartup(s, active("A")))
    }

    @Test
    fun startupActiveSessionClaimsEmptyDatabase() {
        assertEquals(StartupAction.ClaimEmpty("A"), decideStartup(snapshot(), active("A")))
    }

    @Test
    fun startupBlocksSessionThatDoesNotOwnLocalData() {
        val legacy = snapshot(phase = OwnerPhase.LEGACY_UNCLAIMED, hasData = true)
        assertEquals(StartupAction.RequireReauth(REAUTH_REASON_LEGACY_DATA), decideStartup(legacy, active("A")))
        val other = snapshot(owner = "B", phase = OwnerPhase.ACTIVE, hasData = true)
        assertEquals(StartupAction.RequireReauth(REAUTH_REASON_SESSION_MISMATCH), decideStartup(other, active("A")))
        assertEquals(
            StartupAction.RequireReauth(REAUTH_REASON_OWNER_UNKNOWN),
            decideStartup(snapshot(), active(null)),
        )
    }

    @Test
    fun authNoticeExplainsReauthAndRecoveryWithLocalData() {
        val owned = snapshot(owner = "A", phase = OwnerPhase.ACTIVE, hasData = true, unsent = 3)
        assertEquals(
            AuthNotice(AuthNoticeKind.REAUTH, hasLocalData = true, unsentCount = 3),
            authNotice(SessionState.ReauthRequired("A", REAUTH_REASON_UNKNOWN), owned),
        )
        assertEquals(
            AuthNotice(AuthNoticeKind.RECOVERY, hasLocalData = false, unsentCount = 0),
            authNotice(SessionState.RecoveryRequired(RECOVERY_UNREADABLE), snapshot(unsent = 5)),
        )
        // Dane bez właściciela przy reauth też są liczone, bo wyjście je usuwa.
        val legacy = snapshot(phase = OwnerPhase.LEGACY_UNCLAIMED, hasData = true, unsent = 1)
        assertEquals(
            AuthNotice(AuthNoticeKind.REAUTH, hasLocalData = true, unsentCount = 1),
            authNotice(SessionState.ReauthRequired(null, REAUTH_REASON_LEGACY_DATA), legacy),
        )
    }

    @Test
    fun signedOutNoticeOnlyForDataOfKnownOwner() {
        val owned = snapshot(owner = "A", phase = OwnerPhase.ACTIVE, hasData = true, unsent = 2)
        assertEquals(
            AuthNotice(AuthNoticeKind.LOCAL_DATA, hasLocalData = true, unsentCount = 2),
            authNotice(SessionState.SignedOut, owned),
        )
        assertEquals(null, authNotice(SessionState.SignedOut, snapshot()))
        // Dane legacy obsługuje dialog kwarantanny przy loginie, nie karta.
        assertEquals(
            null,
            authNotice(SessionState.SignedOut, snapshot(phase = OwnerPhase.LEGACY_UNCLAIMED, hasData = true)),
        )
        assertEquals(null, authNotice(active("A"), owned))
        assertEquals(null, authNotice(SessionState.Loading, owned))
        val loggingOut = snapshot(owner = "A", phase = OwnerPhase.LOGGING_OUT, hasData = true)
        assertEquals(null, authNotice(SessionState.SignedOut, loggingOut))
    }

    @Test
    fun onlyEndedSessionsLeaveAccountScreens() {
        assertEquals(true, sessionLost(SessionState.SignedOut))
        assertEquals(true, sessionLost(SessionState.ReauthRequired("A", REAUTH_REASON_UNKNOWN)))
        assertEquals(true, sessionLost(SessionState.RecoveryRequired(RECOVERY_STORAGE)))
        assertEquals(false, sessionLost(SessionState.Loading))
        assertEquals(false, sessionLost(active("A")))
    }
}
