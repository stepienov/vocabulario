package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang
import kotlinx.serialization.json.JsonObject

data class TenseHeading(
    val original: String,
    val translation: String? = null,
)

/**
 * Nagłówek odmiany: nazwa w języku uczonym + tłumaczenie w języku aplikacji.
 * Nie zależy od starego [LanguageProfileResponse.tense_label_lang].
 */
fun tenseHeadingForProfile(
    profile: LanguageProfileResponse?,
    tenseKey: String,
    conjugation: JsonObject? = null,
): TenseHeading {
    val learningLang = profile?.learning_lang ?: "en"
    val appLang = profile?.appLang ?: "en"
    val meta = conjugation?.get("ui_meta").asJsonObject()

    val original = firstNonBlank(
        meta?.get("tense_labels_l2").asJsonObject()?.get(tenseKey).asJsonString(),
        meta?.get("non_finite_labels_l2").asJsonObject()?.get(tenseKey).asJsonString(),
        LanguagePacks.tenseLabel(learningLang, tenseKey),
        TenseUiLabels.label(learningLang, learningLang, tenseKey),
    ) ?: tenseKey.replace("_", " ")

    val translated = firstNonBlank(
        meta?.get("tense_labels_app").asJsonObject()?.get(tenseKey).asJsonString(),
        meta?.get("non_finite_labels_app").asJsonObject()?.get(tenseKey).asJsonString(),
        TenseUiLabels.label(learningLang, appLang, tenseKey),
    )
    val showTranslation = !translated.isNullOrBlank() &&
        !translated.equals(original, ignoreCase = true)
    return TenseHeading(original = original, translation = translated.takeIf { showTranslation })
}

/** Zostawione dla testów / miejsc, które chcą tylko nazwę L2. */
fun tenseLabelForProfile(
    profile: LanguageProfileResponse?,
    tenseKey: String,
    conjugation: JsonObject? = null,
): String = tenseHeadingForProfile(profile, tenseKey, conjugation).original

private fun firstNonBlank(vararg values: String?): String? =
    values.firstOrNull { !it.isNullOrBlank() }
