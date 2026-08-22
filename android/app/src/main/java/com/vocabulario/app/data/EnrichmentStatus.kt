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
