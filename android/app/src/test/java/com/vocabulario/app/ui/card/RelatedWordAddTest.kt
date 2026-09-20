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
        assertEquals(null, candidate.source_card_id)
    }

    @Test
    fun relatedWordKeepsSourceCardId() {
        val candidate = relatedWordToCandidate(
            RelatedWord(lemma = "intermitencia", glossL1 = "x", pos = "noun", article = "la"),
            sourceCardId = "card-1",
        )
        assertEquals("la intermitencia", candidate.lemma)
        assertEquals("card-1", candidate.source_card_id)
    }

    @Test
    fun relatedNounJoinsArticleIntoCandidateLemma() {
        val candidate = relatedWordToCandidate(
            RelatedWord(lemma = "alcance", glossL1 = "zasięg", pos = "noun", article = "el"),
        )
        assertEquals("el alcance", candidate.lemma)
    }

    @Test
    fun associationAddOmitsSourceCardId() {
        val word = RelatedWord(
            lemma = "volante",
            glossL1 = "kierownica",
            pos = "noun",
            article = "el",
            joinWordFamily = false,
        )
        val candidate = relatedWordToCandidate(
            word,
            sourceCardId = if (word.joinWordFamily) "card-1" else null,
        )
        assertEquals(null, candidate.source_card_id)
    }

    @Test
    fun familyAddKeepsSourceCardId() {
        val word = RelatedWord(
            lemma = "avance",
            glossL1 = "x",
            pos = "noun",
            article = "el",
            joinWordFamily = true,
        )
        val candidate = relatedWordToCandidate(
            word,
            sourceCardId = if (word.joinWordFamily) "card-1" else null,
        )
        assertEquals("card-1", candidate.source_card_id)
    }
}
