package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class RepairDisplayTextTest {

    @Test
    fun repairsPolishTypographicQuotes() {
        val raw = "S\u0142owo \u00d4\u00c7\u00d7casa\u00d4\u00c7\u0141 ko\u0144czy si\u0119 na a."
        assertEquals("S\u0142owo \u201ecasa\u201d ko\u0144czy si\u0119 na a.", repairDisplayText(raw))
    }

    @Test
    fun leavesCleanTextAlone() {
        val clean = "La palabra \u00abcasa\u00bb termina en a."
        assertEquals(clean, repairDisplayText(clean))
    }
}
