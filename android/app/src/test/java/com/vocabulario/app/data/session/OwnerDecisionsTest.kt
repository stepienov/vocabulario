package com.vocabulario.app.data.session

import com.vocabulario.app.data.local.db.OwnerPhase
import org.junit.Assert.assertEquals
import org.junit.Test

class OwnerDecisionsTest {

    private fun snapshot(
        owner: String? = null,
        phase: String = OwnerPhase.SIGNED_OUT,
        hasData: Boolean = false,
        unsent: Int = 0,
        transitionId: String? = null,
    ) = OwnerSnapshot(owner, generation = 3, phase = phase, transitionId = transitionId, hasOwnedData = hasData, unsentCount = unsent)

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
}
