package com.vocabulario.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.vocabulario.app.data.session.LegacyTokenSource
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("vocabulario_prefs")

@Singleton
class TokenStore @Inject constructor(
    @ApplicationContext private val context: Context,
) : LegacyTokenSource {
    // Tylko do jednorazowej migracji do zaszyfrowanego rekordu SessionCoordinator.
    private val legacyAccessKey = stringPreferencesKey("access_token")
    private val legacyRefreshKey = stringPreferencesKey("refresh_token")
    private val profileKey = stringPreferencesKey("active_profile_id")
    private val themeKey = stringPreferencesKey("theme")
    private val appLangKey = stringPreferencesKey("app_lang")
    private val legacyUiLangKey = stringPreferencesKey("ui_lang")
    // Właściciel, dla którego serwer ostatnio wymagał potwierdzenia adresu (F-003: stan przy koncie).
    private val verificationOwnerKey = stringPreferencesKey("email_verification_required_owner")
    // Właściciel, któremu serwer kazał zaakceptować aktualne warunki (F-007/T-003).
    private val legalOwnerKey = stringPreferencesKey("legal_acceptance_required_owner")

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val cachedAppLang = AtomicReference<String?>(null)
    private val reopenSettings = AtomicBoolean(false)
    private val expandLanguages = AtomicBoolean(false)
    private val expandLimits = AtomicBoolean(false)

    private val _ready = MutableStateFlow(false)
    val ready: StateFlow<Boolean> = _ready.asStateFlow()

    private val _activeProfileId = MutableStateFlow<String?>(null)
    val activeProfileId: StateFlow<String?> = _activeProfileId.asStateFlow()

    private val _verificationRequiredOwner = MutableStateFlow<String?>(null)
    val verificationRequiredOwner: StateFlow<String?> = _verificationRequiredOwner.asStateFlow()

    private val _legalRequiredOwner = MutableStateFlow<String?>(null)
    val legalRequiredOwner: StateFlow<String?> = _legalRequiredOwner.asStateFlow()

    val theme: Flow<String> = context.dataStore.data.map { it[themeKey] ?: "system" }
    val appLang: Flow<String> = context.dataStore.data.map { readAppLang(it) }

    init {
        scope.launch {
            migrateLegacyUiLangKey()
            val prefs = context.dataStore.data.first()
            _activeProfileId.value = prefs[profileKey]
            _verificationRequiredOwner.value = prefs[verificationOwnerKey]
            _legalRequiredOwner.value = prefs[legalOwnerKey]
            cachedAppLang.set(readAppLang(prefs))
            _ready.value = true
        }
        scope.launch {
            context.dataStore.data.map { it[profileKey] }.collect { id ->
                if (_activeProfileId.value != id) {
                    _activeProfileId.value = id
                }
            }
        }
    }

    private fun readAppLang(prefs: Preferences): String =
        prefs[appLangKey] ?: prefs[legacyUiLangKey] ?: "en"

    private suspend fun migrateLegacyUiLangKey() {
        context.dataStore.edit { prefs ->
            if (prefs[appLangKey] == null && prefs[legacyUiLangKey] != null) {
                prefs[appLangKey] = prefs[legacyUiLangKey]!!
            }
            prefs.remove(legacyUiLangKey)
        }
    }

    suspend fun awaitReady() {
        ready.first { it }
    }

    override fun readLegacyTokens(): Pair<String, String>? = runBlocking(Dispatchers.IO) {
        val prefs = context.dataStore.data.first()
        val access = prefs[legacyAccessKey]?.takeIf { it.isNotBlank() }
        val refresh = prefs[legacyRefreshKey]?.takeIf { it.isNotBlank() }
        if (access != null && refresh != null) access to refresh else null
    }

    override fun removeLegacyTokens() {
        runBlocking(Dispatchers.IO) {
            val prefs = context.dataStore.data.first()
            if (prefs[legacyAccessKey] == null && prefs[legacyRefreshKey] == null) return@runBlocking
            context.dataStore.edit {
                it.remove(legacyAccessKey)
                it.remove(legacyRefreshKey)
            }
        }
    }
    suspend fun saveActiveProfile(profileId: String) {
        if (_activeProfileId.value == profileId) return
        _activeProfileId.value = profileId
        context.dataStore.edit { it[profileKey] = profileId }
    }

    suspend fun saveTheme(value: String) {
        val current = context.dataStore.data.first()[themeKey]
        if (current == value) return
        context.dataStore.edit { it[themeKey] = value }
    }

    suspend fun saveAppLang(value: String) {
        val normalized = value.trim().lowercase()
        if (cachedAppLang.get() == normalized) return
        cachedAppLang.set(normalized)
        context.dataStore.edit {
            it[appLangKey] = normalized
            it.remove(legacyUiLangKey)
        }
    }

    fun peekAppLang(): String = cachedAppLang.get().orEmpty()

    /** null = brak wymogu; pamięć od razu, zapis w tle nie blokuje wywołującego (np. interceptor). */
    fun setVerificationRequiredOwner(ownerUserId: String?) {
        if (_verificationRequiredOwner.value == ownerUserId) return
        _verificationRequiredOwner.value = ownerUserId
        scope.launch {
            context.dataStore.edit { prefs ->
                val newest = _verificationRequiredOwner.value
                if (newest == null) prefs.remove(verificationOwnerKey) else prefs[verificationOwnerKey] = newest
            }
        }
    }

    /** null = brak wymogu; tak samo jak weryfikacja adresu: pamięć od razu, zapis w tle. */
    fun setLegalRequiredOwner(ownerUserId: String?) {
        if (_legalRequiredOwner.value == ownerUserId) return
        _legalRequiredOwner.value = ownerUserId
        scope.launch {
            context.dataStore.edit { prefs ->
                val newest = _legalRequiredOwner.value
                if (newest == null) prefs.remove(legalOwnerKey) else prefs[legalOwnerKey] = newest
            }
        }
    }

    fun markExpandLimits() {
        expandLimits.set(true)
    }

    fun consumeExpandLimits(): Boolean = expandLimits.getAndSet(false)

    fun markReopenSettings() {
        reopenSettings.set(true)
        expandLanguages.set(true)
    }

    fun consumeReopenSettings(): Boolean = reopenSettings.getAndSet(false)

    fun consumeExpandLanguages(): Boolean = expandLanguages.getAndSet(false)

    suspend fun clear() {
        clearMemory()
        context.dataStore.edit { it.clear() }
    }

    /** Natychmiastowe wylogowanie w pamięci (bez blokady DataStore). */
    fun clearMemory() {
        _activeProfileId.value = null
        _verificationRequiredOwner.value = null
        _legalRequiredOwner.value = null
        cachedAppLang.set(null)
    }
}
