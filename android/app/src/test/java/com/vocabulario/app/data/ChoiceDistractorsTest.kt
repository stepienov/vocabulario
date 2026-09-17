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
        correctPos: String? = "adjective",
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
        correctPos = correctPos,
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

    private val phraseList = listOf(
        card("p1", "quedarse dormido", "zasnąć", "phrase"),
        card("p2", "tener sueño", "być sennym", "phrase"),
        card("p3", "tener que", "musieć", "phrase"),
        card("n1", "la autoridad", "władza", "noun"),
        card("n2", "el liderazgo", "przywództwo", "noun"),
        card("a1", "vulnerable", "bezbronny", "adj"),
        card("a2", "suelto", "luźny", "adj"),
        card("v1", "prevenir", "zapobiegać", "verb"),
        card("v2", "comportar", "pociągać za sobą", "verb"),
        card("v3", "hablar", "mówić", "verb"),
        card("v4", "comer", "jeść", "verb"),
        card("v5", "abrir", "otwierać", "verb"),
        card("v6", "cerrar", "zamykać", "verb"),
        card("v7", "vivir", "żyć", "verb"),
        card("v8", "escribir", "pisać", "verb"),
    )

    @Test
    fun phrasePrompt_excludesNounsAndAdjectives() {
        val result = pick(
            correctId = "p1",
            correctLemma = "quedarse dormido",
            correctGloss = "zasnąć",
            correctPos = "phrase",
            list = phraseList,
            similarWords = listOf(
                similar("percatarse", "zauważyć", "verb"),
                similar("quemarse", "spalić się", "verb"),
                similar("averiguar", "ustalić", "verb"),
                similar("cuidarse", "dbać", "verb"),
                similar("vulnerable", "bezbronny", "adj"),
                similar("la autoridad", "władza", "noun"),
                similar("el liderazgo", "przywództwo", "noun"),
            ),
            seed = 6,
        )
        assertEquals(8, result.options.size)
        val lemmas = result.options.map { it.lemma_l2 }.toSet()
        assertTrue("quedarse dormido" in lemmas)
        assertTrue(result.options.none { normalizePosKey(it.pos) == "noun" })
        assertTrue(result.options.none { normalizePosKey(it.pos) == "adj" })
        assertTrue(result.options.none {
            it.lemma_l2 in setOf("la autoridad", "el liderazgo", "vulnerable", "suelto")
        })
    }

    @Test
    fun phrasePrompt_prefersOtherPhrasesFromSimilar() {
        val result = pick(
            correctId = "p2",
            correctLemma = "tener sueño",
            correctGloss = "być sennym",
            correctPos = "phrase",
            list = phraseList,
            similarWords = listOf(
                similar("estar risueño", "być uśmiechniętym", "phrase"),
                similar("tener sospechas", "mieć podejrzenia", "phrase"),
                similar("tener en cuenta", "brać pod uwagę", "phrase"),
                similar("tener lugar", "odbywać się", "phrase"),
                similar("tener prisa", "spieszyć się", "phrase"),
                similar("tener sed", "być spragnionym", "phrase"),
                similar("tener suerte", "mieć szczęście", "phrase"),
                similar("suelto", "luźny", "adj"),
            ),
            seed = 7,
        )
        assertEquals(8, result.options.size)
        assertTrue(result.options.none { normalizePosKey(it.pos) == "adj" })
        assertTrue(result.options.none { normalizePosKey(it.pos) == "noun" })
        assertTrue(result.options.none { it.lemma_l2 == "suelto" })
        assertTrue(result.options.count { normalizePosKey(it.pos) == "phrase" } >= 3)
    }

    @Test
    fun similarWithoutPos_skippedWhenTargetPosKnown() {
        val result = pick(
            similarWords = listOf(
                similar("correr", "biegać", ""),
                similar("la mesa", "stół", ""),
                similar("corto", "krótki", "adj"),
            ),
            seed = 8,
        )
        assertTrue(result.options.all { normalizePosKey(it.pos) == "adj" })
        assertTrue(result.options.none { it.lemma_l2 == "correr" || it.lemma_l2 == "la mesa" })
        assertTrue(result.options.any { it.lemma_l2 == "corto" || it.is_correct })
    }

    @Test
    fun phrase_aloneOnAccount_fillsEightFromSimilar() {
        val similarPhrases = (1..12).map { i ->
            similar("at the other time $i", "en otro momento $i", "phrase")
        }
        val result = pick(
            correctId = "only",
            correctLemma = "at the same time",
            correctGloss = "a la vez",
            correctPos = "phrase",
            list = listOf(card("only", "at the same time", "a la vez", "phrase")),
            similarWords = similarPhrases,
            seed = 11,
        )
        assertEquals(8, result.options.size)
        assertTrue(result.options.all { normalizePosKey(it.pos) == "phrase" })
        assertEquals(1, result.options.count { it.is_correct })
    }

    @Test
    fun unknownPos_doesNotDumpTheWholeDeck() {
        val result = pick(
            correctId = "x",
            correctLemma = "xyz",
            correctGloss = "xyz",
            correctPos = null,
            list = phraseList,
            similarWords = listOf(similar("foo", "foo", "noun")),
            seed = 9,
        )
        val lemmas = result.options.map { it.lemma_l2 }.toSet()
        assertTrue(lemmas.none { it in setOf("la autoridad", "vulnerable", "hablar", "quedarse dormido") })
    }
}
