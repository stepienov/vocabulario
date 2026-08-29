package com.vocabulario.app.data.local

import kotlinx.serialization.json.add
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
}
