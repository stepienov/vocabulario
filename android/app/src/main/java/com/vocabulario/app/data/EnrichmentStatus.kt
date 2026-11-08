package com.vocabulario.app.data

/** Statusy enrichmentu karty — nauka od `learnable`, pełny słownik to `ready`. */
object EnrichmentStatus {
    const val PENDING = "pending"
    const val PREPARING = "preparing"
    const val LEARNABLE = "learnable"
    const val READY = "ready"
    const val FAILED = "failed"
    const val PREP_PROBLEM = "prep_problem"
    const val AWAITING_NETWORK = "awaiting_network"

    fun isStudyable(status: String?): Boolean {
        val s = status?.trim()?.lowercase().orEmpty()
        return s == READY || s == LEARNABLE
    }

    fun isCreating(status: String?): Boolean {
        val s = status?.trim()?.lowercase().orEmpty()
        return s == PENDING || s == PREPARING
    }

    fun needsPoll(status: String?): Boolean {
        val s = status?.trim()?.lowercase().orEmpty()
        return s == PENDING || s == PREPARING || s == LEARNABLE
    }
}

/** Czy karta zostaje w odpytywaniu tej sesji ekranu. Czas liczy się od pierwszego GET. */
object EnrichmentPollPolicy {
    const val LEARNABLE_LIMIT_MS = 3 * 60 * 1000L
    const val OTHER_LIMIT_MS = 5 * 60 * 1000L

    fun shouldKeepPolling(
        status: String?,
        enrichmentActive: Boolean?,
        hasCardActivity: Boolean,
        elapsedMillis: Long,
    ): Boolean {
        if (hasCardActivity) return true
        val normalized = status?.trim()?.lowercase().orEmpty()
        if (!EnrichmentStatus.needsPoll(normalized)) return false
        val limit = if (normalized == EnrichmentStatus.LEARNABLE) LEARNABLE_LIMIT_MS else OTHER_LIMIT_MS
        if (elapsedMillis >= limit) return false
        if (enrichmentActive == null) return true
        return when (normalized) {
            EnrichmentStatus.LEARNABLE, EnrichmentStatus.PREPARING -> enrichmentActive
            else -> true
        }
    }
}
