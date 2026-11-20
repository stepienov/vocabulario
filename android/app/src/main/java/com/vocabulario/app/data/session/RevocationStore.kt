package com.vocabulario.app.data.session

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import java.util.Base64
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

interface WallClock {
    fun nowMs(): Long
}

class SystemWallClock @Inject constructor() : WallClock {
    override fun nowMs(): Long = System.currentTimeMillis()
}

/** Blokujący jak [SessionPersistence]; zapis rzuca wyjątek, gdy się nie powiódł. */
interface RevocationPersistence {
    fun read(): RevocationQueue
    fun write(queue: RevocationQueue)
}

class RevocationQueueCodec(private val cipher: SessionCipher) {
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun encode(queue: RevocationQueue): String {
        val plain = json.encodeToString(RevocationQueue.serializer(), queue).toByteArray(Charsets.UTF_8)
        return Base64.getEncoder().encodeToString(cipher.encrypt(plain))
    }

    /**
     * Nieczytelna kolejka (brak klucza po odtworzeniu, uszkodzenie) nie ma użytecznych sekretów,
     * więc traktujemy ją jak pustą; nie dotyka to danych konta w Room.
     */
    fun decode(stored: String): RevocationQueue {
        val plain = runCatching { cipher.decrypt(Base64.getDecoder().decode(stored)) }.getOrNull()
            ?: return RevocationQueue()
        val queue = runCatching {
            json.decodeFromString(RevocationQueue.serializer(), String(plain, Charsets.UTF_8))
        }.getOrNull() ?: return RevocationQueue()
        return if (queue.version > REVOCATION_QUEUE_VERSION) RevocationQueue() else queue
    }
}

private val Context.revocationDataStore by preferencesDataStore("vocabulario_revocations")

@Singleton
class DataStoreRevocationPersistence @Inject constructor(
    @ApplicationContext private val context: Context,
    cipher: SessionCipher,
) : RevocationPersistence {
    private val codec = RevocationQueueCodec(cipher)
    private val queueKey = stringPreferencesKey("revocation_queue")

    override fun read(): RevocationQueue {
        val stored = runBlocking(Dispatchers.IO) { context.revocationDataStore.data.first()[queueKey] }
            ?: return RevocationQueue()
        return codec.decode(stored)
    }

    override fun write(queue: RevocationQueue) {
        val encoded = if (queue.requests.isEmpty()) null else codec.encode(queue)
        runBlocking(Dispatchers.IO) {
            context.revocationDataStore.edit { prefs ->
                if (encoded == null) prefs.remove(queueKey) else prefs[queueKey] = encoded
            }
        }
    }
}

class RevocationQueueFullException : Exception("revocation_queue_full")

/** Miejsce zarezerwowane przed HTTP loginu; zwalniane po decyzji o kandydacie. */
class RevocationReservation internal constructor(internal val id: String)

/**
 * Zaszyfrowana kolejka zleceń odwołania, trzymana poza danymi konta (nie znika przy logout).
 * Wszystkie operacje pod jedną blokadą; każda zmiana jest trwała, zanim trafi do pamięci.
 */
@Singleton
class RevocationStore @Inject constructor(
    private val persistence: RevocationPersistence,
    private val clock: WallClock,
) {
    private val lock = Any()
    private var cached: RevocationQueue? = null
    private val reservations = mutableSetOf<String>()

    private val _summary = MutableStateFlow(RevocationSummary())
    val summary: StateFlow<RevocationSummary> = _summary.asStateFlow()

    /** Odczyt z purge sekretów starszych niż 30 dni. */
    fun load(): RevocationQueue = synchronized(lock) { queueLocked() }

    fun reserve(activeSession: Boolean): RevocationReservation = synchronized(lock) {
        val queue = runCatching { queueLocked() }.getOrDefault(RevocationQueue())
        if (!canReserve(queue.pendingCount, reservations.size, activeSession)) throw RevocationQueueFullException()
        RevocationReservation(UUID.randomUUID().toString()).also { reservations += it.id }
    }

    fun release(reservation: RevocationReservation) {
        synchronized(lock) { reservations -= reservation.id }
    }

    /** Dodanie zlecenia; zużywa rezerwację kandydata. Rzuca, gdy zapis się nie powiódł. */
    fun add(material: RevocationMaterial, reservation: RevocationReservation? = null): RevocationRequest =
        synchronized(lock) {
            val request = RevocationRequest(
                id = UUID.randomUUID().toString(),
                ownerUserId = material.ownerUserId,
                sessionId = material.sessionId,
                refreshToken = material.refreshToken,
                pendingRefresh = material.pendingRefresh,
                createdAtMs = clock.nowMs(),
            )
            val queue = queueLocked()
            writeLocked(queue.copy(requests = queue.requests + request))
            reservation?.let { reservations -= it.id }
            request
        }

    /** Zlecenia gotowe do wysłania teraz (bez odroczonych przez `Retry-After`). */
    fun due(): List<RevocationRequest> = synchronized(lock) {
        val now = clock.nowMs()
        queueLocked().requests.filter { it.state == RevocationState.PENDING && it.notBeforeMs <= now }
    }

    /** Najbliższy termin odroczonego zlecenia albo null. */
    fun nextDeferredAtMs(): Long? = synchronized(lock) {
        val now = clock.nowMs()
        queueLocked().requests
            .filter { it.state == RevocationState.PENDING && it.notBeforeMs > now }
            .minOfOrNull { it.notBeforeMs }
    }

    /** `null` z [transform] usuwa zlecenie (np. po potwierdzonym 204). Rzuca, gdy zapis zawiódł. */
    fun update(id: String, transform: (RevocationRequest) -> RevocationRequest?) {
        synchronized(lock) {
            val queue = queueLocked()
            val existing = queue.requests.firstOrNull { it.id == id } ?: return
            val updated = transform(existing)
            val requests = if (updated == null) {
                queue.requests.filterNot { it.id == id }
            } else {
                queue.requests.map { if (it.id == id) updated else it }
            }
            writeLocked(queue.copy(requests = trimUnconfirmed(requests)))
        }
    }

    /** Użytkownik przyjął do wiadomości brak potwierdzenia; oczekujących zleceń nie ruszamy. */
    fun dismissUnconfirmed() {
        synchronized(lock) {
            val queue = queueLocked()
            if (queue.unconfirmedCount == 0) return
            writeLocked(queue.copy(requests = queue.requests.filter { it.state == RevocationState.PENDING }))
        }
    }

    private fun queueLocked(): RevocationQueue {
        val base = cached ?: persistence.read()
        val purged = base.purgeExpired(clock.nowMs())
        // Wygasły sekret znika z pamięci od razu; nieudany zapis na dysk nadpisze najbliższa zmiana kolejki.
        if (purged != base) runCatching { persistence.write(purged) }
        cached = purged
        _summary.value = purged.summary()
        return purged
    }

    private fun writeLocked(queue: RevocationQueue) {
        persistence.write(queue)
        cached = queue
        _summary.value = queue.summary()
    }
}
