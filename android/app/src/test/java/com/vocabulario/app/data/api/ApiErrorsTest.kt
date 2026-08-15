package com.vocabulario.app.data.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ApiErrorsTest {

    @Test
    fun prefersApiCodeOverMessage() {
        assertEquals(
            "email_taken",
            resolveErrorCode(httpStatus = 409, apiCode = "email_taken", apiMessage = "Email already registered"),
        )
    }

    @Test
    fun mapsLoginFailures() {
        assertEquals("email_not_found", resolveErrorCode(httpStatus = 401, apiCode = "email_not_found"))
        assertEquals("wrong_password", resolveErrorCode(httpStatus = 401, apiCode = "wrong_password"))
        assertEquals(
            "email_not_found",
            resolveErrorCode(httpStatus = 401, apiMessage = "No account with this email"),
        )
        assertEquals("wrong_password", resolveErrorCode(httpStatus = 401, apiMessage = "Wrong password"))
        assertEquals(
            "google_login_required",
            resolveErrorCode(httpStatus = 401, apiMessage = "This account uses Google sign-in"),
        )
        assertEquals(
            "invalid_credentials",
            resolveErrorCode(httpStatus = 401, apiMessage = "Invalid credentials"),
        )
    }

    @Test
    fun mapsLegacyPolishDetail() {
        assertEquals(
            "list_name_exists",
            resolveErrorCode(httpStatus = 409, apiMessage = "Lista o tej nazwie już istnieje"),
        )
        assertEquals(
            "empty_list_name",
            resolveErrorCode(apiMessage = "Nazwa listy jest wymagana"),
        )
        assertEquals(
            "word_already_on_list",
            resolveErrorCode(apiMessage = "To słowo jest już na liście"),
        )
    }

    @Test
    fun mapsLocalErrorCodes() {
        assertEquals("offline_card", resolveErrorCode(throwableMessage = "offline_card"))
        assertEquals("list_name_taken", resolveErrorCode(throwableMessage = "list_name_exists"))
        assertEquals("no_active_profile", resolveErrorCode(throwableMessage = "no_active_profile"))
    }

    @Test
    fun mapsDailyLimitByStatus() {
        assertEquals("correction_daily_limit", resolveErrorCode(httpStatus = 429))
    }

    @Test
    fun ignoresUnknownBackendText() {
        assertNull(resolveErrorCode(httpStatus = 400, apiMessage = "Some internal English dump"))
        assertNull(resolveErrorCode(throwableMessage = "HTTP 500"))
    }

    @Test
    fun parseCodedDetail() {
        val parsed = parseApiError("""{"detail":{"code":"list_name_taken","message":"Lista o tej nazwie już istnieje"}}""")
        assertEquals("list_name_taken", parsed?.code)
    }

    @Test
    fun parsePlainDetailString() {
        val parsed = parseApiError("""{"detail":"Email already registered"}""")
        assertEquals("Email already registered", parsed?.message)
        assertNull(parsed?.code)
    }

    @Test
    fun foldsPolishQuotesInPreserveImportMessage() {
        assertEquals(
            "import_preserve_no_url",
            resolveErrorCode(apiMessage = "Tryb „zachowaj fiszki” działa z wklejką/plikiem, nie z URL."),
        )
    }
}
