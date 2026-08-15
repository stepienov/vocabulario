package com.vocabulario.app.ui.card

import org.junit.Assert.assertEquals
import org.junit.Test

class ConjugationPersonGridTest {
    @Test
    fun indicativeSix_singularLeftPluralRight() {
        val persons = listOf("yo", "tú", "él", "nosotros", "vosotros", "ellos")
        val rows = conjugationPersonGridRows(persons, keyOf = { it })
        assertEquals(
            listOf(
                ConjugationGridRow("yo", "nosotros"),
                ConjugationGridRow("tú", "vosotros"),
                ConjugationGridRow("él", "ellos"),
            ),
            rows,
        )
    }

    @Test
    fun imperativeFive_singularLeftPluralRight() {
        val persons = listOf("tú", "usted", "nosotros", "vosotros", "ustedes")
        val rows = conjugationPersonGridRows(persons, keyOf = { it })
        assertEquals(
            listOf(
                ConjugationGridRow("tú", "nosotros"),
                ConjugationGridRow("usted", "vosotros"),
                ConjugationGridRow(null, "ustedes"),
            ),
            rows,
        )
    }

    @Test
    fun frenchSix_singularLeftPluralRight() {
        val persons = listOf("je", "tu", "il", "nous", "vous", "ils")
        val rows = conjugationPersonGridRows(persons, keyOf = { it })
        assertEquals(
            listOf(
                ConjugationGridRow("je", "nous"),
                ConjugationGridRow("tu", "vous"),
                ConjugationGridRow("il", "ils"),
            ),
            rows,
        )
    }

    @Test
    fun usesLabelsWhenKeysAmbiguous() {
        val persons = listOf("p1" to "yo", "p2" to "nosotros/as")
        val rows = conjugationPersonGridRows(
            persons,
            keyOf = { it.first },
            labelOf = { it.second },
        )
        assertEquals(
            listOf(ConjugationGridRow("p1" to "yo", "p2" to "nosotros/as")),
            rows,
        )
    }
}
