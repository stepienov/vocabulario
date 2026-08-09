package com.vocabulario.app.i18n

import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat

object AppLocale {
    fun normalize(languageTag: String): String {
        val tag = languageTag.trim().lowercase().ifBlank { "en" }
        return when (tag) {
            "zh", "zh-cn", "zh-hans" -> "zh-CN"
            "pt-br" -> "pt-BR"
            "pt-pt" -> "pt-PT"
            else -> tag
        }
    }

    fun currentTag(): String? {
        val locales = AppCompatDelegate.getApplicationLocales()
        if (locales.isEmpty) return null
        return locales[0]?.toLanguageTag()
    }

    /** Apply only when the tag actually changes (avoids unnecessary UI churn). */
    fun applyIfChanged(languageTag: String) {
        val normalized = normalize(languageTag)
        val current = currentTag()?.lowercase()
        val targetPrimary = normalized.substringBefore('-').lowercase()
        val currentPrimary = current?.substringBefore('-')
        if (currentPrimary == targetPrimary || current?.equals(normalized, ignoreCase = true) == true) {
            return
        }
        apply(normalized)
    }

    fun apply(languageTag: String) {
        val normalized = normalize(languageTag)
        AppCompatDelegate.setApplicationLocales(
            LocaleListCompat.forLanguageTags(normalized),
        )
    }
}
