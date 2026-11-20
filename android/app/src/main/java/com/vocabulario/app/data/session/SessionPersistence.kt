package com.vocabulario.app.data.session

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import java.util.Base64
import javax.inject.Inject
import javax.inject.Singleton

sealed interface StoredSession {
    data object Empty : StoredSession
    data class Present(val record: SessionRecord) : StoredSession
    data class Unreadable(val reason: String) : StoredSession
}

/** Blokujący, bo koordynator wykonuje zapisy pod jedną blokadą (także z wątków OkHttp). */
interface SessionPersistence {
    fun read(): StoredSession

    /** `null` usuwa rekord. Rzuca wyjątek, gdy zapis się nie powiódł. */
    fun write(record: SessionRecord?)
}

/** Stare jawne tokeny z `vocabulario_prefs` sprzed zaszyfrowanego rekordu. */
interface LegacyTokenSource {
    fun readLegacyTokens(): Pair<String, String>?
    fun removeLegacyTokens()
}

class SessionRecordCodec(private val cipher: SessionCipher) {
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun encode(record: SessionRecord): String {
        val plain = json.encodeToString(SessionRecord.serializer(), record).toByteArray(Charsets.UTF_8)
        return Base64.getEncoder().encodeToString(cipher.encrypt(plain))
    }

    fun decode(stored: String): StoredSession {
        val plain = try {
            cipher.decrypt(Base64.getDecoder().decode(stored))
        } catch (e: Exception) {
            // Brak klucza, uszkodzony blob lub błąd Keystore: recovery, nigdy czyszczenie danych.
            return StoredSession.Unreadable(RECOVERY_UNREADABLE)
        }
        val record = runCatching {
            json.decodeFromString(SessionRecord.serializer(), String(plain, Charsets.UTF_8))
        }.getOrNull() ?: return StoredSession.Unreadable(RECOVERY_UNREADABLE)
        if (record.version > SESSION_RECORD_VERSION) return StoredSession.Unreadable(RECOVERY_UNREADABLE)
        return StoredSession.Present(record)
    }
}

private val Context.sessionDataStore by preferencesDataStore("vocabulario_session")

@Singleton
class DataStoreSessionPersistence @Inject constructor(
    @ApplicationContext private val context: Context,
    cipher: SessionCipher,
) : SessionPersistence {
    private val codec = SessionRecordCodec(cipher)
    private val recordKey = stringPreferencesKey("session_record")

    override fun read(): StoredSession {
        val stored = runBlocking(Dispatchers.IO) { context.sessionDataStore.data.first()[recordKey] }
            ?: return StoredSession.Empty
        return codec.decode(stored)
    }

    override fun write(record: SessionRecord?) {
        val encoded = record?.let { codec.encode(it) }
        runBlocking(Dispatchers.IO) {
            context.sessionDataStore.edit { prefs ->
                if (encoded == null) prefs.remove(recordKey) else prefs[recordKey] = encoded
            }
        }
    }
}
