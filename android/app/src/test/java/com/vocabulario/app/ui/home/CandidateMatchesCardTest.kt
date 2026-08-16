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
