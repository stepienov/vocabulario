package com.vocabulario.app.ui.card

import com.vocabulario.app.data.LanguagePacks
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class OrderedPersonsTest {
    @Test
    fun spanishImperative_ustedBeforePlurals_evenWhenPersonOrderIsIndicative() {
        val conjugation = buildJsonObject {
            putJsonObject("ui_meta") {
                put("person_order", jsonStrings("yo", "tú", "él", "nosotros", "vosotros", "ellos"))
                putJsonObject("person_labels") {
                    put("tú", "tú")
                    put("nosotros", "nosotros/as")
                    put("vosotros", "vosotros/as")
                    put("usted", "usted")
                    put("ustedes", "ustedes")
                }
            }
        }
        val forms = buildJsonObject {
            put("tú", "acércate")
            put("nosotros", "acerquémonos")
            put("vosotros", "acercaos")
            put("usted", "acérquese")
            put("ustedes", "acérquense")
        }

        val rows = orderedPersons(forms, conjugation, "es", "imperativo_afirmativo")
        assertEquals(
            listOf("tú", "usted", "nosotros/as", "vosotros/as", "ustedes"),
            rows.map { it.first },
        )
    }

    @Test
    fun spanishPresent_keepsSixPersonSingularThenPlural() {
        val conjugation = buildJsonObject {
            putJsonObject("ui_meta") {
                put("person_order", jsonStrings("yo", "tú", "él", "nosotros", "vosotros", "ellos"))
            }
        }
        val forms = buildJsonObject {
            put("yo", "me acerco")
            put("tú", "te acercas")
            put("él", "se acerca")
            put("nosotros", "nos acercamos")
            put("vosotros", "os acercáis")
            put("ellos", "se acercan")
        }
        val rows = orderedPersons(forms, conjugation, "es", "presente")
        assertEquals(
            listOf("yo", "tú", "él", "nosotros", "vosotros", "ellos"),
            rows.map { it.first },
        )
    }

    @Test
    fun esImperativeGrid_isSingularThenPlural() {
        assertEquals(
            listOf("tú", "usted", "nosotros", "vosotros", "ustedes"),
            LanguagePacks.personKeysForTense("es", "imperativo_afirmativo"),
        )
        assertEquals(
            LanguagePacks.personKeysForTense("es", "imperativo_afirmativo"),
            LanguagePacks.personKeysForTense("es", "imperativo_negativo"),
        )
    }

    private fun jsonStrings(vararg values: String) =
        JsonArray(values.map { JsonPrimitive(it) })
}
