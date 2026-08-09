package com.vocabulario.app.data.local

import com.vocabulario.app.data.api.CardResponse

/**
 * Czysta logika prezentacji skrzynki „Oczekujące": jeden kafelek na słowo.
 * Stub offline („Czeka na sieć") znika, gdy istnieje już karta serwerowa dla tego słowa —
 * dzięki temu przejście stub → karta to zmiana stanu tego samego kafelka, nie nowy wiersz.
 */
object PendingInboxDisplay {

    private fun norm(s: String) = s.trim().lowercase()

    fun merge(stubs: List<CardResponse>, cards: List<CardResponse>): List<CardResponse> {
        val cardLemmas = cards.map { norm(it.lemma_l2) }.toSet()

        fun stubHasCard(stub: CardResponse): Boolean {
            val stubLemma = norm(stub.lemma_l2)
            if (stubLemma in cardLemmas) return true
            // Karta mogła znormalizować lemma (np. „zloto" → „el oro"); dopasuj też po glosie.
            return cards.any { card -> card.gloss_primary?.let { norm(it) == stubLemma } == true }
        }

        val orphanStubs = stubs.filterNot { stubHasCard(it) }
        return (orphanStubs + cards)
            .distinctBy { it.id }
            .sortedWith(
                compareBy<CardResponse> {
                    when (it.enrichment_status) {
                        "needs_review" -> 0
                        "awaiting_network" -> 1
                        "pending" -> 2
                        else -> 3
                    }
                }.thenBy { norm(it.lemma_l2) },
            )
    }
}
