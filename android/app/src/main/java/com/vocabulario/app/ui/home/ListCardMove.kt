package com.vocabulario.app.ui.home

import com.vocabulario.app.data.api.CardResponse

/** Stub offline lookup queued on the pending inbox. */
fun CardResponse.isPendingLookupStub(): Boolean =
    id.startsWith("pending-lookup-")

/** Optymistyczny kafelek „tworzę kartę” — jeszcze nie ma rekordu na serwerze. */
fun CardResponse.isOptimisticCreatingTile(): Boolean =
    id.startsWith("pending-") && !isPendingLookupStub()

/**
 * Ready to leave the current list (including Oczekujące).
 * Zostają tylko stuby bez rekordu: offline lookup i kafelek w trakcie create.
 * Pending enrichment na prawdziwym UUID nie blokuje przenoszenia ani usuwania.
 */
fun CardResponse.isReadyToMove(): Boolean {
    if (isPendingLookupStub() || isOptimisticCreatingTile()) return false
    return enrichment_status != "awaiting_network"
}

/** Multi-select / delete: czekające na sieć — tak; kafelek create — nie. */
fun CardResponse.isSelectableOnList(): Boolean {
    if (isPendingLookupStub()) return true
    if (isOptimisticCreatingTile()) return false
    return true
}
