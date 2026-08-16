package com.vocabulario.app.data.api

import java.util.Base64

private const val EXP_SKEW_SECONDS = 90L

internal fun jwtExpiresAtEpochSeconds(token: String): Long? {
    val payload = token.split('.').getOrNull(1) ?: return null
    val padded = payload + "=".repeat((4 - payload.length % 4) % 4)
    val json = runCatching {
        String(Base64.getUrlDecoder().decode(padded), Charsets.UTF_8)
    }.getOrNull() ?: return null
    return Regex("\"exp\"\\s*:\\s*(\\d+)").find(json)?.groupValues?.get(1)?.toLongOrNull()
}

internal fun jwtIsExpiringSoon(
    token: String,
    nowEpochSeconds: Long = System.currentTimeMillis() / 1000,
    skewSeconds: Long = EXP_SKEW_SECONDS,
): Boolean {
    val exp = jwtExpiresAtEpochSeconds(token) ?: return false
    return exp <= nowEpochSeconds + skewSeconds
}
