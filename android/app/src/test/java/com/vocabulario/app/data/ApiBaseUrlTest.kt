package com.vocabulario.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class ApiBaseUrlTest {
    @Test
    fun localEmulatorUsesLoopbackAlias() {
        assertEquals(
            "http://10.0.2.2:8000/api/v1/",
            resolveApiBaseUrl(
                override = "",
                isEmulator = true,
                emulatorHost = "10.0.2.2",
                deviceHost = "192.168.1.45",
                port = "8000",
            ),
        )
    }

    @Test
    fun localDeviceUsesLanHost() {
        assertEquals(
            "http://192.168.1.45:8000/api/v1/",
            resolveApiBaseUrl(
                override = "",
                isEmulator = false,
                emulatorHost = "10.0.2.2",
                deviceHost = "192.168.1.45",
                port = "8000",
            ),
        )
    }

    @Test
    fun railwayOverrideWinsAndGetsTrailingSlash() {
        assertEquals(
            "https://vocabulario.up.railway.app/api/v1/",
            resolveApiBaseUrl(
                override = "https://vocabulario.up.railway.app/api/v1",
                isEmulator = false,
                emulatorHost = "10.0.2.2",
                deviceHost = "192.168.1.45",
                port = "8000",
            ),
        )
    }

    @Test
    fun releaseAcceptsOnlySecurePublicApiUrl() {
        fun release(override: String) = resolveApiBaseUrl(
            override = override,
            isEmulator = false,
            emulatorHost = "10.0.2.2",
            deviceHost = "192.168.1.45",
            port = "8000",
            allowLocal = false,
        )
        assertEquals("https://api.example.com/api/v1/", release("https://api.example.com/api/v1"))
        listOf(
            "",
            "http://api.example.com/api/v1",
            "https://10.0.2.2/api/v1",
            "https://localhost/api/v1",
            "https://user:pw@api.example.com/api/v1",
            "https://api.example.com/api/v1?x=1",
            "https://api.example.com/other",
            "https://api.example.com:8443/api/v1",
        ).forEach { assertEquals(it, UNREACHABLE_API_BASE_URL, release(it)) }
    }
}
