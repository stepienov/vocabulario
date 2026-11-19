package com.vocabulario.app.data

import android.os.Build
import com.vocabulario.app.BuildConfig

/**
 * Domyślnie lokalny BE:
 * emulator → [BuildConfig.API_EMULATOR_HOST] (10.0.2.2),
 * telefon → [BuildConfig.API_DEVICE_HOST] z `android/local.properties`.
 *
 * Jeśli [BuildConfig.API_BASE_URL] jest ustawione (build testera z `-Papi.base.url`),
 * idzie na ten URL (np. Railway) i pomija host/port lokalny.
 */
object ApiBaseUrl {
    fun resolve(): String = resolveApiBaseUrl(
        override = BuildConfig.API_BASE_URL,
        isEmulator = isEmulator(),
        emulatorHost = BuildConfig.API_EMULATOR_HOST,
        deviceHost = BuildConfig.API_DEVICE_HOST,
        port = BuildConfig.API_PORT,
        allowLocal = BuildConfig.DEBUG,
    )

    fun isEmulator(): Boolean {
        val fingerprint = Build.FINGERPRINT.lowercase()
        val model = Build.MODEL.lowercase()
        val product = Build.PRODUCT.lowercase()
        val hardware = Build.HARDWARE.lowercase()
        return fingerprint.contains("generic") ||
            fingerprint.contains("emulator") ||
            model.contains("emulator") ||
            model.contains("android sdk") ||
            product.contains("sdk") ||
            product.contains("emulator") ||
            hardware.contains("goldfish") ||
            hardware.contains("ranchu") ||
            (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic"))
    }
}

/** Adres, którego nie da się osiągnąć; release nigdy nie schodzi do hosta lokalnego ani do HTTP. */
const val UNREACHABLE_API_BASE_URL = "https://api.invalid/api/v1/"

/** Release: tylko https, bez danych logowania/query/fragmentu i bez hosta lokalnego lub literału IP. */
fun isSecureApiBaseUrl(url: String): Boolean {
    val uri = runCatching { java.net.URI(url.trim().trimEnd('/')) }.getOrNull() ?: return false
    val host = uri.host?.lowercase() ?: return false
    val local = host == "localhost" || !host.contains('.') ||
        host.endsWith(".local") || host.endsWith(".internal") || host.endsWith(".localhost") ||
        host.all { it.isDigit() || it == '.' } || host.contains(':')
    return uri.scheme == "https" && uri.userInfo == null && uri.query == null &&
        uri.fragment == null && !local && uri.port == -1 && uri.path == "/api/v1"
}

fun resolveApiBaseUrl(
    override: String,
    isEmulator: Boolean,
    emulatorHost: String,
    deviceHost: String,
    port: String,
    allowLocal: Boolean = true,
): String {
    val base = override.trim()
    if (!allowLocal) {
        return if (isSecureApiBaseUrl(base)) base.trimEnd('/') + "/" else UNREACHABLE_API_BASE_URL
    }
    if (base.isNotEmpty()) {
        return if (base.endsWith("/")) base else "$base/"
    }
    val host = if (isEmulator) emulatorHost else deviceHost.ifBlank { emulatorHost }
    return "http://$host:$port/api/v1/"
}
