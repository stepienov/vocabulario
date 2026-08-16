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

fun resolveApiBaseUrl(
    override: String,
    isEmulator: Boolean,
    emulatorHost: String,
    deviceHost: String,
    port: String,
): String {
    val base = override.trim()
    if (base.isNotEmpty()) {
        return if (base.endsWith("/")) base else "$base/"
    }
    val host = if (isEmulator) emulatorHost else deviceHost.ifBlank { emulatorHost }
    return "http://$host:$port/api/v1/"
}
