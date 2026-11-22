package com.vocabulario.app.data.sync

import com.vocabulario.app.data.api.LanguageProfileResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ProfileDraftTest {
    private fun server(cefr: String = "A2", revision: Long? = 3, tenses: List<String> = listOf("presente")) =
        LanguageProfileResponse(
            id = "p1",
            app_lang = "pl",
            learning_lang = "es",
            cefr_level = cefr,
            selected_tenses = tenses,
            is_active = true,
            revision = revision,
        )

    private fun op(
        seq: Long,
        fields: ProfileFields,
        status: String = "pending",
        attempts: Int = 0,
        lastError: String? = null,
        prev: ProfileFields? = null,
    ) = ProfileOpView(
        seq,
        status,
        attempts,
        lastError,
        ProfileUpdatePayload(profileId = "p1", fields = fields, prev = prev),
    )

    @Test
    fun overlayNewerFieldWinsAndRestStays() {
        val base = ProfileFields(cefr_level = "A2", selected_tenses = listOf("a"))
        val merged = base.overlaidBy(ProfileFields(cefr_level = "B1"))
        assertEquals("B1", merged.cefr_level)
        assertEquals(listOf("a"), merged.selected_tenses)
    }

    @Test
    fun validationRejectsUnknownLevelAndBadLabelLang() {
        assertTrue(validateProfileFields(ProfileFields(cefr_level = "B2")))
        assertFalse(validateProfileFields(ProfileFields(cefr_level = "Z9")))
        assertFalse(validateProfileFields(ProfileFields(tense_label_lang = "other")))
        assertFalse(validateProfileFields(ProfileFields(selected_tenses = listOf(" "))))
    }

    @Test
    fun mergeKeepsOldestPrevAndNewestValue() {
        val first = ProfileUpdatePayload(
            profileId = "p1",
            fields = ProfileFields(cefr_level = "B1"),
            prev = ProfileFields(cefr_level = "A2"),
        )
        val merged = first.mergedWith(ProfileFields(cefr_level = "B2"), ProfileFields(cefr_level = "B1"))
        assertEquals("B2", merged.fields.cefr_level)
        assertEquals("A2", merged.prev?.cefr_level)
    }

    @Test
    fun planMergesIntoNeverSentOp() {
        val existing = listOf(op(1, ProfileFields(cefr_level = "B1")))
        val plan = planProfileEdit("p1", ProfileFields(cefr_level = "B2"), ProfileFields(cefr_level = "B1"), 3, existing)
        plan as ProfileEditPlan.MergeInto
        assertEquals(1L, plan.seq)
        assertFalse(plan.newPending)
    }

    @Test
    fun planAppendsAfterSentOpWithoutBase() {
        val existing = listOf(op(1, ProfileFields(cefr_level = "B1"), attempts = 1, lastError = PROFILE_OP_SENT))
        val plan = planProfileEdit("p1", ProfileFields(cefr_level = "B2"), ProfileFields(cefr_level = "B1"), 3, existing)
        plan as ProfileEditPlan.Append
        assertNull(plan.payload.baseRevision)
    }

    @Test
    fun planUsesConfirmedRevisionWhenQueueEmpty() {
        val plan = planProfileEdit("p1", ProfileFields(cefr_level = "B2"), ProfileFields(cefr_level = "A2"), 3, emptyList())
        plan as ProfileEditPlan.Append
        assertEquals(3L, plan.payload.baseRevision)
    }

    @Test
    fun planRepairsInvalidBlockedOpAndRequeuesIt() {
        val existing = listOf(op(1, ProfileFields(cefr_level = "B1"), status = "blocked", lastError = ProfileBlock.INVALID))
        val plan = planProfileEdit("p1", ProfileFields(cefr_level = "B2"), ProfileFields(cefr_level = "B1"), 3, existing)
        plan as ProfileEditPlan.MergeInto
        assertTrue(plan.newPending)
    }

    @Test
    fun planKeepsConflictBlockedOpBlocked() {
        val existing = listOf(op(1, ProfileFields(cefr_level = "B1"), status = "blocked", lastError = ProfileBlock.CONFLICT))
        val plan = planProfileEdit("p1", ProfileFields(cefr_level = "B2"), ProfileFields(cefr_level = "B1"), 3, existing)
        plan as ProfileEditPlan.MergeInto
        assertFalse(plan.newPending)
    }

    @Test
    fun overlayDraftsAppliesInSeqOrder() {
        val ops = listOf(
            op(1, ProfileFields(cefr_level = "B1", selected_tenses = listOf("a"))),
            op(2, ProfileFields(cefr_level = "B2")),
        )
        val result = overlayDrafts(ops)
        assertEquals("B2", result.cefr_level)
        assertEquals(listOf("a"), result.selected_tenses)
    }

    @Test
    fun resolveBaseAlreadyAppliedWhenServerHasValues() {
        val payload = ProfileUpdatePayload(profileId = "p1", fields = ProfileFields(cefr_level = "B1"))
        assertEquals(BaseResolution.AlreadyApplied, resolveDraftBase(payload, server(cefr = "B1")))
    }

    @Test
    fun resolveBaseUsesRevisionWhenServerUntouchedSincePrev() {
        val payload = ProfileUpdatePayload(
            profileId = "p1",
            fields = ProfileFields(cefr_level = "B1"),
            prev = ProfileFields(cefr_level = "A2"),
        )
        assertEquals(BaseResolution.Use(3), resolveDraftBase(payload, server(cefr = "A2", revision = 3)))
    }

    @Test
    fun resolveBaseConflictWhenServerChangedOrNoSnapshot() {
        val withPrev = ProfileUpdatePayload(
            profileId = "p1",
            fields = ProfileFields(cefr_level = "B1"),
            prev = ProfileFields(cefr_level = "A1"),
        )
        assertEquals(BaseResolution.Conflict, resolveDraftBase(withPrev, server(cefr = "A2")))
        val noPrev = ProfileUpdatePayload(profileId = "p1", fields = ProfileFields(cefr_level = "B1"))
        assertEquals(BaseResolution.Conflict, resolveDraftBase(noPrev, server(cefr = "A2")))
    }

    @Test
    fun blockReasonMapsOnlyPermanentFailures() {
        assertEquals(ProfileBlock.CONFLICT, profileUpdateBlockReason(409, "profile_conflict"))
        assertEquals(ProfileBlock.NOT_FOUND, profileUpdateBlockReason(404, null))
        assertEquals(ProfileBlock.INVALID, profileUpdateBlockReason(422, "x"))
        assertNull(profileUpdateBlockReason(500, null))
        assertNull(profileUpdateBlockReason(429, null))
    }

    @Test
    fun applyMineOnlyAfterRevisionConflict() {
        assertTrue(ProfileBlock.canApplyMine(ProfileBlock.CONFLICT))
        assertFalse(ProfileBlock.canApplyMine(ProfileBlock.INVALID))
        assertFalse(ProfileBlock.canApplyMine(ProfileBlock.NOT_FOUND))
    }
}
