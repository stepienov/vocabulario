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
}
