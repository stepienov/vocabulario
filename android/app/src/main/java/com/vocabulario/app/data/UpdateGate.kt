package com.vocabulario.app.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

const val CLIENT_VERSION_HEADER = "X-App-Version-Code"
const val UPDATE_REQUIRED_STATUS = 426

/**
 * Serwer odrzucił tę wersję aplikacji (426 `app_update_required`). To tylko blokada ekranu:
 * sesja, Room i kolejki zostają nietknięte, a odpowiedź nigdy nie jest powodem ponowienia ani logoutu.
 */
@Singleton
class UpdateGate @Inject constructor() {
    private val _required = MutableStateFlow(false)
    val required: StateFlow<Boolean> = _required.asStateFlow()

    fun onServerRequired() {
        _required.value = true
    }

    /** Po ręcznym „sprawdź ponownie"; następne żądanie ustawi blokadę, jeśli minimum nadal obowiązuje. */
    fun clear() {
        _required.value = false
    }
}

/** Jedyny adres aktualizacji, jaki aplikacja otwiera: własny wpis w Google Play, nie URL z odpowiedzi. */
fun playListingUrl(packageName: String): String =
    "https://play.google.com/store/apps/details?id=$packageName"
