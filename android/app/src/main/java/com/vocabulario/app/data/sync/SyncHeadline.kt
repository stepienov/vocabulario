package com.vocabulario.app.data.sync

/** Stan synchronizacji w jednym słowie dla użytkownika; teksty dobiera UI, nigdy odpowiedź backendu. */
enum class SyncHeadline {
    /** Brak jeszcze żadnej synchronizacji i żadnej oczekującej pracy. */
    IDLE,
    SYNCING,
    SYNCED,

    /** Zmiany zapisane na urządzeniu, wyślą się przy następnej synchronizacji. */
    SAVED_LOCALLY,
    OFFLINE,
    OFFLINE_WITH_PENDING,

    /** Część wysłana, reszta czeka na ponowienie. */
    PARTIAL,
    SIGN_IN_REQUIRED,
    VERIFICATION_REQUIRED,
    CONSENT_REQUIRED,

    /** Zablokowane, zaparkowane lub do sprawdzenia: wymaga działania użytkownika. */
    NEEDS_ATTENTION,
}

/** Stan ostatniego przebiegu syncu trzymany w pamięci (bez treści błędów). */
data class SyncStatus(
    val running: Boolean = false,
    val last: SyncResult? = null,
    val lastAttemptAt: Long? = null,
    val lastCompleteAt: Long? = null,
)

/**
 * Priorytet: trwa sync → blokada konta (auth/weryfikacja/zgody) → praca wymagająca decyzji →
 * brak sieci → częściowy wynik → zmiany lokalne → pełna synchronizacja. Nie sumuje stanów i nie
 * pokazuje „zsynchronizowano", gdy coś czeka.
 */
fun syncHeadline(online: Boolean, status: SyncStatus, queue: QueueSnapshot): SyncHeadline {
    if (status.running) return SyncHeadline.SYNCING
    when (status.last) {
        is SyncResult.AuthRequired -> return SyncHeadline.SIGN_IN_REQUIRED
        is SyncResult.VerificationRequired -> return SyncHeadline.VERIFICATION_REQUIRED
        is SyncResult.LegalAcceptanceRequired -> return SyncHeadline.CONSENT_REQUIRED
        else -> Unit
    }
    if (queue.blocked > 0 || queue.lookupsNeedsReview > 0) return SyncHeadline.NEEDS_ATTENTION
    if (!online) {
        return if (queue.unresolved > 0) SyncHeadline.OFFLINE_WITH_PENDING else SyncHeadline.OFFLINE
    }
    val last = status.last
    if ((last is SyncResult.Partial || last is SyncResult.Failed || last is SyncResult.Offline) &&
        queue.unresolved > 0
    ) {
        return SyncHeadline.PARTIAL
    }
    if (queue.unresolved > 0) return SyncHeadline.SAVED_LOCALLY
    if (status.lastCompleteAt != null || last is SyncResult.Complete) return SyncHeadline.SYNCED
    return SyncHeadline.IDLE
}

/** Przycisk „Spróbuj ponownie" ma sens tylko wtedy, gdy coś czeka na wysłanie. */
fun SyncHeadline.canRetry(): Boolean = when (this) {
    SyncHeadline.SAVED_LOCALLY, SyncHeadline.PARTIAL, SyncHeadline.OFFLINE_WITH_PENDING -> true
    else -> false
}

/** Akcje zablokowanej pozycji: konflikt rewizji profilu daje wybór stron, reszta tylko „Odrzuć". */
enum class BlockedAction { APPLY_MINE, ACCEPT_SERVER, DISCARD }

fun blockedActions(item: BlockedItem): List<BlockedAction> =
    if (item.kind == BlockedKind.OUTBOX && item.type == OP_PROFILE_UPDATE && ProfileBlock.canApplyMine(item.reason)) {
        listOf(BlockedAction.APPLY_MINE, BlockedAction.ACCEPT_SERVER)
    } else {
        listOf(BlockedAction.DISCARD)
    }