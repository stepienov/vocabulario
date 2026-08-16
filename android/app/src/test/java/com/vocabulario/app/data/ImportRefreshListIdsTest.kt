package com.vocabulario.app.data

import com.vocabulario.app.data.api.WordListResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImportRefreshListIdsTest {

    @Test
    fun includesRequestedAndSystemAndInbox() {
        val lists = listOf(
            WordListResponse(id = "sys-1", name = "Aprendiendo", is_system = true),
            WordListResponse(id = "inbox-1", name = "Oczekujące", is_system = false, is_pending_inbox = true),
            WordListResponse(id = "custom-1", name = "Verbos", is_system = false),
        )
        assertEquals(
            listOf("custom-1", "sys-1", "inbox-1"),
            importRefreshListIds("custom-1", lists),
        )
    }

    @Test
    fun skipsLocalIdsAndStillFetchesServerSystem() {
        val lists = listOf(
            WordListResponse(id = "sys-1", name = "Aprendiendo", is_system = true),
            WordListResponse(id = "local-pending-inbox-1", name = "Oczekujące", is_system = false, is_pending_inbox = true),
        )
        assertEquals(
            listOf("sys-1"),
            importRefreshListIds("local-system-learning", lists),
        )
    }

    @Test
    fun skipsRequestedIdNotOnThisProfile() {
        val lists = listOf(
            WordListResponse(id = "sys-1", name = "Aprendiendo", is_system = true),
        )
        assertEquals(
            listOf("sys-1"),
            importRefreshListIds("other-profile-list", lists),
        )
    }

    @Test
    fun doesNotDuplicateSystemWhenItIsTheTarget() {
        val lists = listOf(
            WordListResponse(id = "sys-1", name = "Aprendiendo", is_system = true),
        )
        assertEquals(listOf("sys-1"), importRefreshListIds("sys-1", lists))
    }

    @Test
    fun localOnlyHelper() {
        assertTrue(isLocalOnlyListId("local-system-learning"))
        assertTrue(isLocalOnlyListId("local:abc"))
        assertFalse(isLocalOnlyListId("sys-1"))
    }
}
