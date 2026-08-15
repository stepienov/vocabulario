package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ListCardMoveTest {

    private fun card(
        id: String,
        status: String = "ready",
    ) = CardResponse(
        id = id,
        lemma_l2 = id,
        content = buildJsonObject { },
        created_at = "",
        enrichment_status = status,
    )

    @Test
    fun readyCard_canMove() {
        assertTrue(card("srv-1", "ready").isReadyToMove())
    }

    @Test
    fun awaitingNetwork_cannotMove_butCanSelect() {
        val stub = card("pending-lookup-mesa", "awaiting_network")
        assertFalse(stub.isReadyToMove())
        assertTrue(stub.isSelectableOnList())
    }

    @Test
    fun creatingTile_cannotMoveOrSelect() {
        val creating = card("pending-casa", "pending")
        assertFalse(creating.isReadyToMove())
        assertFalse(creating.isSelectableOnList())
    }

    @Test
    fun serverPending_cannotMove() {
        val pending = card("srv-2", "pending")
        assertFalse(pending.isReadyToMove())
        assertFalse(pending.isSelectableOnList())
    }
}
