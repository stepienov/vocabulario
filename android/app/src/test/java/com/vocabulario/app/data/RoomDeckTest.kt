package com.vocabulario.app.data

import com.vocabulario.app.data.api.WordListResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RoomDeckTest {

    private val system = WordListResponse(id = "sys-uuid", name = "Uczę się", is_system = true)
    private val custom = WordListResponse(id = "custom-1", name = "Verbos", is_system = false)
    private val lists = listOf(system, custom)

    @Test
    fun systemListDeckIdIsAlwaysNull() {
        assertTrue(isSystemListForRoom("sys-uuid", lists))
        assertNull(roomDeckIdForList("sys-uuid", isSystem = true))
    }

    @Test
    fun oldElvisWouldHaveStoredTheSystemUuid() {
        val listId = "sys-uuid"
        val broken = lists.find { it.id == listId && it.is_system }?.let { null }
            ?: listId.takeUnless { it.startsWith("local-") }
        assertEquals(
            "regresja: Elvis po let { null } zapisuje UUID listy systemowej",
            listId,
            broken,
        )
        assertNull(roomDeckIdForList(listId, isSystem = isSystemListForRoom(listId, lists)))
    }

    @Test
    fun customListKeepsItsId() {
        assertFalse(isSystemListForRoom("custom-1", lists))
        assertEquals("custom-1", roomDeckIdForList("custom-1", isSystem = false))
    }

    @Test
    fun localSystemPlaceholderIsSystemEvenWithoutCachedLists() {
        assertTrue(isSystemListForRoom(LOCAL_SYSTEM_LIST_ID, emptyList()))
        assertNull(roomDeckIdForList(LOCAL_SYSTEM_LIST_ID, isSystem = true))
    }

    @Test
    fun unknownIdIsNotTreatedAsSystem() {
        assertFalse(isSystemListForRoom("other-profile-list", lists))
        assertEquals("other-profile-list", roomDeckIdForList("other-profile-list", isSystem = false))
    }
}
