package com.vocabulario.app.i18n

import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalConfiguration
import com.vocabulario.app.data.posLabel

/** Part-of-speech label in the active app UI language (never hardcodes Polish). */
@Composable
fun localizedPosLabel(pos: String?): String {
    val lang = LocalConfiguration.current.locales[0]?.language ?: "en"
    return posLabel(pos, lang)
}
