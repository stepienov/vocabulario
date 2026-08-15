package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class TenseLabelsTest {
    private val profileLearning = LanguageProfileResponse(
        id = "1",
        app_lang = "pl",
        native_lang = "pl",
        learning_lang = "es",
        cefr_level = "A2",
        selected_tenses = emptyList(),
        tense_label_lang = "learning_lang",
        is_active = true,
    )

    private val profileApp = profileLearning.copy(tense_label_lang = "app_lang")

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
    fun learningLang_ignoresLegacyPolishMix() {
        val conjugation = meta(
            l2 = mapOf("futuro_simple" to "Futuro simple"),
            legacy = mapOf(
                "preterito_imperfecto" to "Czas przeszły niedokonany",
                "futuro_simple" to "Futuro simple",
            ),
        )
        // Missing in l2 → LanguagePacks.es, NOT legacy Polish
        assertEquals(
            "Imperfecto",
            tenseLabelForProfile(profileLearning, "preterito_imperfecto", conjugation),
        )
        assertEquals(
            "Futuro simple",
            tenseLabelForProfile(profileLearning, "futuro_simple", conjugation),
        )
    }

    @Test
    fun appLang_usesAppMapNotLegacy() {
        val conjugation = meta(
            app = mapOf("preterito_imperfecto" to "Czas przeszły niedokonany"),
            legacy = mapOf("preterito_imperfecto" to "Pretérito imperfecto"),
        )
        assertEquals(
            "Czas przeszły niedokonany",
            tenseLabelForProfile(profileApp, "preterito_imperfecto", conjugation),
        )
    }
}
