package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TenseLabelsTest {
    private val profile = LanguageProfileResponse(
        id = "1",
        app_lang = "pl",
        native_lang = "pl",
        learning_lang = "es",
        cefr_level = "A2",
        selected_tenses = emptyList(),
        is_active = true,
    )

    private fun meta(
        app: Map<String, String> = emptyMap(),
        l2: Map<String, String> = emptyMap(),
        legacy: Map<String, String> = emptyMap(),
    ): JsonObject = buildJsonObject {
        putJsonObject("ui_meta") {
            if (app.isNotEmpty()) {
                putJsonObject("tense_labels_app") {
                    app.forEach { (k, v) -> put(k, v) }
                }
            }
            if (l2.isNotEmpty()) {
                putJsonObject("tense_labels_l2") {
                    l2.forEach { (k, v) -> put(k, v) }
                }
            }
            if (legacy.isNotEmpty()) {
                putJsonObject("tense_labels") {
                    legacy.forEach { (k, v) -> put(k, v) }
                }
            }
        }
    }

    @Test
    fun originalIsAlwaysL2_evenWhenAppMapHasPolish() {
        val conjugation = meta(
            app = mapOf("futuro_simple" to "Czas przyszły"),
            l2 = mapOf("futuro_simple" to "Futuro simple"),
            legacy = mapOf("futuro_simple" to "Czas przyszły"),
        )
        val heading = tenseHeadingForProfile(profile, "futuro_simple", conjugation)
        assertEquals("Futuro simple", heading.original)
        assertEquals("Czas przyszły", heading.translation)
    }

    @Test
    fun hidesTranslationWhenSameAsOriginal() {
        val conjugation = meta(
            app = mapOf("futuro_simple" to "Futuro simple"),
            l2 = mapOf("futuro_simple" to "Futuro simple"),
        )
        val heading = tenseHeadingForProfile(profile, "futuro_simple", conjugation)
        assertEquals("Futuro simple", heading.original)
        assertNull(heading.translation)
    }

    @Test
    fun ignoresLegacyMixForOriginal() {
        val conjugation = meta(
            legacy = mapOf("preterito_imperfecto" to "Czas przeszły niedokonany"),
        )
        assertEquals(
            "Imperfecto",
            tenseLabelForProfile(profile, "preterito_imperfecto", conjugation),
        )
    }
}
