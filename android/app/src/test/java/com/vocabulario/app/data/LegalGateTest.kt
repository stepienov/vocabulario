package com.vocabulario.app.data

import com.vocabulario.app.data.api.LegalManifest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LegalGateTest {

    @Test
    fun acceptanceCarriesManifestVersionAndLocaleWithAdultStatement() {
        val body = acceptanceFor(LegalManifest(terms_version = "2026-06-01", locale = "pl"))
        assertEquals("2026-06-01", body.terms_version)
        assertEquals("pl", body.locale)
        assertTrue(body.adult_confirmed)
    }

    @Test
    fun publicSiteUrlDropsApiPrefix() {
        assertEquals("https://app.example/legal", publicSiteUrl("https://app.example/api/v1/", "/legal"))
        assertEquals("http://10.0.2.2:8000/privacy", publicSiteUrl("http://10.0.2.2:8000/api/v1/", "/privacy"))
    }
}
