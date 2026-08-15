package com.vocabulario.app.data

import android.os.Build
import com.vocabulario.app.BuildConfig

/**
 * Emulator → [BuildConfig.API_EMULATOR_HOST] (domyślnie 10.0.2.2).
 * Fizyczny telefon → [BuildConfig.API_DEVICE_HOST] z `android/local.properties`
 * (`api.device.host=192.168.x.x`).
 */
object ApiBaseUrl {
    fun resolve(): String {
        val host = if (isEmulator()) {
            BuildConfig.API_EMULATOR_HOST
        } else {
            BuildConfig.API_DEVICE_HOST.ifBlank { BuildConfig.API_EMULATOR_HOST }
        }
        return "http://$host:${BuildConfig.API_PORT}/api/v1/"
    }

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
