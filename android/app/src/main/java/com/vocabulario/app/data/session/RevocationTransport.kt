package com.vocabulario.app.data.session

import com.vocabulario.app.BuildConfig
import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.CLIENT_VERSION_HEADER
import com.vocabulario.app.data.api.LogoutRequest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/** `POST /auth/logout` bez Bearer i bez interceptorów sesji (działa także w SignedOut). */
interface RevocationTransport {
    fun logout(refreshToken: String): LogoutHttpResult
}

@Singleton
class OkHttpRevocationTransport @Inject constructor() : RevocationTransport {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()
    private val json = Json { encodeDefaults = true }

    override fun logout(refreshToken: String): LogoutHttpResult {
        val url = ApiBaseUrl.resolve().trimEnd('/') + "/auth/logout"
        val body = json.encodeToString(LogoutRequest.serializer(), LogoutRequest(refreshToken))
        val request = Request.Builder()
            .url(url)
            .header(CLIENT_VERSION_HEADER, BuildConfig.VERSION_CODE.toString())
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                classifyLogoutResponse(response.code, response.body?.string().orEmpty(), response.header("Retry-After"))
            }
        } catch (e: IOException) {
            LogoutHttpResult.Transient("network")
        }
    }
}

data class RevocationReport(val retryNeeded: Boolean, val nextDeferredAtMs: Long?)

/**
 * Wysyła oczekujące zlecenia. Kolejność wg T-002 §5: najpierw odzyskanie nieznanej rotacji
 * tym samym pending input/ID, potem logout. Tylko 204 (lub `session_revoked` przy odzyskaniu)
 * usuwa zlecenie jako potwierdzone; inne definitywne odmowy kończą się „niepotwierdzonym”.
 */
@Singleton
class RevocationProcessor @Inject constructor(
    private val store: RevocationStore,
    private val logoutTransport: RevocationTransport,
    private val refreshTransport: RefreshTransport,
    private val clock: WallClock,
) {
    private val lock = Any()

    fun processDue(): RevocationReport = synchronized(lock) {
        var retryNeeded = false
        for (request in store.due()) {
            val handled = runCatching { process(request) }.getOrDefault(false)
            if (!handled) retryNeeded = true
        }
        RevocationReport(retryNeeded, store.nextDeferredAtMs())
    }

    /** Zwraca false, gdy zlecenie trzeba ponowić z backoffem. */
    private fun process(request: RevocationRequest): Boolean {
        var refresh = request.refreshToken
        val pending = request.pendingRefresh
        if (pending != null) {
            when (val recovered = safeRefresh(pending)) {
                is RefreshHttpResult.Transient -> return false
                is RefreshHttpResult.Ok -> {
                    val rotated = recovered.tokens.refresh_token.takeIf { it.isNotBlank() } ?: return false
                    // Para z odzyskania trafia wyłącznie do zlecenia, zanim użyjemy jej do logout.
                    store.update(request.id) { it.copy(refreshToken = rotated, pendingRefresh = null) }
                    refresh = rotated
                }
                is RefreshHttpResult.Rejected -> {
                    if (recovered.code == "session_revoked") {
                        store.update(request.id) { null }
                        return true
                    }
                    store.update(request.id) { it.copy(pendingRefresh = null) }
                }
            }
        }
        val proof = refresh?.takeIf { it.isNotBlank() } ?: run {
            store.update(request.id) { it.unconfirmed(REVOCATION_REASON_INVALID) }
            return true
        }
        return when (val result = safeLogout(proof)) {
            LogoutHttpResult.Revoked -> {
                store.update(request.id) { null }
                true
            }
            is LogoutHttpResult.Invalid -> {
                store.update(request.id) { it.unconfirmed(REVOCATION_REASON_INVALID) }
                true
            }
            is LogoutHttpResult.RetryAfter -> {
                store.update(request.id) { it.copy(notBeforeMs = nowPlus(result.delayMs)) }
                true
            }
            is LogoutHttpResult.Transient -> false
        }
    }

    private fun nowPlus(delayMs: Long): Long = clock.nowMs() + delayMs

    private fun safeRefresh(pending: PendingRefresh): RefreshHttpResult =
        try {
            refreshTransport.refresh(pending.inputRefresh, pending.requestId)
        } catch (e: Exception) {
            RefreshHttpResult.Transient("transport")
        }

    private fun safeLogout(refresh: String): LogoutHttpResult =
        try {
            logoutTransport.logout(refresh)
        } catch (e: Exception) {
            LogoutHttpResult.Transient("transport")
        }
}
