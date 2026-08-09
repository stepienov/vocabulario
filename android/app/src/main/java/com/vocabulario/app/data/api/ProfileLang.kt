package com.vocabulario.app.data.api

import kotlinx.serialization.json.JsonNames

/** Język aplikacji (UI + glossy L1). */
val LanguageProfileResponse.appLang: String
    get() = app_lang.ifBlank { native_lang.orEmpty() }.ifBlank { "en" }

/** Skąd brać etykiety czasów: app_lang (domyślnie) lub learning_lang. */
fun LanguageProfileResponse.tenseLabelSourceLang(): String =
    if (tense_label_lang == "learning_lang") learning_lang else appLang
