package com.vocabulario.app.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicInteger
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Ref-counted lock for the shared full-screen busy overlay (blur + spinner).
 * Nested [run] / [launchIn] calls keep the overlay up until the outermost
 * wait finishes.
 */
@Singleton
class BlockingBusy @Inject constructor() {
    private val depth = AtomicInteger(0)
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    fun acquire(message: String? = null) {
        if (message != null) _message.value = message
        if (depth.incrementAndGet() > 0) _busy.value = true
    }

    fun release() {
        while (true) {
            val cur = depth.get()
            if (cur <= 0) {
                _busy.value = false
                _message.value = null
                return
            }
            if (depth.compareAndSet(cur, cur - 1)) {
                if (cur - 1 == 0) {
                    _busy.value = false
                    _message.value = null
                }
                return
            }
        }
    }

    suspend fun <T> run(message: String? = null, block: suspend () -> T): T {
        acquire(message)
        try {
            return block()
        } finally {
            release()
        }
    }

    /** Acquire on the calling thread so the overlay appears before dispatch. */
    fun launchIn(scope: CoroutineScope, message: String? = null, block: suspend () -> Unit): Job {
        acquire(message)
        return scope.launch {
            try {
                block()
            } finally {
                release()
            }
        }
    }
}
