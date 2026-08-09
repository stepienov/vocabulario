package com.vocabulario.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
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
import java.util.concurrent.atomic.AtomicReference
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore("vocabulario_prefs")

@Singleton
class TokenStore @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val accessKey = stringPreferencesKey("access_token")
    private val refreshKey = stringPreferencesKey("refresh_token")
    private val profileKey = stringPreferencesKey("active_profile_id")
    private val themeKey = stringPreferencesKey("theme")
    private val appLangKey = stringPreferencesKey("app_lang")
    private val legacyUiLangKey = stringPreferencesKey("ui_lang")

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val cachedAccess = AtomicReference<String?>(null)
    private val cachedRefresh = AtomicReference<String?>(null)

    private val _ready = MutableStateFlow(false)
    val ready: StateFlow<Boolean> = _ready.asStateFlow()

    private val _accessToken = MutableStateFlow<String?>(null)
    val accessToken: Flow<String?> = _accessToken

    private val _activeProfileId = MutableStateFlow<String?>(null)
    val activeProfileId: StateFlow<String?> = _activeProfileId.asStateFlow()

    val theme: Flow<String> = context.dataStore.data.map { it[themeKey] ?: "system" }
    val appLang: Flow<String> = context.dataStore.data.map { readAppLang(it) }

    init {
        scope.launch {
            migrateLegacyUiLangKey()
            val prefs = context.dataStore.data.first()
            val access = prefs[accessKey]
            val refresh = prefs[refreshKey]
            cachedAccess.set(access)
            cachedRefresh.set(refresh)
            _accessToken.value = access
            _activeProfileId.value = prefs[profileKey]
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

    /** Tylko pamięć — nigdy nie blokuj wątku (OkHttp / Main). */
    fun peekAccessToken(): String? = cachedAccess.get()

    fun peekRefreshToken(): String? = cachedRefresh.get()

    suspend fun awaitReady() {
        ready.first { it }
    }

    suspend fun saveTokens(access: String, refresh: String) {
        cachedAccess.set(access)
        cachedRefresh.set(refresh)
        _accessToken.value = access
        context.dataStore.edit {
            it[accessKey] = access
            it[refreshKey] = refresh
        }
    }

    /** Dla Authenticatora — cache od razu, zapis DataStore w tle. */
    fun saveTokensAsync(access: String, refresh: String) {
        cachedAccess.set(access)
        cachedRefresh.set(refresh)
        _accessToken.value = access
        scope.launch {
            runCatching {
                context.dataStore.edit {
                    it[accessKey] = access
                    it[refreshKey] = refresh
                }
            }
        }
    }

    suspend fun getRefreshToken(): String? =
        cachedRefresh.get()
            ?: context.dataStore.data.first()[refreshKey]?.also { cachedRefresh.set(it) }

    suspend fun saveActiveProfile(profileId: String) {
        _activeProfileId.value = profileId
        context.dataStore.edit { it[profileKey] = profileId }
    }

    suspend fun saveTheme(value: String) {
        context.dataStore.edit { it[themeKey] = value }
    }

    suspend fun saveAppLang(value: String) {
        context.dataStore.edit {
            it[appLangKey] = value.trim().lowercase()
            it.remove(legacyUiLangKey)
        }
    }

    suspend fun peekAppLang(): String =
        readAppLang(context.dataStore.data.first())

    suspend fun clear() {
        clearMemory()
        context.dataStore.edit { it.clear() }
    }

    /** Natychmiastowe wylogowanie w pamięci (bez blokady DataStore). */
    fun clearMemory() {
        cachedAccess.set(null)
        cachedRefresh.set(null)
        _accessToken.value = null
        _activeProfileId.value = null
        scope.launch {
            runCatching { context.dataStore.edit { it.clear() } }
        }
    }
}
