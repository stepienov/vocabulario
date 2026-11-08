package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CardMembershipTest {

    @Test
    fun pradoMatchesCardWithArticle() {
        val card = row("el prado", "noun")
        assertEquals("el prado", selectLiveCardForLemma(listOf(card), "prado", "noun")?.lemmaL2)
    }

    @Test
    fun articleQueryMatchesBareCard() {
        val card = row("prado", "noun")
        assertEquals("prado", selectLiveCardForLemma(listOf(card), "el prado", "noun")?.lemmaL2)
    }

    @Test
    fun parentheticalLemmaMatchesArticleCard() {
        val card = row("el castillo", "noun")
        assertEquals(
            "el castillo",
            selectLiveCardForLemma(listOf(card), "castillo (fortaleza)", "noun")?.lemmaL2,
        )
    }

    @Test
    fun apostrophePrefixMatchesBareLemma() {
        val card = row("eau", "noun")
        assertEquals("eau", selectLiveCardForLemma(listOf(card), "l'eau", "noun")?.lemmaL2)
    }

    @Test
    fun missingPosDoesNotMatchANoun() {
        assertNull(selectLiveCardForLemma(listOf(row("el prado", "noun")), "prado", null))
        assertNull(selectLiveCardForLemma(listOf(row("prado", null)), "prado", "noun"))
    }

    @Test
    fun bothWithoutPosMatch() {
        val card = row("prado", null)
        assertEquals("prado", selectLiveCardForLemma(listOf(card), "prado", null)?.lemmaL2)
    }

    @Test
    fun verbDoesNotMatchNoun() {
        val card = row("play", "noun")
        assertNull(selectLiveCardForLemma(listOf(card), "play", "verb"))
    }

    @Test
    fun longerCanonicalLemmaWins() {
        val cards = listOf(row("prado", "noun", "short"), row("el prado", "noun", "long"))
        assertEquals("long", selectLiveCardForLemma(cards, "los prado", "noun")?.id)
    }

    @Test
    fun germanSharpSMatchesCasefold() {
        val card = row("STRASSE", "noun")
        assertEquals("STRASSE", selectLiveCardForLemma(listOf(card), "Straße", "noun")?.lemmaL2)
    }

    @Test
    fun posBucketsMatchTheSharedLabels() {
        assertEquals("noun", normalizePosKey("noun"))
        assertEquals("noun", normalizePosKey("rzeczownik"))
        assertEquals("noun", normalizePosKey("sustantivo masculino"))
        assertEquals("verb", normalizePosKey("verbo"))
        assertEquals("adj", normalizePosKey("adj"))
        assertEquals("phrase", normalizePosKey("phrase"))
        assertEquals("phrase", normalizePosKey("wyrażenie"))
        assertEquals("unknown", normalizePosKey(""))
        assertEquals("unknown", normalizePosKey(null))
    }

    private fun row(lemma: String, pos: String?, id: String = lemma) = CardMembershipRow(
        id = id,
        lemmaL2 = lemma,
        pos = pos,
        deckId = null,
        enrichmentStatus = "ready",
    )
}
