package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.LookupCandidate
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CandidateMatchesCardTest {

    @Test
    fun sameLemmaDifferentPos_doesNotMatch() {
        val verb = candidate(pos = "verb", entry = "lex-verb")
        val nounCard = card(pos = "noun", entry = "lex-noun")
        assertFalse(candidateMatchesCard(verb, nounCard))
    }

    @Test
    fun sameLemmaSamePos_matches() {
        val verb = candidate(pos = "verb", entry = null)
        val verbCard = card(pos = "verb", entry = null)
        assertTrue(candidateMatchesCard(verb, verbCard))
    }

    @Test
    fun lexicalEntryDoesNotOverrideDifferentPos() {
        val noun = candidate(pos = "noun", entry = "lex-verb")
        val verbCard = card(pos = "verb", entry = "lex-verb")
        assertFalse(candidateMatchesCard(noun, verbCard))
    }

    @Test
    fun pendingIdsAreDistinctPerPos() {
        assertEquals("pending-play-verb", pendingCardId("play", "verb"))
        assertEquals("pending-play-noun", pendingCardId("play", "noun"))
        assertFalse(pendingCardId("play", "verb") == pendingCardId("play", "noun"))
    }

    @Test
    fun sameLemmaAndPos_rejectsHomographs() {
        assertTrue(sameLemmaAndPos("play", "verb", "Play", "verb"))
        assertFalse(sameLemmaAndPos("play", "verb", "play", "noun"))
    }

    @Test
    fun sameLemmaAndPos_allowsUnknownPosMatch() {
        assertTrue(sameLemmaAndPos("casa", null, "casa", "noun"))
        assertTrue(sameLemmaAndPos("casa", "noun", "casa", null))
    }

    @Test
    fun candidateMatchesCard_doesNotTreatMissingPosAsNoun() {
        val bare = LookupCandidate(lemma = "play", pos = null, gloss = "gra")
        assertFalse(candidateMatchesCard(bare, card(pos = "noun", entry = null)))
        val noun = LookupCandidate(lemma = "play", pos = "noun", gloss = "gra")
        assertFalse(candidateMatchesCard(noun, card(pos = null, entry = null)))
    }

    @Test
    fun candidateMatchesCard_byLearningCardId() {
        val candidate = LookupCandidate(
            lemma = "casa",
            pos = null,
            gloss = "dom",
            learning_card_id = "card-42",
        )
        val card = CardResponse(
            id = "card-42",
            lemma_l2 = "casa",
            pos = "noun",
            gloss_primary = "dom",
            content = buildJsonObject { },
            created_at = "",
            enrichment_status = "ready",
        )
        assertTrue(candidateMatchesCard(candidate, card))
    }

    @Test
    fun mergeLookupCandidates_keepsCurrentAndAppendsNew() {
        val cached = listOf(candidate(pos = "verb", entry = null))
        val expanded = listOf(
            candidate(pos = "verb", entry = "lex-verb"),
            candidate(pos = "noun", entry = null).copy(gloss = "sztuka"),
        )
        val merged = mergeLookupCandidates(cached, expanded)
        assertEquals(2, merged.size)
        assertEquals("verb", merged[0].pos)
        assertEquals("noun", merged[1].pos)
        assertEquals("sztuka", merged[1].gloss)
    }

    @Test
    fun mergeLookupCandidates_appendsNewAndDropsRowsTheServerRemoved() {
        val current = listOf(
            candidate(pos = "verb", entry = null),
            candidate(pos = "noun", entry = null).copy(lemma = "la droga", gloss = "droga"),
        )
        val incoming = listOf(
            candidate(pos = "noun", entry = null).copy(lemma = "el camino", gloss = "droga"),
            candidate(pos = "verb", entry = "lex-verb"),
        )
        val merged = mergeLookupCandidates(current, incoming)
        assertEquals(listOf("play", "el camino"), merged.map { it.lemma })
        assertEquals("lex-verb", merged[0].lexical_entry_id)
    }

    @Test
    fun mergeLookupCandidates_preservesOnListMembership() {
        val current = listOf(
            candidate(pos = "verb", entry = null).copy(
                list_name = "Uczę się",
                learning_card_id = "card-1",
                enrichment_status = "pending",
            ),
        )
        val incoming = listOf(candidate(pos = "verb", entry = "lex-verb"))
        val merged = mergeLookupCandidates(current, incoming)
        assertEquals(1, merged.size)
        assertEquals("Uczę się", merged[0].list_name)
        assertEquals("card-1", merged[0].learning_card_id)
        assertEquals("pending", merged[0].enrichment_status)
        assertEquals("lex-verb", merged[0].lexical_entry_id)
    }

    private fun candidate(pos: String?, entry: String?) = LookupCandidate(
        lemma = "play",
        pos = pos,
        gloss = "grać",
        lexical_entry_id = entry,
    )

    private fun card(pos: String?, entry: String?) = CardResponse(
        id = "c1",
        lemma_l2 = "play",
        pos = pos,
        gloss_primary = "grać",
        content = buildJsonObject { },
        lexical_entry_id = entry,
        created_at = "",
        enrichment_status = "pending",
    )
}
