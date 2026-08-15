package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LanguagePacksTest {
    @Test
    fun defaultSelectedTenses_isSinglePresentLikeForm() {
        for ((code, _) in SUPPORTED_LEARNING_LANGS) {
            val selected = LanguagePacks.defaultSelectedTenses(code)
            assertEquals("$code should default to one tense", 1, selected.size)
            val key = selected.single()
            val catalog = LanguagePacks.tenseCatalog(code).map { it.key }
            assertTrue("$code default '$key' must be in catalog $catalog", key in catalog)
        }
    }
}
