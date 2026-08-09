package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.api.tenseLabelSourceLang
import kotlinx.serialization.json.JsonObject

/** Etykieta czasu wg profilu (tense_label_lang → app_lang lub learning_lang). */
fun tenseLabelForProfile(
    profile: LanguageProfileResponse?,
    tenseKey: String,
    conjugation: JsonObject? = null,
): String {
    val learningLang = profile?.learning_lang ?: "en"
    val labelLang = profile?.tenseLabelSourceLang() ?: learningLang
    val meta = conjugation?.get("ui_meta").asJsonObject()
    val useAppLang = profile != null && labelLang.equals(profile.appLang, ignoreCase = true)
    val tenseMapKey = if (useAppLang) "tense_labels_app" else "tense_labels_l2"
    val nfMapKey = if (useAppLang) "non_finite_labels_app" else "non_finite_labels_l2"
    meta?.get(tenseMapKey).asJsonObject()?.get(tenseKey).asJsonString()
        ?.takeIf { it.isNotBlank() }?.let { return it }
    meta?.get(nfMapKey).asJsonObject()?.get(tenseKey).asJsonString()
        ?.takeIf { it.isNotBlank() }?.let { return it }
    meta?.get("tense_labels").asJsonObject()?.get(tenseKey).asJsonString()
        ?.takeIf { it.isNotBlank() }?.let { return it }
    meta?.get("non_finite_labels").asJsonObject()?.get(tenseKey).asJsonString()
        ?.takeIf { it.isNotBlank() }?.let { return it }
    return LanguagePacks.tenseLabel(labelLang, tenseKey)
        ?: LanguagePacks.tenseLabel(learningLang, tenseKey)
        ?: tenseKey.replace("_", " ")
}
