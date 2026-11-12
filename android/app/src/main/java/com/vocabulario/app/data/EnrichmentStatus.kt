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

/**
 * Czy otwarta karta pokazuje kółko w pustych sekcjach.
 * Treść, która już jest, zawsze wchodzi od razu — kółko tylko przy realnym oczekiwaniu.
 */
object CardSectionWaiting {
    fun forCard(status: String?, stillPolling: Boolean): Boolean =
        stillPolling && EnrichmentStatus.needsPoll(status)

    fun meanings(hasMeaningContent: Boolean, status: String?, stillPolling: Boolean): Boolean {
        if (hasMeaningContent) return false
        if (!stillPolling) return false
        val s = status?.trim()?.lowercase().orEmpty()
        return s == EnrichmentStatus.PENDING || s == EnrichmentStatus.PREPARING
    }

    /**
     * Zdania przykładowe przy już widocznym glosie.
     * [examplesPending] z `content.examples_pending` (task 12); bez znacznika — kółko
     * tylko w pending/preparing przy odpytywaniu.
     */
    fun examples(
        hasExamples: Boolean,
        status: String?,
        stillPolling: Boolean,
        examplesPending: Boolean? = null,
    ): Boolean {
        if (hasExamples) return false
        if (examplesPending == false) return false
        val s = status?.trim()?.lowercase().orEmpty()
        if (examplesPending == true) {
            return stillPolling || EnrichmentStatus.needsPoll(s)
        }
        if (!stillPolling) return false
        return s == EnrichmentStatus.PENDING || s == EnrichmentStatus.PREPARING
    }

    /**
     * Synonimy / przeciwieństwa / rodzina / skojarzenia.
     * [relatedPending] pochodzi z `content.related_pending` (task 10); przy braku znacznika
     * kółko jest tylko przed `learnable`.
     */
    fun related(
        isEmpty: Boolean,
        status: String?,
        stillPolling: Boolean,
        relatedPending: Boolean? = null,
    ): Boolean {
        if (!isEmpty) return false
        if (relatedPending == false) return false
        val s = status?.trim()?.lowercase().orEmpty()
        if (relatedPending == true) {
            return stillPolling || EnrichmentStatus.needsPoll(s)
        }
        if (!stillPolling) return false
        return s == EnrichmentStatus.PENDING || s == EnrichmentStatus.PREPARING
    }

    /**
     * Odmiana: nagłówek z kółkiem, gdy jeszcze jej nie ma, a karta nie jest gotowa
     * i spodziewamy się odmiany (czasownik / show_conjugation). Nie zależy wyłącznie
     * od stillPolling — inaczej przy learnable znika cały sektor „Odmiana”.
     */
    fun inflection(
        hasInflection: Boolean,
        status: String?,
        stillPolling: Boolean,
        expectInflection: Boolean = true,
    ): Boolean {
        if (hasInflection || !expectInflection) return false
        val s = status?.trim()?.lowercase().orEmpty()
        if (s == EnrichmentStatus.READY ||
            s == EnrichmentStatus.FAILED ||
            s == EnrichmentStatus.PREP_PROBLEM
        ) {
            return false
        }
        if (!EnrichmentStatus.needsPoll(s)) return false
        return stillPolling || s == EnrichmentStatus.LEARNABLE ||
            s == EnrichmentStatus.PENDING ||
            s == EnrichmentStatus.PREPARING
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
