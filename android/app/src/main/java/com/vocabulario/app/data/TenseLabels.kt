package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang
import kotlinx.serialization.json.JsonObject

/**
 * Etykieta czasu wg profilu ([tense_label_lang] → app_lang lub learning_lang).
 *
 * Używa wyłącznie map językowych z karty (`tense_labels_app` / `tense_labels_l2`),
 * potem katalogu LanguagePacks dla wybranego języka. Nie miesza z legacy
 * `tense_labels` z LLM (często L1 albo mix), bo to dawało PL+ES w jednej belce.
 */
fun tenseLabelForProfile(
    profile: LanguageProfileResponse?,
    tenseKey: String,
    conjugation: JsonObject? = null,
): String {
    val learningLang = profile?.learning_lang ?: "en"
    val appLang = profile?.appLang ?: "en"
    val useLearningLang = profile?.tense_label_lang == "learning_lang"
    val labelLang = if (useLearningLang) learningLang else appLang
    val meta = conjugation?.get("ui_meta").asJsonObject()

    val tenseMapKey = if (useLearningLang) "tense_labels_l2" else "tense_labels_app"
    val nfMapKey = if (useLearningLang) "non_finite_labels_l2" else "non_finite_labels_app"

    meta?.get(tenseMapKey).asJsonObject()?.get(tenseKey).asJsonString()
        ?.takeIf { it.isNotBlank() }?.let { return it }
    meta?.get(nfMapKey).asJsonObject()?.get(tenseKey).asJsonString()
        ?.takeIf { it.isNotBlank() }?.let { return it }

    LanguagePacks.tenseLabel(labelLang, tenseKey)?.let { return it }

    // App-lang katalogi nie mają kluczy L2 (np. pl pack ≠ es tenses) — dopełnij L2.
    if (!useLearningLang) {
        LanguagePacks.tenseLabel(learningLang, tenseKey)?.let { return it }
    }

    return tenseKey.replace("_", " ")
}
