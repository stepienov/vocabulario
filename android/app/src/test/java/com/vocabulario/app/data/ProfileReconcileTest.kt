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

    @Test
    fun langPairSwitchNeverMutatesExistingPair() {
        val plEs = profile("pl-es", active = true)
        assertEquals(LangPairSwitch.Keep, langPairSwitch(plEs, "pl-es"))
        assertEquals(LangPairSwitch.Activate("it-es"), langPairSwitch(profile("it-es", active = false), "pl-es"))
        assertEquals(LangPairSwitch.Create, langPairSwitch(null, "pl-es"))
    }

    @Test
    fun mergeKeepsLocalActiveOverServerFlag() {
        val local = profile("old", active = true, cefr = "B1", tenses = listOf("pres"))
        val remote = listOf(
            profile("old", active = false, cefr = "A1"),
            profile("live", active = true),
        )
        val merged = mergeRemoteProfiles(remote, local, "old")
        val kept = merged.single { it.is_active }
        assertEquals("old", kept.id)
        assertEquals("B1", kept.cefr_level)
        assertEquals(listOf("pres"), kept.selected_tenses)
        assertEquals(false, merged.first { it.id == "live" }.is_active)
    }

    @Test
    fun mergeFallsBackToServerActiveWhenLocalIdMissing() {
        val remote = listOf(profile("live", active = true), profile("other", active = false))
        val merged = mergeRemoteProfiles(remote, localActive = null, chosenId = "ghost")
        assertEquals("live", merged.single { it.is_active }.id)
    }

    @Test
    fun mergeEmptyRemoteReturnsEmpty() {
        assertEquals(emptyList<LanguageProfileResponse>(), mergeRemoteProfiles(emptyList(), null, "x"))
    }

    private fun profile(
        id: String,
        active: Boolean,
        cefr: String = "A2",
        tenses: List<String> = emptyList(),
    ) = LanguageProfileResponse(
        id = id,
        app_lang = "pl",
        learning_lang = "es",
        cefr_level = cefr,
        selected_tenses = tenses,
        is_active = active,
    )
}
