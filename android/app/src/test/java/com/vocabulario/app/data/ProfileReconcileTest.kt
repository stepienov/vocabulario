package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ProfileReconcileTest {

    @Test
    fun keepsStoredIdWhenItExistsOnServer() {
        val remote = listOf(profile("old", active = false), profile("live", active = true))
        assertEquals("old", resolveActiveProfile("old", remote)?.id)
    }

    @Test
    fun dropsGhostIdAndUsesServerActive() {
        val remote = listOf(profile("live", active = true), profile("other", active = false))
        assertEquals("live", resolveActiveProfile("ghost-3d722ec2", remote)?.id)
    }

    @Test
    fun emptyRemoteReturnsNull() {
        assertNull(resolveActiveProfile("any", emptyList()))
    }

    @Test
    fun overlayKeepsStoredUiLang() {
        val profile = profile("live", active = true)
        assertEquals("en", overlayAppLang(profile, "en").app_lang)
        assertEquals("pl", overlayAppLang(profile, "pl").app_lang)
        assertEquals("pl", overlayAppLang(profile, "").app_lang)
    }

    @Test
    fun findsLangPairIgnoringCase() {
        val remote = listOf(profile("live", active = true))
        assertEquals("live", findLangPair(remote, "PL", "ES")?.id)
        assertNull(findLangPair(remote, "en", "es"))
    }

    private fun profile(id: String, active: Boolean) = LanguageProfileResponse(
        id = id,
        app_lang = "pl",
        learning_lang = "es",
        cefr_level = "A2",
        selected_tenses = emptyList(),
        is_active = active,
    )
}
