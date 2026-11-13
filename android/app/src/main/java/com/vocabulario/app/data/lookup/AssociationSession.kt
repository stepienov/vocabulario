package com.vocabulario.app.data.lookup

import com.vocabulario.app.data.canonicalLemma
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.LookupResponse
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AssocRoundNotReady : Exception()

fun AssociationState.toLookupSession() = LookupSessionState(
    generation = generation,
    query = query,
    candidates = candidates,
    expanding = expanding,
    suggestionsExhausted = false,
    error = error,
    notice = notice,
)

data class AssociationState(
    val generation: Long = 0,
    val query: String = "",
    val word: LookupCandidate? = null,
    val wordLoading: Boolean = false,
    val rounds: List<List<LookupCandidate>> = emptyList(),
    val roundLoading: Int? = null,
    val exhausted: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
) {
    val candidates: List<LookupCandidate>
        get() = listOfNotNull(word) + rounds.flatten()

    val expanding: Boolean
        get() = wordLoading || roundLoading != null

    val canAskMore: Boolean
        get() = rounds.size in 1..2 && roundLoading == null && !wordLoading && !exhausted

    val hasResultsOrProgress: Boolean
        get() = expanding || candidates.isNotEmpty() || error != null || notice != null
}

class AssociationSession(
    private val lookupWord: suspend (String) -> LookupResponse,
    private val lookupRound: suspend (String, Int) -> LookupResponse,
    private val mapError: (Throwable) -> String,
    private val parent: CoroutineScope,
) {
    private val _state = MutableStateFlow(AssociationState())
    val state: StateFlow<AssociationState> = _state.asStateFlow()
    private var job: Job? = null

    fun start(query: String) {
        val text = query.trim()
        if (text.isEmpty()) return
        job?.cancel()
        val gen = _state.value.generation + 1
        _state.value = AssociationState(
            generation = gen,
            query = text,
            wordLoading = true,
            roundLoading = 1,
        )
        job = parent.launch {
            launch {
                val response = try {
                    lookupWord(text)
                } catch (_: Throwable) {
                    null
                }
                if (_state.value.generation != gen) return@launch
                val word = response?.candidates?.firstOrNull()
                _state.value = refilter(
                    publish(gen) { it.copy(word = word, wordLoading = false) },
                )
            }
            launch {
                loadRound(gen, text, 1, append = false)
            }
        }
    }

    fun more() {
        val now = _state.value
        if (!now.canAskMore) return
        val gen = now.generation
        val text = now.query
        val round = now.rounds.size + 1
        _state.value = now.copy(roundLoading = round, error = null, notice = null)
        job = parent.launch {
            loadRound(gen, text, round, append = true)
        }
    }

    fun clear() {
        job?.cancel()
        _state.value = AssociationState()
    }

    fun retryPending() {
        val now = _state.value
        if (now.query.isBlank()) return
        if (now.wordLoading || now.roundLoading != null) {
            start(now.query)
        }
    }

    private suspend fun loadRound(gen: Long, text: String, round: Int, append: Boolean) {
        try {
            val response = lookupRound(text, round)
            if (_state.value.generation != gen) return
            val fresh = filter(response.candidates, _state.value)
            _state.value = publish(gen) { current ->
                val rounds = if (append && fresh.isNotEmpty()) {
                    current.rounds + listOf(fresh)
                } else if (!append) {
                    if (fresh.isEmpty()) current.rounds else listOf(fresh)
                } else {
                    current.rounds
                }
                val done = fresh.isEmpty() || rounds.size >= 3
                current.copy(
                    rounds = rounds,
                    roundLoading = null,
                    exhausted = done && (append || rounds.isNotEmpty() && fresh.isEmpty()),
                    notice = null,
                )
            }
            val after = _state.value
            if (after.generation == gen && after.rounds.size >= 3) {
                _state.value = after.copy(exhausted = true)
            }
            if (after.generation == gen && append && fresh.isEmpty()) {
                _state.value = _state.value.copy(exhausted = true, roundLoading = null)
            }
        } catch (_: AssocRoundNotReady) {
            if (_state.value.generation != gen) return
            _state.value = _state.value.copy(roundLoading = null)
        } catch (error: Throwable) {
            if (_state.value.generation != gen) return
            _state.value = _state.value.copy(
                roundLoading = null,
                notice = mapError(error),
            )
        }
    }

    private fun publish(gen: Long, block: (AssociationState) -> AssociationState): AssociationState {
        val current = _state.value
        if (current.generation != gen) return current
        return block(current)
    }

    private fun refilter(state: AssociationState): AssociationState {
        val cleaned = mutableListOf<List<LookupCandidate>>()
        val blocked = mutableSetOf<String>()
        canonicalLemma(state.word?.lemma).takeIf { it.isNotEmpty() }?.let { blocked += it }
        for (round in state.rounds) {
            val keep = round.filter { canonicalLemma(it.lemma) !in blocked }
            cleaned += keep
            keep.forEach { lemma ->
                canonicalLemma(lemma.lemma).takeIf { it.isNotEmpty() }?.let { blocked += it }
            }
        }
        return state.copy(rounds = cleaned)
    }

    private fun filter(
        incoming: List<LookupCandidate>,
        current: AssociationState,
    ): List<LookupCandidate> {
        val blocked = buildSet {
            current.word?.lemma?.let { add(canonicalLemma(it)) }
            current.rounds.flatten().forEach { add(canonicalLemma(it.lemma)) }
        }.filter { it.isNotEmpty() }.toSet()
        return incoming.filter { canonicalLemma(it.lemma) !in blocked }
    }
}
