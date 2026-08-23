package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class TenseKeyNormalizeTest {
    @Test
    fun polishAliasesApplyOnlyForPolish() {
        assertEquals("czas_terazniejszy", normalizeTenseKey("present", "pl"))
        assertEquals("present", normalizeTenseKey("present", "ko"))
        assertEquals("present", normalizeTenseKey("present", "zh"))
        assertEquals("present", normalizeTenseKey("present"))
    }

    @Test
    fun spanishAliasesDoNotRewritePortugueseFuturo() {
        assertEquals("futuro_simple", normalizeTenseKey("futuro", "es"))
        assertEquals("futuro", normalizeTenseKey("futuro", "pt-br"))
        assertEquals("futuro", normalizeTenseKey("futuro", "pt-pt"))
    }

    @Test
    fun diacriticAliasesStayGlobal() {
        assertEquals("czas_terazniejszy", normalizeTenseKey("czas_teraźniejszy", "ko"))
        assertEquals("tryb_rozkazujacy", normalizeTenseKey("tryb_rozkazujący"))
    }
}
