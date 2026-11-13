package com.vocabulario.app.data

import com.vocabulario.app.data.api.CardResponse
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Odpytywanie enrichmentu żyje w procesie aplikacji, nie w ViewModelu ekranu.
 * Zamknięcie karty, wyjście z nauki i onStop nie anulują pętli.
 */
@Singleton
class EnrichmentPoller @Inject constructor(
    private val repository: LearningRepository,
) {
    data class Watch(
        val id: String,
        val status: String?,
        val activity: String? = null,
    )

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()
    private val startedAt = mutableMapOf<String, Long>()
    private val stopped = mutableSetOf<String>()
    private val lastEnrichmentActive = mutableMapOf<String, Boolean?>()
    private val lastStatus = mutableMapOf<String, String?>()
    private val lastActivity = mutableMapOf<String, String?>()
    private val seenIdentity = mutableMapOf<String, String>()
    private val _pollingIds = MutableStateFlow<Set<String>>(emptySet())
    val pollingIds: StateFlow<Set<String>> = _pollingIds.asStateFlow()
    private var loopJob: Job? = null

    fun isPolling(cardId: String): Boolean = cardId in _pollingIds.value

    fun sectionWaiting(cardId: String, status: String?): Boolean =
        CardSectionWaiting.forCard(status = status, stillPolling = isPolling(cardId))

    /** Dopisuje karty do odpytywania. Nie kasuje już obserwowanych przy wyjściu z ekranu. */
    fun watch(cards: Collection<Watch>) {
        if (cards.isEmpty()) return
        scope.launch {
            mutex.withLock {
                val now = System.currentTimeMillis()
                for (card in cards) {
                    val id = card.id.trim()
                    if (!isServerCardId(id)) continue
                    noteIdentity(id, card.status, card.activity)
                    lastStatus[id] = card.status
                    lastActivity[id] = card.activity
                    if (id in stopped) continue
                    val watch = EnrichmentStatus.needsPoll(card.status) ||
                        !card.activity.isNullOrBlank()
                    if (!watch) continue
                    startedAt.putIfAbsent(id, now)
                }
                publishLocked()
            }
            ensureLoop()
        }
    }

    fun watchCards(cards: Collection<CardResponse>) {
        watch(
            cards.map {
                Watch(
                    id = it.id,
                    status = it.enrichment_status,
                    activity = it.card_activity_status,
                )
            },
        )
    }

    fun watchCard(card: CardResponse) {
        watchCards(listOf(card))
    }

    fun reset() {
        scope.launch {
            mutex.withLock {
                startedAt.clear()
                stopped.clear()
                lastEnrichmentActive.clear()
                lastStatus.clear()
                lastActivity.clear()
                seenIdentity.clear()
                _pollingIds.value = emptySet()
            }
            loopJob?.cancel()
            loopJob = null
        }
    }

    private fun isServerCardId(id: String): Boolean =
        id.isNotBlank() && !id.startsWith("pending-") && !id.startsWith("local:")

    private fun noteIdentity(id: String, status: String?, activity: String?) {
        val key = "${status.orEmpty()}|${activity.orEmpty()}"
        val previous = seenIdentity.put(id, key)
        if (previous != null && previous != key) {
            stopped.remove(id)
            startedAt.remove(id)
            lastEnrichmentActive.remove(id)
        }
    }

    private fun publishLocked() {
        val now = System.currentTimeMillis()
        val active = linkedSetOf<String>()
        for ((id, started) in startedAt) {
            if (id in stopped) continue
            val status = lastStatus[id]
            val activity = lastActivity[id]
            val hasActivity = !activity.isNullOrBlank()
            if (!EnrichmentStatus.needsPoll(status) && !hasActivity) continue
            val keep = EnrichmentPollPolicy.shouldKeepPolling(
                status = status,
                enrichmentActive = lastEnrichmentActive[id],
                hasCardActivity = hasActivity,
                elapsedMillis = now - started,
            )
            if (!keep) {
                stopped.add(id)
                continue
            }
            active.add(id)
        }
        _pollingIds.value = active
    }

    private fun ensureLoop() {
        if (loopJob?.isActive == true) return
        loopJob = scope.launch {
            while (isActive) {
                val ids = mutex.withLock {
                    publishLocked()
                    _pollingIds.value.toList()
                }
                if (ids.isEmpty()) {
                    runCatching { repository.evaluateReadyBatches() }
                    break
                }
                val fetched = runCatching { repository.refreshCardsFromServer(ids) }
                    .getOrNull()
                    .orEmpty()
                mutex.withLock {
                    val now = System.currentTimeMillis()
                    fetched.forEach { card ->
                        noteIdentity(card.id, card.enrichment_status, card.card_activity_status)
                        lastStatus[card.id] = card.enrichment_status
                        lastActivity[card.id] = card.card_activity_status
                        lastEnrichmentActive[card.id] = card.enrichment_active
                        startedAt.putIfAbsent(card.id, now)
                        val keep = EnrichmentPollPolicy.shouldKeepPolling(
                            status = card.enrichment_status,
                            enrichmentActive = card.enrichment_active,
                            hasCardActivity = !card.card_activity_status.isNullOrBlank(),
                            elapsedMillis = now - (startedAt[card.id] ?: now),
                        )
                        if (!keep) stopped.add(card.id)
                    }
                    publishLocked()
                }
                if (_pollingIds.value.isEmpty()) {
                    runCatching { repository.evaluateReadyBatches() }
                    break
                }
                delay(2_500)
            }
        }
    }
}
