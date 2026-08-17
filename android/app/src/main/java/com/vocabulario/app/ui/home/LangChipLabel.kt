package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.LanguageProfileResponse

fun langChipLabel(
    profile: LanguageProfileResponse?,
    all: List<LanguageProfileResponse>,
): String {
    val active = profile ?: return ""
    val iso = active.learning_lang.trim().uppercase()
    if (iso.isEmpty()) return ""
    val collisions = all.count { it.learning_lang.equals(active.learning_lang, ignoreCase = true) }
    return if (collisions > 1) {
        "${active.app_lang.trim().uppercase()}→$iso"
    } else {
        iso
    }
}
