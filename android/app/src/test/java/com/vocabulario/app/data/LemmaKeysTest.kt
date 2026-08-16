package com.vocabulario.app.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LemmaKeysTest {

    @Test
    fun containsLemma_matchesArticleVariants() {
        val lemmas = lemmaKeys("el banco")
        assertTrue(lemmas.containsLemma("banco"))
        assertTrue(lemmas.containsLemma("el banco"))
        assertTrue(lemmas.containsLemma("El Banco"))
        assertFalse(lemmas.containsLemma("banca"))
        assertFalse(lemmas.containsLemma(null))
        assertFalse(lemmas.containsLemma("  "))
    }

    @Test
    fun containsLemma_matchesBareLemmaAgainstArticledCard() {
        val lemmas = lemmaKeys("banco")
        assertTrue(lemmas.containsLemma("el banco"))
        assertTrue(lemmas.containsLemma("la banco"))
    }
}
