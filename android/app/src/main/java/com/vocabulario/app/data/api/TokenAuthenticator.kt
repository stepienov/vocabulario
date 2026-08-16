package com.vocabulario.app.data.api

import com.vocabulario.app.data.local.TokenStore
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Fallback gdy access token jednak wygasł w locie. Jak refresh się nie uda — czyści sesję.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenStore: TokenStore,
    private val tokenRefresher: TokenRefresher,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) {
            tokenStore.clearMemory()
            return null
        }
        val path = response.request.url.encodedPath
        if (path.contains("/auth/")) return null

        val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")?.trim()
        val fresh = tokenRefresher.refreshIfUnauthorized(failedToken) ?: return null
        return response.request.newBuilder()
            .header("Authorization", "Bearer $fresh")
            .build()
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
