package com.vocabulario.app.data.deletion

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.vocabulario.app.data.api.DeletionView
import com.vocabulario.app.data.session.SessionCipher
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.Base64
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Pokwitowanie wniosku o usunięcie konta (E-001/F-006/T-002 §5). Zapisywane w Keystore przed
 * wysłaniem wniosku, żeby po utracie odpowiedzi można było sprawdzić status bez sesji.
 * [deletion] jest `null`, dopóki serwer nie potwierdził wniosku.
 */
@Serializable
data class DeletionReceipt(
    val requestId: String,
    val statusSecret: String,
    val email: String,
    val userId: String,
    /** Stały identyfikator cofnięcia: powtórzenie po utracie odpowiedzi jest idempotentne. */
    val cancelRequestId: String? = null,
    val deletion: DeletionView? = null,
)

interface DeletionReceiptPersistence {
    /** `null` także wtedy, gdy rekordu nie da się odczytać (np. brak klucza po przywróceniu). */
    fun read(): DeletionReceipt?

    /** `null` usuwa rekord. Rzuca wyjątek, gdy zapis się nie powiódł. */
    fun write(receipt: DeletionReceipt?)
}

class DeletionReceiptCodec(private val cipher: SessionCipher) {
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun encode(receipt: DeletionReceipt): String {
        val plain = json.encodeToString(DeletionReceipt.serializer(), receipt).toByteArray(Charsets.UTF_8)
        return Base64.getEncoder().encodeToString(cipher.encrypt(plain))
    }

    fun decode(stored: String): DeletionReceipt? = runCatching {
        val plain = cipher.decrypt(Base64.getDecoder().decode(stored))
        json.decodeFromString(DeletionReceipt.serializer(), String(plain, Charsets.UTF_8))
    }.getOrNull()
}

private val Context.deletionDataStore by preferencesDataStore("vocabulario_deletion")

@Singleton
class DataStoreDeletionReceiptPersistence @Inject constructor(
    @ApplicationContext private val context: Context,
    cipher: SessionCipher,
) : DeletionReceiptPersistence {
    private val codec = DeletionReceiptCodec(cipher)
    private val key = stringPreferencesKey("receipt")

    override fun read(): DeletionReceipt? {
        val stored = runBlocking(Dispatchers.IO) { context.deletionDataStore.data.first()[key] }
        return stored?.let { codec.decode(it) }
    }

    override fun write(receipt: DeletionReceipt?) {
        val encoded = receipt?.let { codec.encode(it) }
        runBlocking(Dispatchers.IO) {
            context.deletionDataStore.edit { prefs ->
                if (encoded == null) prefs.remove(key) else prefs[key] = encoded
            }
        }
    }
}

/** Pamięć podręczna pokwitowania; zapis trafia na dysk, zanim zmieni się stan w pamięci. */
@Singleton
class DeletionReceiptStore @Inject constructor(
    private val persistence: DeletionReceiptPersistence,
) {
    private val lock = Any()

    @Volatile
    private var loaded = false

    private val _receipt = MutableStateFlow<DeletionReceipt?>(null)
    val receipt: StateFlow<DeletionReceipt?> = _receipt.asStateFlow()

    suspend fun load(): DeletionReceipt? = withContext(Dispatchers.IO) {
        synchronized(lock) {
            if (!loaded) {
                _receipt.value = persistence.read()
                loaded = true
            }
            _receipt.value
        }
    }

    suspend fun save(receipt: DeletionReceipt) = withContext(Dispatchers.IO) {
        synchronized(lock) {
            persistence.write(receipt)
            loaded = true
            _receipt.value = receipt
        }
    }

    suspend fun clear() = withContext(Dispatchers.IO) {
        synchronized(lock) {
            persistence.write(null)
            loaded = true
            _receipt.value = null
        }
    }
}
