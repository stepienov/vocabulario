package com.vocabulario.app.data

import java.net.URI

enum class AccountLinkKind { VERIFY, RESET }

class AccountLink(val kind: AccountLinkKind, val token: String)

internal fun parseAccountLink(value: String?): AccountLink? {
    val uri = try {
        URI(value ?: return null)
    } catch (_: IllegalArgumentException) {
        return null
    } catch (_: java.net.URISyntaxException) {
        return null
    }
    if (uri.scheme != "https" || uri.host != "vocabulario.io" || uri.port != -1 || uri.userInfo != null) {
        return null
    }
    val kind = when (uri.rawPath) {
        "/account/verify-email" -> AccountLinkKind.VERIFY
        "/account/reset-password" -> AccountLinkKind.RESET
        else -> return null
    }
    val match = Regex("^token=([A-Za-z0-9_-]{1,512})$").matchEntire(uri.rawFragment ?: return null)
        ?: return null
    return AccountLink(kind, match.groupValues[1])
}
