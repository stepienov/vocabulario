package com.vocabulario.app.data.local

import kotlinx.serialization.json.add
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalAnswerCheckTest {

    private fun l2ToL1Content() = buildJsonObject {
        put("lemma", "alcanzar")
        put(
            "meanings",
            buildJsonArray {
                add(
                    buildJsonObject {
                        put("gloss_l1", "osiągnąć")
                        put(
                            "synonyms_l1",
                            buildJsonArray {
                                add("dosięgnąć")
                            },
                        )
                    },
                )
            },
        )
    }

    private fun conclusionContent() = buildJsonObject {
        put("lemma", "la conclusión")
        put("pos", "noun")
        put(
            "synonyms_l2",
            buildJsonArray {
                addJsonObject {
                    put("lemma", "resultado")
                    put("article", "el")
                    put("gloss_l1", "wynik")
                }
            },
        )
        put(
            "meanings",
            buildJsonArray {
                addJsonObject {
                    put("gloss_l1", "wniosek")
                }
            },
        )
    }

    @Test
    fun exactMainGlossIsNotSynonym() {
        val result = LocalAnswerCheck.check("osiągnąć", l2ToL1Content(), "l2_to_l1")
        assertTrue(result.correct)
        assertFalse(result.acceptedAsTypo)
        assertFalse(result.acceptedAsSynonym)
    }

    @Test
    fun exactSynonymIsNotTypo() {
        val result = LocalAnswerCheck.check("dosięgnąć", l2ToL1Content(), "l2_to_l1")
        assertTrue(result.correct)
        assertFalse(result.acceptedAsTypo)
        assertTrue(result.acceptedAsSynonym)
        assertEquals(null, result.expected)
    }

    @Test
    fun omittedNounArticleIsTypo() {
        val content = buildJsonObject { put("lemma", "la casa") }
        val result = LocalAnswerCheck.check("casa", content, "l1_to_l2")
        assertTrue(result.correct)
        assertTrue(result.acceptedAsTypo)
        assertFalse(result.acceptedAsSynonym)
        assertEquals("la casa", result.expected)
    }

    @Test
    fun synonymWithArticleIsExactSynonym() {
        val result = LocalAnswerCheck.check("el resultado", conclusionContent(), "l1_to_l2")
        assertTrue(result.correct)
        assertFalse(result.acceptedAsTypo)
        assertTrue(result.acceptedAsSynonym)
        val syn = LocalAnswerCheck.resolveSynonym(conclusionContent(), "l1_to_l2", "el resultado")
        assertEquals("el resultado", syn?.displayLemma)
        assertEquals("wynik", syn?.glossL1)
    }

    @Test
    fun synonymTypoFlagsBoth() {
        val result = LocalAnswerCheck.check("resultadp", conclusionContent(), "l1_to_l2")
        assertTrue(result.correct)
        assertTrue(result.acceptedAsTypo)
        assertTrue(result.acceptedAsSynonym)
        assertEquals("resultado", result.expected)
    }

    @Test
    fun extraArticleOnVerbIsError() {
        val content = buildJsonObject { put("lemma", "trabajar") }
        val result = LocalAnswerCheck.check("el trabajar", content, "l1_to_l2")
        assertFalse(result.correct)
        assertFalse(result.acceptedAsTypo)
        assertFalse(result.acceptedAsSynonym)
    }
}
