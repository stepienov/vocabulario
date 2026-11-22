package com.vocabulario.app.data.session

import com.vocabulario.app.data.local.db.OwnerPhase
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.withContext
import kotlin.coroutines.AbstractCoroutineContextElement
import kotlin.coroutines.CoroutineContext

/** Właściciel danych i generacja przechwycone na starcie pracy w tle. */
data class OwnerContext(val ownerUserId: String, val generation: Long)

/** Kontekst zapisu tylko dla aktywnego właściciela; każda inna faza oznacza brak prawa do zapisu. */
fun ownerContextOf(ownerUserId: String?, generation: Long, phase: String): OwnerContext? =
    if (phase == OwnerPhase.ACTIVE && !ownerUserId.isNullOrBlank()) OwnerContext(ownerUserId, generation) else null

/** Praca w tle należy do innego właściciela lub generacji; wynik ma zostać porzucony bez zapisu. */
class SupersededException : IllegalStateException("superseded_owner_context")

/** Element korutyny, pod którym zapisy w Room sprawdzają właściciela w tej samej transakcji. */
class OwnerScope(val owner: OwnerContext) : AbstractCoroutineContextElement(OwnerScope) {
    companion object Key : CoroutineContext.Key<OwnerScope>
}

/**
 * Uruchamia [block] jako właściciel przechwycony teraz (albo już obowiązujący w zewnętrznym
 * zakresie). Zwraca null, gdy nie ma aktywnego właściciela albo praca została zastąpiona.
 */
suspend fun <T> runAsOwner(current: suspend () -> OwnerContext?, block: suspend () -> T): T? {
    val owner = currentCoroutineContext()[OwnerScope]?.owner ?: current() ?: return null
    return try {
        withContext(OwnerScope(owner)) { block() }
    } catch (_: SupersededException) {
        null
    }
}

/** Kontrola po HTTP i przed skutkiem ubocznym; bez zakresu nie ma czego sprawdzać. */
suspend fun ensureOwner(current: suspend () -> OwnerContext?) {
    val scoped = currentCoroutineContext()[OwnerScope]?.owner ?: return
    if (current() != scoped) throw SupersededException()
}
