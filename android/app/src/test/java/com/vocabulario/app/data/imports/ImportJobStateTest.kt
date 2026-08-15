package com.vocabulario.app.data.imports

import com.vocabulario.app.data.api.ImportDisplayCard
import com.vocabulario.app.data.api.ImportDisplayPayload
import com.vocabulario.app.data.api.ImportValidWord
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImportJobStateTest {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    @Test
    fun busy_only_processing_and_committing() {
        assertFalse(ImportJobState(status = ImportStatus.Idle).busy)
        assertTrue(ImportJobState(status = ImportStatus.Processing).busy)
        assertFalse(ImportJobState(status = ImportStatus.Review).busy)
        assertTrue(ImportJobState(status = ImportStatus.Committing).busy)
        assertFalse(ImportJobState(status = ImportStatus.Done).busy)
        assertFalse(ImportJobState(status = ImportStatus.Error).busy)
    }

    @Test
    fun selectedCount_respects_deselected_keys_vocab() {
        val state = ImportJobState(
            mode = "vocabulario",
            valid = listOf(
                ImportValidWord(input = "a", lemma = "a"),
                ImportValidWord(input = "b", lemma = "b"),
                ImportValidWord(input = "c", lemma = "c"),
            ),
            deselectedKeys = setOf("b"),
        )
        assertEquals(2, state.selectedCount)
        assertEquals(listOf("a", "c"), state.selectedValid.map { it.input })
    }

    @Test
    fun selectedCount_respects_deselected_keys_preserve() {
        val cards = listOf(
            displayCard("1", "uno"),
            displayCard("2", "dos"),
        )
        val state = ImportJobState(
            mode = "preserve",
            displayCards = cards,
            deselectedKeys = setOf("1"),
        )
        assertEquals(1, state.selectedCount)
        assertEquals(listOf("2"), state.selectedDisplayCards.map { it.key })
    }

    @Test
    fun toggle_semantics_via_deselected_set() {
        var state = ImportJobState(
            status = ImportStatus.Review,
            valid = listOf(ImportValidWord(input = "hola", lemma = "hola")),
        )
        state = state.copy(deselectedKeys = state.deselectedKeys + "hola")
        assertEquals(0, state.selectedCount)
        state = state.copy(deselectedKeys = state.deselectedKeys - "hola")
        assertEquals(1, state.selectedCount)
    }

    @Test
    fun snapshot_roundtrip_preserves_review_fields() {
        val original = ImportJobState(
            status = ImportStatus.Review,
            sourceName = "quizlet1.txt",
            mode = "vocabulario",
            targetListId = "list-1",
            targetListName = "Uczę się",
            valid = listOf(
                ImportValidWord(
                    input = "casa",
                    lemma = "casa",
                    gloss = "house",
                    entry_kind = "lemma",
                ),
            ),
            invalid = listOf("???"),
            deselectedKeys = setOf("casa"),
            total = 1,
            showAbortConfirm = true,
        )
        val encoded = json.encodeToString(original)
        val decoded = json.decodeFromString<ImportJobState>(encoded)
            .copy(showAbortConfirm = false)
        assertEquals(ImportStatus.Review, decoded.status)
        assertEquals("quizlet1.txt", decoded.sourceName)
        assertEquals("list-1", decoded.targetListId)
        assertEquals(1, decoded.valid.size)
        assertEquals(setOf("casa"), decoded.deselectedKeys)
        assertFalse(decoded.showAbortConfirm)
    }

    @Test
    fun committing_snapshot_roundtrip() {
        val original = ImportJobState(
            status = ImportStatus.Committing,
            mode = "vocabulario",
            targetListId = "x",
            processed = 3,
            total = 10,
            valid = listOf(
                ImportValidWord(input = "a", lemma = "a"),
                ImportValidWord(input = "b", lemma = "b"),
            ),
        )
        val decoded = json.decodeFromString<ImportJobState>(json.encodeToString(original))
        assertEquals(ImportStatus.Committing, decoded.status)
        assertEquals(3, decoded.processed)
        assertEquals(10, decoded.total)
    }

    private fun displayCard(key: String, lemma: String) = ImportDisplayCard(
        key = key,
        lemma_l2 = lemma,
        display = ImportDisplayPayload(),
    )
}
