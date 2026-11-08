package com.vocabulario.app.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EnrichmentPollPolicyTest {

    @Test
    fun learnableDropsImmediatelyWhenInactive() {
        assertFalse(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.LEARNABLE,
                enrichmentActive = false,
                hasCardActivity = false,
                elapsedMillis = 0,
            )
        )
    }

    @Test
    fun learnableStaysWhileActiveUntilThreeMinutes() {
        val justUnder = EnrichmentPollPolicy.LEARNABLE_LIMIT_MS - 1
        assertTrue(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.LEARNABLE,
                enrichmentActive = true,
                hasCardActivity = false,
                elapsedMillis = justUnder,
            )
        )
        assertFalse(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.LEARNABLE,
                enrichmentActive = true,
                hasCardActivity = false,
                elapsedMillis = EnrichmentPollPolicy.LEARNABLE_LIMIT_MS,
            )
        )
    }

    @Test
    fun learnableWithoutActiveFlagUsesOnlyTheTimeLimit() {
        assertTrue(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.LEARNABLE,
                enrichmentActive = null,
                hasCardActivity = false,
                elapsedMillis = 0,
            )
        )
        assertFalse(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.LEARNABLE,
                enrichmentActive = null,
                hasCardActivity = false,
                elapsedMillis = EnrichmentPollPolicy.LEARNABLE_LIMIT_MS,
            )
        )
    }

    @Test
    fun pendingStaysUntilFiveMinutes() {
        assertTrue(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.PENDING,
                enrichmentActive = false,
                hasCardActivity = false,
                elapsedMillis = EnrichmentPollPolicy.OTHER_LIMIT_MS - 1,
            )
        )
        assertFalse(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.PENDING,
                enrichmentActive = null,
                hasCardActivity = false,
                elapsedMillis = EnrichmentPollPolicy.OTHER_LIMIT_MS,
            )
        )
    }

    @Test
    fun cardActivityKeepsPolling() {
        assertTrue(
            EnrichmentPollPolicy.shouldKeepPolling(
                status = EnrichmentStatus.LEARNABLE,
                enrichmentActive = false,
                hasCardActivity = true,
                elapsedMillis = EnrichmentPollPolicy.OTHER_LIMIT_MS,
            )
        )
    }
}
