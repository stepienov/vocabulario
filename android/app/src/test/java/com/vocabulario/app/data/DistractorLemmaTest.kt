package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DistractorLemmaTest {

    @Test
    fun l2ToL1_usesKnownLemmaNotDisplayedGloss() {
        assertEquals(
            "la correa",
            distractorLemmaL2("l2_to_l1", "la correa", "pasek"),
        )
    }

    @Test
    fun l2ToL1_withoutLemma_doesNotTreatGlossAsLemma() {
        assertNull(distractorLemmaL2("l2_to_l1", null, "pasek"))
        assertNull(distractorLemmaL2("l2_to_l1", "  ", "pasek"))
    }

    @Test
    fun l1ToL2_fallsBackToDisplayedLemma() {
        assertEquals("la tira", distractorLemmaL2("l1_to_l2", null, "la tira"))
        assertEquals(
            "la tira",
            distractorLemmaL2("l1_to_l2", "la tira", "la tira"),
        )
    }
}
