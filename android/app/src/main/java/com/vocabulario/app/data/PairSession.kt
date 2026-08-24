package com.vocabulario.app.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Coordinates language-pair switches so UI can show a busy overlay
 * and screens can drop stale cards/lists immediately.
 *
 * [markDataReady] only clears busy for the switch that asked to await reload.
 * A Home refresh during someone else's switch cannot dismiss the overlay.
 */
@Singleton
class PairSession @Inject constructor() {
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    private val _revision = MutableStateFlow(0L)
    val revision: StateFlow<Long> = _revision.asStateFlow()

    private var switchGen = 0L
    private var awaitingGen = 0L

    suspend fun <T> withSwitch(
        awaitDataReload: Boolean = false,
        block: suspend () -> T,
    ): T {
        val gen = ++switchGen
        awaitingGen = 0L
        _busy.value = true
        return try {
            val result = block()
            _revision.value = _revision.value + 1L
            if (awaitDataReload && switchGen == gen) {
                awaitingGen = gen
            } else if (switchGen == gen) {
                _busy.value = false
            }
            result
        } catch (e: Throwable) {
            if (switchGen == gen) {
                _busy.value = false
                awaitingGen = 0L
            }
            throw e
        }
    }

    /** Called after lists/cards for the active pair have been reloaded. */
    fun markDataReady() {
        val gen = awaitingGen
        if (gen == 0L || gen != switchGen) return
        awaitingGen = 0L
        _busy.value = false
    }

    fun bump() {
        _revision.value = _revision.value + 1L
    }
}
