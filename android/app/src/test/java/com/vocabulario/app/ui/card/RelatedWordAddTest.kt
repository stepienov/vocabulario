package com.vocabulario.app.ui.card

import com.vocabulario.app.ui.home.relatedWordToCandidate
import org.junit.Assert.assertEquals
import org.junit.Test

class RelatedWordAddTest {

    @Test
    fun relatedWordMapsToLookupCandidate() {
        val candidate = relatedWordToCandidate(
            RelatedWord(lemma = "la tira", glossL1 = "pasek, taśma", pos = "noun"),
        )
        assertEquals("la tira", candidate.lemma)
        assertEquals("pasek, taśma", candidate.gloss)
        assertEquals("noun", candidate.pos)
        assertEquals(false, candidate.onList)
    }
}
