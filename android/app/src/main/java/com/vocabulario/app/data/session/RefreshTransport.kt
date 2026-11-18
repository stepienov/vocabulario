package com.vocabulario.app.data.session

import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.api.RefreshRequest
import com.vocabulario.app.data.api.TokenResponse
import com.vocabulario.app.data.api.parseApiError
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

sealed interface RefreshHttpResult {
    data class Ok(val tokens: TokenResponse) : RefreshHttpResult

    /** Serwer jednoznacznie odrzucił refresh (401 ze znanym kodem lub 409 `refresh_conflict`). */
    data class Rejected(val code: String) : RefreshHttpResult

    /** Timeout, brak sieci, 429, 5xx lub wadliwa odpowiedź — nie dowodzi odwołania sesji. */
    data class Transient(val detail: String) : RefreshHttpResult
}

interface RefreshTransport {
    fun refresh(inputRefresh: String, requestId: String): RefreshHttpResult
}

internal const val CODE_REFRESH_CONFLICT = "refresh_conflict"

internal val REFRESH_REJECTION_CODES = setOf(
    "session_revoked",
    "session_expired",
    "session_upgrade_required",
    "invalid_refresh_token",
    "invalid_token",
)

internal fun classifyRefreshResponse(httpStatus: Int, body: String): RefreshHttpResult {
    if (httpStatus in 200..299) {
        val tokens = runCatching { transportJson.decodeFromString(TokenResponse.serializer(), body) }.getOrNull()
        return if (tokens != null) RefreshHttpResult.Ok(tokens) else RefreshHttpResult.Transient("malformed_body")
    }
    val code = parseApiError(body)?.code?.trim()?.lowercase()
    return when {
        httpStatus == 401 && code in REFRESH_REJECTION_CODES -> RefreshHttpResult.Rejected(code!!)
        httpStatus == 409 && code == CODE_REFRESH_CONFLICT -> RefreshHttpResult.Rejected(code)
        else -> RefreshHttpResult.Transient("http_$httpStatus")
    }
}

private val transportJson = Json { ignoreUnknownKeys = true }

@Singleton
class OkHttpRefreshTransport @Inject constructor() : RefreshTransport {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()

    override fun refresh(inputRefresh: String, requestId: String): RefreshHttpResult {
        val url = ApiBaseUrl.resolve().trimEnd('/') + "/auth/refresh"
        val body = transportJson.encodeToString(
            RefreshRequest.serializer(),
            RefreshRequest(refresh_token = inputRefresh, request_id = requestId),
        )
        val request = Request.Builder()
            .url(url)
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                classifyRefreshResponse(response.code, response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            RefreshHttpResult.Transient("network")
        }
    }
}
