package com.vocabulario.app.data.api

import com.vocabulario.app.data.CLIENT_VERSION_HEADER
import com.vocabulario.app.di.AppModule
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import retrofit2.HttpException

class CandidateProfilesApiTest {
    @Test
    fun profileVerificationUsesCandidateToken() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(
                MockResponse().setBody(
                    """[{"id":"p1","app_lang":"pl","learning_lang":"en","cefr_level":"A2","selected_tenses":[],"is_active":true}]""",
                ),
            )
            val api = AppModule.candidateProfilesApi(server.url("/api/v1/").toString())
            assertEquals(listOf("p1"), api.listProfiles("Bearer candidate-token").map { it.id })
            val request = server.takeRequest()
            assertEquals("/api/v1/profiles", request.path)
            assertEquals("Bearer candidate-token", request.getHeader("Authorization"))
            assertEquals(com.vocabulario.app.BuildConfig.VERSION_CODE.toString(), request.getHeader(CLIENT_VERSION_HEADER))
            assertNull(request.getHeader("Cookie"))
        }
    }

    @Test(expected = HttpException::class)
    fun profileVerificationSurfacesServerFailure(): Unit = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setResponseCode(503))
            AppModule.candidateProfilesApi(server.url("/api/v1/").toString())
                .listProfiles("Bearer candidate-token")
        }
    }
}
