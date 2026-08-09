package com.vocabulario.app.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Coordinates language-pair switches so UI can show a busy overlay
 * and screens can drop stale cards/lists immediately.
 */
@Singleton
class PairSession @Inject constructor() {
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    private val _revision = MutableStateFlow(0L)
    val revision: StateFlow<Long> = _revision.asStateFlow()

    private val _awaitingDataReload = MutableStateFlow(false)

    suspend fun <T> withSwitch(
        awaitDataReload: Boolean = false,
        block: suspend () -> T,
    ): T {
        _busy.value = true
        return try {
            val result = block()
            _revision.value = _revision.value + 1L
            if (awaitDataReload) {
                _awaitingDataReload.value = true
            } else {
                _busy.value = false
            }
            result
        } catch (e: Throwable) {
            _busy.value = false
            _awaitingDataReload.value = false
            throw e
        }
    }

    /** Called after lists/cards for the active pair have been reloaded. */
    fun markDataReady() {
        if (_awaitingDataReload.value) {
            _awaitingDataReload.value = false
        }
        _busy.value = false
    }

    fun bump() {
        _revision.value = _revision.value + 1L
    }
}
