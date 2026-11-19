package com.vocabulario.app.data.deletion

import com.vocabulario.app.data.api.DeletionView
import com.vocabulario.app.data.session.SessionCipher
import com.vocabulario.app.ui.deletion.formatDeletionInstant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId
import java.util.Locale

class AccountDeletionTest {

    private object XorCipher : SessionCipher {
        override fun encrypt(plain: ByteArray) = ByteArray(plain.size) { (plain[it].toInt() xor 0x5A).toByte() }
        override fun decrypt(blob: ByteArray) = encrypt(blob)
    }

    @Test
    fun secretIs43UrlSafeCharsAndUnique() {
        val a = newSecret32()
        val b = newSecret32()
        assertEquals(43, a.length)
        assertTrue(a.all { it.isLetterOrDigit() || it == '-' || it == '_' })
        assertNotEquals(a, b)
    }

    @Test
    fun receiptSurvivesEncryptedRoundTrip() {
        val codec = DeletionReceiptCodec(XorCipher)
        val receipt = DeletionReceipt(
            requestId = "r", statusSecret = "s", email = "a@b.c", userId = "u", cancelRequestId = "c",
            deletion = DeletionView("d", "grace", "2026-01-01T10:00:00Z", "2026-01-08T10:00:00Z", "2026-01-15T10:00:00Z", true),
        )
        val stored = codec.encode(receipt)
        assertTrue(!stored.contains("a@b.c"))
        assertEquals(receipt, codec.decode(stored))
    }

    @Test
    fun corruptedReceiptDecodesToNull() {
        assertNull(DeletionReceiptCodec(XorCipher).decode("not-base64!!"))
    }

    @Test
    fun instantIsFormattedInDeviceZoneOrKeptOnParseError() {
        val formatted = formatDeletionInstant("2026-01-08T23:30:00Z", ZoneId.of("Europe/Warsaw"), Locale.ENGLISH)
        assertNotNull(formatted)
        assertTrue(formatted.contains("9") && formatted.contains("2026"))
        assertEquals("garbage", formatDeletionInstant("garbage", ZoneId.of("UTC"), Locale.ENGLISH))
    }
}
