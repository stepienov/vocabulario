package com.vocabulario.app.data.api

import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.local.TokenStore
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Odświeża access token zanim wygaśnie — bez czekania na 401 w logach BE.
 */
@Singleton
class TokenRefresher @Inject constructor(
    private val tokenStore: TokenStore,
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val lock = Any()
    private val refreshClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()

    fun accessTokenForRequest(): String? {
        val current = tokenStore.peekAccessToken() ?: return null
        if (!jwtIsExpiringSoon(current)) return current
        return synchronized(lock) {
            val newest = tokenStore.peekAccessToken() ?: return@synchronized null
            if (!jwtIsExpiringSoon(newest)) newest else refreshNow(clearOnFailure = false) ?: newest
        }
    }

    fun refreshIfUnauthorized(failedToken: String?): String? {
        val current = tokenStore.peekAccessToken()
        if (!current.isNullOrBlank() && current != failedToken) return current
        val refresh = tokenStore.peekRefreshToken()
        if (refresh.isNullOrBlank()) {
            tokenStore.clearMemory()
            return null
        }
        return synchronized(lock) {
            val newest = tokenStore.peekAccessToken()
            if (!newest.isNullOrBlank() && newest != failedToken) {
                newest
            } else {
                refreshNow(clearOnFailure = true)
            }
        }
    }

    private fun refreshNow(clearOnFailure: Boolean): String? {
        val refresh = tokenStore.peekRefreshToken()
        if (refresh.isNullOrBlank()) {
            if (clearOnFailure) tokenStore.clearMemory()
            return null
        }
        return try {
            val url = ApiBaseUrl.resolve().trimEnd('/') + "/auth/refresh"
            val bodyJson = json.encodeToString(
                RefreshRequest.serializer(),
                RefreshRequest(refresh_token = refresh),
            )
            val refreshRequest = Request.Builder()
                .url(url)
                .post(bodyJson.toRequestBody("application/json".toMediaType()))
                .build()
            refreshClient.newCall(refreshRequest).execute().use { refreshResponse ->
                if (!refreshResponse.isSuccessful) {
                    if (clearOnFailure) tokenStore.clearMemory()
                    return@use null
                }
                val payload = refreshResponse.body?.string().orEmpty()
                val tokens = runCatching {
                    json.decodeFromString(TokenResponse.serializer(), payload)
                }.getOrNull()
                if (tokens == null) {
                    if (clearOnFailure) tokenStore.clearMemory()
                    return@use null
                }
                tokenStore.saveTokensAsync(tokens.access_token, tokens.refresh_token)
                tokens.access_token
            }
        } catch (_: Exception) {
            if (clearOnFailure) tokenStore.clearMemory()
            null
        }
    }
}
