package com.vocabulario.app.i18n

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.vocabulario.app.R
import java.util.Locale

fun languageDisplayName(code: String, inLang: String): String {
    val target = Locale.forLanguageTag(code.ifBlank { "und" })
    val inLocale = Locale.forLanguageTag(inLang.ifBlank { "en" })
    val name = target.getDisplayLanguage(inLocale).ifBlank { code }
    return name.replaceFirstChar { ch ->
        if (ch.isLowerCase()) ch.titlecase(inLocale) else ch.toString()
    }
}

fun lookupShowsReadingChips(readings: Collection<String?>): Boolean {
    val set = readings.mapNotNull { it?.takeIf(String::isNotBlank) }.toSet()
    return "learning" in set && "native" in set
}

@Composable
fun localizedLookupReadingLabel(
    reading: String?,
    typedAs: String?,
    appLang: String,
    learningLang: String,
): String? = when (reading) {
    "learning" -> stringResource(
        R.string.lookup_reading_learning,
        languageDisplayName(learningLang, appLang),
    )
    "native" -> stringResource(
        R.string.lookup_reading_native,
        languageDisplayName(appLang, appLang),
        typedAs.orEmpty(),
    )
    else -> null
}
