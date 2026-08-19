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

/** Inny język nauki z ≥1 kartą — tylko wtedy Home pokazuje dropdown. */
fun hasOtherLearningLanguage(
    profiles: List<LanguageProfileResponse>,
    cardCounts: Map<String, Int>,
    activeId: String?,
): Boolean = profiles.any { it.id != activeId && (cardCounts[it.id] ?: 0) > 0 }

fun dropdownLearningProfiles(
    profiles: List<LanguageProfileResponse>,
    cardCounts: Map<String, Int>,
    activeId: String?,
): List<LanguageProfileResponse> {
    if (!hasOtherLearningLanguage(profiles, cardCounts, activeId)) {
        return profiles.filter { it.id == activeId }
    }
    return profiles.filter { it.id == activeId || (cardCounts[it.id] ?: 0) > 0 }
}
