package com.vocabulario.app.data.api

import com.vocabulario.app.BuildConfig
import com.vocabulario.app.data.local.TokenStore
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Przy 401 próbuje /auth/refresh. Jak się nie uda — czyści sesję w pamięci.
 * Bez runBlocking — nie wolno blokować wątku OkHttp/Main (ANR emulera).
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenStore: TokenStore,
) : Authenticator {

    private val json = Json { ignoreUnknownKeys = true }

    private val refreshClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) {
            tokenStore.clearMemory()
            return null
        }

        val path = response.request.url.encodedPath
        if (path.contains("/auth/")) return null

        val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")?.trim()
        val current = tokenStore.peekAccessToken()
        if (!current.isNullOrBlank() && current != failedToken) {
            return response.request.newBuilder()
                .header("Authorization", "Bearer $current")
                .build()
        }

        val refresh = tokenStore.peekRefreshToken()
        if (refresh.isNullOrBlank()) {
            tokenStore.clearMemory()
            return null
        }

        synchronized(this) {
            val newest = tokenStore.peekAccessToken()
            if (!newest.isNullOrBlank() && newest != failedToken) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $newest")
                    .build()
            }

            return try {
                val url = BuildConfig.API_BASE_URL.trimEnd('/') + "/auth/refresh"
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
                        tokenStore.clearMemory()
                        return@use null
                    }
                    val payload = refreshResponse.body?.string().orEmpty()
                    val tokens = runCatching {
                        json.decodeFromString(TokenResponse.serializer(), payload)
                    }.getOrNull()
                    if (tokens == null) {
                        tokenStore.clearMemory()
                        return@use null
                    }
                    tokenStore.saveTokensAsync(tokens.access_token, tokens.refresh_token)
                    response.request.newBuilder()
                        .header("Authorization", "Bearer ${tokens.access_token}")
                        .build()
                }
            } catch (_: Exception) {
                tokenStore.clearMemory()
                null
            }
        }
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
