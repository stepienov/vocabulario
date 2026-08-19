package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.LanguageProfileResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LangChipLabelTest {

    @Test
    fun newUserWithEmptyProfilesHasNoDropdown() {
        val es = profile("es-id", learning = "es")
        val en = profile("en-id", learning = "en")
        val counts = mapOf("es-id" to 0, "en-id" to 0)
        assertFalse(hasOtherLearningLanguage(listOf(es, en), counts, "es-id"))
        assertEquals(listOf(es), dropdownLearningProfiles(listOf(es, en), counts, "es-id"))
    }

    @Test
    fun dropdownOnlyWhenOtherLanguageHasCards() {
        val es = profile("es-id", learning = "es")
        val it = profile("it-id", learning = "it")
        val counts = mapOf("es-id" to 3, "it-id" to 1)
        assertTrue(hasOtherLearningLanguage(listOf(es, it), counts, "es-id"))
        assertEquals(listOf(es, it), dropdownLearningProfiles(listOf(es, it), counts, "es-id"))
    }

    @Test
    fun emptyGhostProfileStaysHidden() {
        val es = profile("es-id", learning = "es")
        val en = profile("en-id", learning = "en")
        val counts = mapOf("es-id" to 4, "en-id" to 0)
        assertFalse(hasOtherLearningLanguage(listOf(es, en), counts, "es-id"))
        assertEquals(listOf(es), dropdownLearningProfiles(listOf(es, en), counts, "es-id"))
    }

    @Test
    fun collisionUsesAppLangPrefix() {
        val plEs = profile("a", app = "pl", learning = "es")
        val enEs = profile("b", app = "en", learning = "es")
        assertEquals("PL→ES", langChipLabel(plEs, listOf(plEs, enEs)))
        assertEquals("EN→ES", langChipLabel(enEs, listOf(plEs, enEs)))
    }

    private fun profile(
        id: String,
        app: String = "en",
        learning: String,
    ) = LanguageProfileResponse(
        id = id,
        app_lang = app,
        learning_lang = learning,
        cefr_level = "A2",
        selected_tenses = emptyList(),
        is_active = false,
    )
}
