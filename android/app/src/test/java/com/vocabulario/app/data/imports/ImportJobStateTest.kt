package com.vocabulario.app.data.imports

import com.vocabulario.app.data.api.ImportJobItemResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImportJobStateTest {

    @Test
    fun busy_only_in_flight_statuses() {
        assertFalse(ImportJobState(status = ImportStatus.Idle).busy)
        assertTrue(ImportJobState(status = ImportStatus.Queued).busy)
        assertTrue(ImportJobState(status = ImportStatus.Analyzing).busy)
        assertFalse(ImportJobState(status = ImportStatus.Review).busy)
        assertTrue(ImportJobState(status = ImportStatus.Committing).busy)
        assertTrue(ImportJobState(status = ImportStatus.Cancelling).busy)
        assertFalse(ImportJobState(status = ImportStatus.Done).busy)
        assertFalse(ImportJobState(status = ImportStatus.Error).busy)
    }

    @Test
    fun blocksUi_only_while_job_in_progress() {
        assertFalse(ImportJobState(status = ImportStatus.Idle).blocksUi)
        assertTrue(ImportJobState(status = ImportStatus.Review).blocksUi)
        assertTrue(ImportJobState(status = ImportStatus.Analyzing).blocksUi)
        assertFalse(ImportJobState(status = ImportStatus.Done).blocksUi)
        assertFalse(ImportJobState(status = ImportStatus.Cancelled).blocksUi)
        assertTrue(ImportJobState(status = ImportStatus.Done).showOutcome)
        assertTrue(ImportJobState(status = ImportStatus.Cancelled).showOutcome)
    }

    @Test
    fun errorClipboard_joins_failed_lemmas() {
        val state = ImportJobState(
            items = listOf(
                item(0, "ready", "casa", "casa | dom"),
                item(2, "failed", "gamma", "g"),
                item(1, "failed", null, "alpha"),
                item(3, "failed", "delta", "d"),
            ),
        )
        assertEquals("alpha; gamma; delta", state.errorClipboard)
    }

    @Test
    fun readyItems_sort_ignores_spanish_articles() {
        val state = ImportJobState(
            items = listOf(
                item(0, "ready", "el resultado", "el resultado"),
                item(1, "ready", "la fábrica", "la fábrica"),
                item(2, "ready", "el medio ambiente", "el medio ambiente"),
                item(3, "ready", "la asignatura", "la asignatura"),
            ),
        )
        assertEquals(
            listOf("la asignatura", "la fábrica", "el medio ambiente", "el resultado"),
            state.readyItems.map { it.lemma },
        )
    }

    @Test
    fun normalizeImportSourceName_maps_legacy_polish() {
        assertEquals("paste", normalizeImportSourceName("Wklejka"))
        assertEquals("paste", normalizeImportSourceName("paste"))
        assertEquals("lista.csv", normalizeImportSourceName("lista.csv"))
    }

    @Test
    fun parseImportStatus_maps_backend() {
        assertEquals(ImportStatus.Analyzing, parseImportStatus("analyzing"))
        assertEquals(ImportStatus.Review, parseImportStatus("review"))
        assertEquals(ImportStatus.Cancelled, parseImportStatus("cancelled"))
    }

    @Test
    fun item_parses_when_display_is_not_a_card_tree() {
        val json = kotlinx.serialization.json.Json {
            ignoreUnknownKeys = true
            coerceInputValues = true
            isLenient = true
        }
        val raw = """
            {"id":"a","ordinal":0,"input_label":"casa","verdict":"ready",
             "lemma":"casa","gloss":"house","display":[]}
        """.trimIndent()
        val item = json.decodeFromString(ImportJobItemResponse.serializer(), raw)
        assertEquals("casa", item.lemma)
        assertEquals("house", item.gloss)
        assertEquals("ready", item.verdict)
    }

    private fun item(
        ordinal: Int,
        verdict: String,
        lemma: String?,
        input: String,
    ) = ImportJobItemResponse(
        id = "id-$ordinal",
        ordinal = ordinal,
        input_label = input,
        verdict = verdict,
        lemma = lemma,
    )
}
