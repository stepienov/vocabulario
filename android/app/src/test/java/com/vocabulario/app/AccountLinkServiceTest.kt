package com.vocabulario.app

import com.vocabulario.app.data.AccountLink
import com.vocabulario.app.data.AccountLinkKind
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AccountLinkServiceTest {
    @Test
    fun confirmationUsesOnlyItsTokenAndNeverAUserSession() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
            val service = AccountLinkService(server.url("/api/v1/auth/"), OkHttpClient())
            val result = service.submit(AccountLink(AccountLinkKind.VERIFY, "token_123"), "")
            val request = server.takeRequest()
            assertNull(result)
            assertEquals("POST", request.method)
            assertEquals("/api/v1/auth/email-verification/confirm", request.path)
            assertNull(request.getHeader("Authorization"))
            assertNull(request.getHeader("Cookie"))
            assertEquals("""{"token":"token_123"}""", request.body.readUtf8())
        }
    }

    @Test
    fun resetSendsPasswordAndSurfacesInvalidPassword() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(
                MockResponse().setResponseCode(422)
                    .setBody("""{"detail":{"code":"password_invalid_unicode"}}"""),
            )
            val service = AccountLinkService(server.url("/api/v1/auth/"), OkHttpClient())
            val result = service.submit(AccountLink(AccountLinkKind.RESET, "abc"), "a long password")
            val request = server.takeRequest()
            assertEquals(R.string.err_password_invalid_chars, result)
            assertEquals("/api/v1/auth/password-reset/confirm", request.path)
            assertEquals("""{"token":"abc","new_password":"a long password"}""", request.body.readUtf8())
        }
    }

}
