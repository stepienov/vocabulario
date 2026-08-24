package com.vocabulario.app.data

import com.vocabulario.app.data.api.WordListResponse

internal const val LOCAL_SYSTEM_LIST_ID = "local-system-learning"

internal fun isSystemListForRoom(listId: String, lists: List<WordListResponse>): Boolean {
    if (listId == LOCAL_SYSTEM_LIST_ID) return true
    return lists.any { it.id == listId && it.is_system }
}

/**
 * `deckId` zapisane przy karcie w Room.
 *
 * Lista systemowa („Uczę się”) = `null`, tak samo jak `deck_id` na serwerze.
 * `systemListCards()` pokazuje tylko `deckId IS NULL` — UUID listy systemowej
 * sprawia, że karta istnieje w bazie, ale użytkownik jej nie widzi.
 *
 * Nie wolno pisać tego jako `find { is_system }?.let { null } ?: listId`:
 * lewa strona jest zawsze null, więc Elvis i tak wstawia UUID.
 */
internal fun roomDeckIdForList(listId: String, isSystem: Boolean): String? {
    if (isSystem) return null
    return listId
}
