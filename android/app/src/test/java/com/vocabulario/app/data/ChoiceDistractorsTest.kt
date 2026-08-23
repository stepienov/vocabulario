package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class ChoiceDistractorsTest {

    private fun card(id: String, lemma: String, gloss: String, pos: String) =
        DistractorCard(id = id, lemmaL2 = lemma, glossPrimary = gloss, pos = pos)

    private fun similar(lemma: String, gloss: String, pos: String) =
        SimilarWordSeed(lemma = lemma, glossL1 = gloss, pos = pos)

    private val adjList = listOf(
        card("1", "limitado", "ograniczony", "adj"),
        card("2", "rápido", "szybki", "adj"),
        card("3", "lento", "wolny", "adj"),
        card("4", "alto", "wysoki", "adj"),
        card("5", "hablar", "mówić", "verb"),
        card("6", "el libro", "książka", "noun"),
        card("7", "comer", "jeść", "verb"),
        card("8", "bajo", "niski", "adj"),
        card("9", "fuerte", "silny", "adj"),
        card("10", "débil", "słaby", "adj"),
    )

    private val adjSimilar = listOf(
        similar("corto", "krótki", "adj"),
        similar("largo", "długi", "adj"),
        similar("oscuro", "ciemny", "adj"),
        similar("claro", "jasny", "adj"),
        similar("simple", "prosty", "adj"),
        similar("correr", "biegać", "verb"),
        similar("la mesa", "stół", "noun"),
    )

    private fun pick(
        correctId: String = "1",
        correctLemma: String = "limitado",
        correctGloss: String = "ograniczony",
        usedKeys: Set<String> = emptySet(),
        seed: Int = 1,
        list: List<DistractorCard> = adjList,
        similarWords: List<SimilarWordSeed> = adjSimilar,
        direction: String = "l1_to_l2",
    ) = pickChoiceDistractors(
        direction = direction,
        correctText = if (direction == "l2_to_l1") correctGloss else correctLemma,
        correctLemmaL2 = correctLemma,
        correctGloss = correctGloss,
        correctPos = "adjective",
        correctCardId = correctId,
        listCards = list,
        similar = similarWords,
        usedKeys = usedKeys,
        random = Random(seed),
    )

    @Test
    fun adjectivePrompt_allOptionsAreAdj() {
        val result = pick(direction = "l2_to_l1")
        assertEquals(8, result.options.size)
        assertTrue(result.options.all { normalizePosKey(it.pos) == "adj" })
        assertFalse(result.options.any { normalizePosKey(it.pos) == "verb" })
        assertFalse(result.options.any { normalizePosKey(it.pos) == "noun" })
    }

    @Test
    fun differentSeeds_pickDifferentListSubsets() {
        val a = pick(seed = 1)
        val b = pick(seed = 2)
        assertTrue(a.usedListKeys.isNotEmpty())
        assertTrue(a.usedListKeys.toSet() != b.usedListKeys.toSet() ||
            a.options.map { it.text } != b.options.map { it.text })
    }

    @Test
    fun usedKeys_avoidRepeatingTheSameListLemmas() {
        val first = pick(seed = 3)
        val second = pick(
            correctId = "2",
            correctLemma = "rápido",
            correctGloss = "szybki",
            usedKeys = first.usedListKeys.toSet(),
            seed = 3,
        )
        assertTrue(first.usedListKeys.none { it in second.usedListKeys })
        assertFalse(second.unusedPoolWasEmpty)
    }

    @Test
    fun similarWordsFill_whenListHasFewSamePos() {
        val result = pick(
            list = listOf(
                card("1", "limitado", "ograniczony", "adj"),
                card("5", "hablar", "mówić", "verb"),
            ),
            seed = 4,
        )
        val lemmas = result.options.map { it.lemma_l2 }
        assertTrue(lemmas.any { it in setOf("corto", "largo", "oscuro", "claro", "simple") })
        assertTrue(result.options.filter { !it.is_correct }.count { it.in_learning } <= 3)
    }

    @Test
    fun mixedPosNeverFillsShortage() {
        val result = pick(
            list = listOf(
                card("1", "limitado", "ograniczony", "adj"),
                card("5", "hablar", "mówić", "verb"),
                card("6", "el libro", "książka", "noun"),
            ),
            similarWords = listOf(similar("correr", "biegać", "verb")),
            seed = 5,
        )
        assertTrue(result.options.all { normalizePosKey(it.pos) == "adj" })
        assertTrue(result.options.none { it.lemma_l2 == "hablar" || it.lemma_l2 == "el libro" })
        assertTrue(result.options.none { it.text == "correr" })
    }
}
