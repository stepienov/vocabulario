package com.vocabulario.app.data.api

import androidx.annotation.StringRes
import com.vocabulario.app.R
import com.vocabulario.app.i18n.UiStrings
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException
import java.util.Collections
import java.util.WeakHashMap

private val json = Json { ignoreUnknownKeys = true }

data class ParsedApiError(
    val code: String? = null,
    val message: String? = null,
)

private val httpErrorCache: MutableMap<HttpException, ParsedApiError> =
    Collections.synchronizedMap(WeakHashMap())

private val LOCAL_ERROR_CODES = setOf(
    "empty_list_name",
    "list_name_exists",
    "list_name_taken",
    "list_name_reserved",
    "pending_inbox_not_deletable",
    "pending_inbox_clear_incomplete",
    "offline",
    "offline_card",
    "no_inbox",
    "add_failed",
    "no_active_profile",
)

private val CODE_TO_RES: Map<String, Int> = mapOf(
    "email_taken" to R.string.err_email_taken,
    "invalid_credentials" to R.string.err_login_wrong_password,
    "email_not_found" to R.string.err_login_email_unknown,
    "wrong_password" to R.string.err_login_wrong_password,
    "google_login_required" to R.string.err_login_use_google,
    "invalid_google_token" to R.string.err_google_login,
    "invalid_refresh_token" to R.string.err_login,
    "not_authenticated" to R.string.err_login,
    "invalid_token" to R.string.err_login,
    "user_not_found" to R.string.err_login,
    "profile_not_found" to R.string.err_load_profile,
    "no_active_profile" to R.string.err_load_profile,
    "card_not_found" to R.string.err_load_cards,
    "list_not_found" to R.string.err_lists,
    "target_list_not_found" to R.string.err_lists,
    "word_already_on_list" to R.string.err_word_on_list,
    "empty_list_name" to R.string.err_empty_list_name,
    "list_name_reserved" to R.string.list_name_reserved,
    "list_name_exists" to R.string.list_name_taken,
    "list_name_taken" to R.string.list_name_taken,
    "list_not_editable" to R.string.err_list_not_editable,
    "list_not_deletable" to R.string.err_list_not_deletable,
    "import_empty" to R.string.err_import_empty,
    "import_preserve_no_url" to R.string.err_import,
    "correction_daily_limit" to R.string.correction_daily_limit,
    "pending_inbox_not_deletable" to R.string.err_pending_inbox_not_deletable,
    "pending_inbox_clear_incomplete" to R.string.err_pending_inbox_clear,
    "offline" to R.string.err_offline,
    "offline_card" to R.string.err_offline_card,
    "no_inbox" to R.string.err_no_inbox,
    "add_failed" to R.string.err_add,
)

private val DETAIL_ALIASES: Map<String, String> = mapOf(
    "email already registered" to "email_taken",
    "invalid credentials" to "invalid_credentials",
    "no account with this email" to "email_not_found",
    "wrong password" to "wrong_password",
    "this account uses google sign-in" to "google_login_required",
    "invalid google token" to "invalid_google_token",
    "invalid refresh token" to "invalid_refresh_token",
    "not authenticated" to "not_authenticated",
    "invalid token" to "invalid_token",
    "user not found" to "user_not_found",
    "profile not found" to "profile_not_found",
    "no active language profile" to "no_active_profile",
    "card not found" to "card_not_found",
    "karta nie znaleziona" to "card_not_found",
    "lista nie znaleziona" to "list_not_found",
    "lista docelowa nie znaleziona" to "target_list_not_found",
    "to słowo jest już na liście" to "word_already_on_list",
    "nazwa listy jest wymagana" to "empty_list_name",
    "ta nazwa jest zarezerwowana" to "list_name_reserved",
    "lista o tej nazwie już istnieje" to "list_name_exists",
    "tej listy nie można edytować" to "list_not_editable",
    "tej listy nie można usunąć" to "list_not_deletable",
    "brak słów do zaimportowania" to "import_empty",
    "brak karty offline" to "offline_card",
    "card not in cache" to "offline_card",
    "tryb \"zachowaj fiszki\" działa z wklejką/plikiem, nie z url." to "import_preserve_no_url",
)

fun Throwable.userMessage(strings: UiStrings, @StringRes defaultRes: Int): String {
    val mapped = mappedErrorRes()
    return strings.get(mapped ?: defaultRes)
}

fun Throwable.userMessage(default: String, strings: UiStrings): String {
    val mapped = mappedErrorRes()
    return if (mapped != null) strings.get(mapped) else default
}

fun Throwable.mappedErrorRes(): Int? {
    val parsed = if (this is HttpException) readApiError() else null
    val code = resolveErrorCode(
        httpStatus = (this as? HttpException)?.code(),
        apiCode = parsed?.code,
        apiMessage = parsed?.message,
        throwableMessage = message,
    )
    return code?.let { CODE_TO_RES[it] }
}

internal fun resolveErrorCode(
    httpStatus: Int? = null,
    apiCode: String? = null,
    apiMessage: String? = null,
    throwableMessage: String? = null,
): String? {
    val fromApi = apiCode?.trim()?.lowercase()?.takeIf { it.isNotEmpty() }
    if (fromApi != null && fromApi in CODE_TO_RES) return fromApi

    val local = throwableMessage?.trim()?.takeIf { it in LOCAL_ERROR_CODES }
    if (local != null) return if (local == "list_name_exists") "list_name_taken" else local

    val folded = foldErrorText(apiMessage ?: throwableMessage)
    if (folded.isNotEmpty()) {
        DETAIL_ALIASES[folded]?.let { return it }
        DETAIL_ALIASES.entries.firstOrNull { (alias, _) ->
            folded == alias || folded.startsWith("$alias:") || folded.startsWith("$alias ")
        }?.let { return it.value }
    }

    return when (httpStatus) {
        429 -> "correction_daily_limit"
        else -> null
    }
}

internal fun foldErrorText(raw: String?): String {
    if (raw.isNullOrBlank()) return ""
    return raw.trim().lowercase()
        .replace('„', '"')
        .replace('”', '"')
        .replace('“', '"')
        .replace('’', '\'')
        .replace('‘', '\'')
}

/** Reads error body once; subsequent calls reuse the cache. */
private fun HttpException.readApiError(): ParsedApiError {
    httpErrorCache[this]?.let { return it }
    val body = response()?.errorBody()?.string()
    val parsed = if (body.isNullOrBlank()) {
        ParsedApiError()
    } else {
        parseApiError(body) ?: ParsedApiError()
    }
    httpErrorCache[this] = parsed
    return parsed
}

internal fun parseApiError(body: String): ParsedApiError? {
    return runCatching {
        val element = json.parseToJsonElement(body)
        if (element !is JsonObject) return@runCatching null
        when (val detail = element["detail"]) {
            is JsonArray -> ParsedApiError()
            is JsonObject -> ParsedApiError(
                code = detail["code"]?.jsonPrimitive?.content,
                message = detail["message"]?.jsonPrimitive?.content
                    ?: detail["code"]?.jsonPrimitive?.content,
            )
            null -> null
            else -> ParsedApiError(message = detail.jsonPrimitive.content)
        }
    }.getOrNull()
}
