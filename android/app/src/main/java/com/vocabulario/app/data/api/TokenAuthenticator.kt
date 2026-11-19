package com.vocabulario.app.data.api

import com.vocabulario.app.data.session.SessionCoordinator
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Singleton

private val PUBLIC_AUTH_SUFFIXES = listOf(
    "/auth/register",
    "/auth/login",
    "/auth/google",
    "/auth/google/challenge",
    "/auth/refresh",
    "/auth/logout",
    "/auth/password-reset/request",
    "/account-deletion/proof/password",
    "/account-deletion/google/challenge",
    "/account-deletion/proof/google",
    "/account-deletion/request",
    "/account-deletion/status",
    "/account-deletion/cancel",
)

/** Publiczne operacje auth: bez Bearer i bez refresh po 401 (np. błędne hasło to nie koniec sesji). */
internal fun isPublicAuthPath(encodedPath: String): Boolean {
    val path = encodedPath.trimEnd('/')
    return PUBLIC_AUTH_SUFFIXES.any { path.endsWith(it) }
}

/**
 * Po 401 jedna próba wspólnego refresh i jedno ponowienie żądania. Nieudany refresh
 * nie czyści sesji — o odwołaniu decyduje [SessionCoordinator].
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val sessionCoordinator: SessionCoordinator,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.priorResponse != null) return null
        if (isPublicAuthPath(response.request.url.encodedPath)) return null

        val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")?.trim()
        val fresh = sessionCoordinator.refreshAfterUnauthorized(failedToken) ?: return null
        return response.request.newBuilder()
            .header("Authorization", "Bearer $fresh")
            .build()
    }
}
