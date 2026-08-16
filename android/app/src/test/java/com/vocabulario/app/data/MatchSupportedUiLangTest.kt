package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MatchSupportedUiLangTest {
    @Test
    fun matchesSupportedPrimaryLanguage() {
        assertEquals("pl", matchSupportedUiLang("pl"))
        assertEquals("en", matchSupportedUiLang("en", "US"))
        assertEquals("ja", matchSupportedUiLang("ja", "JP"))
    }

    @Test
    fun mapsPortugueseVariants() {
        assertEquals("pt-br", matchSupportedUiLang("pt", "BR"))
        assertEquals("pt-pt", matchSupportedUiLang("pt", "PT"))
        assertEquals("pt-br", matchSupportedUiLang("pt"))
    }

    @Test
    fun mapsChineseAndFallsBackToEnglishCaller() {
        assertEquals("zh", matchSupportedUiLang("zh", "CN"))
        assertNull(matchSupportedUiLang("xx"))
        assertEquals("en", matchSupportedUiLang("xx") ?: "en")
    }

    @Test
    fun languageDropdownsAreAlphabeticalByLabel() {
        val labels = SUPPORTED_UI_LANGS.map { it.second }
        val sorted = labels.sortedWith(java.text.Collator.getInstance(java.util.Locale.ROOT))
        assertEquals(sorted, labels)
        assertEquals("Polski", SUPPORTED_UI_LANGS.first { it.first == "pl" }.second)
        assertEquals("pl", SUPPORTED_LEARNING_LANGS.first { it.second == "Polski" }.first)
    }
}
