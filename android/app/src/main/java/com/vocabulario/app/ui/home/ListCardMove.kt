package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse

/** Stub offline lookup queued on the pending inbox. */
fun CardResponse.isPendingLookupStub(): Boolean =
    id.startsWith("pending-lookup-")

/**
 * Ready to leave the current list (including Oczekujące).
 * "Czeka na sieć" / still-creating tiles stay put.
 */
fun CardResponse.isReadyToMove(): Boolean {
    if (isPendingLookupStub() || id.startsWith("pending-")) return false
    val status = enrichment_status
    return status != "awaiting_network" && status != "pending"
}

/** Multi-select / delete: waiting-for-network stubs are allowed; in-flight create tiles are not. */
fun CardResponse.isSelectableOnList(): Boolean {
    if (isPendingLookupStub()) return true
    if (id.startsWith("pending-")) return false
    return enrichment_status != "pending"
}
