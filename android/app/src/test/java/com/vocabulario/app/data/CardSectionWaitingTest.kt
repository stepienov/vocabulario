package com.vocabulario.app.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CardSectionWaitingTest {

    @Test
    fun meaningsSpinnerOnlyBeforeLearnableWhilePolling() {
        assertTrue(
            CardSectionWaiting.meanings(
                hasMeaningContent = false,
                status = EnrichmentStatus.PENDING,
                stillPolling = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.meanings(
                hasMeaningContent = false,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.meanings(
                hasMeaningContent = true,
                status = EnrichmentStatus.PENDING,
                stillPolling = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.meanings(
                hasMeaningContent = false,
                status = EnrichmentStatus.PENDING,
                stillPolling = false,
            ),
        )
    }

    @Test
    fun relatedSpinnerRespectsRelatedPending() {
        assertTrue(
            CardSectionWaiting.related(
                isEmpty = true,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
                relatedPending = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.related(
                isEmpty = true,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
                relatedPending = false,
            ),
        )
        assertTrue(
            CardSectionWaiting.related(
                isEmpty = true,
                status = EnrichmentStatus.PREPARING,
                stillPolling = true,
                relatedPending = null,
            ),
        )
        assertFalse(
            CardSectionWaiting.related(
                isEmpty = true,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
                relatedPending = null,
            ),
        )
        assertFalse(
            CardSectionWaiting.related(
                isEmpty = false,
                status = EnrichmentStatus.PENDING,
                stillPolling = true,
                relatedPending = true,
            ),
        )
    }

    @Test
    fun inflectionSpinnerWhileNotReadyAndPolling() {
        assertTrue(
            CardSectionWaiting.inflection(
                hasInflection = false,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
            ),
        )
        assertTrue(
            CardSectionWaiting.inflection(
                hasInflection = false,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = false,
                expectInflection = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.inflection(
                hasInflection = false,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = false,
                expectInflection = false,
            ),
        )
        assertFalse(
            CardSectionWaiting.inflection(
                hasInflection = true,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.inflection(
                hasInflection = false,
                status = EnrichmentStatus.READY,
                stillPolling = false,
            ),
        )
    }

    @Test
    fun relatedSpinnerWithoutPollingWhenRelatedPending() {
        assertTrue(
            CardSectionWaiting.related(
                isEmpty = true,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = false,
                relatedPending = true,
            ),
        )
    }

    @Test
    fun examplesSpinnerRespectsExamplesPending() {
        assertTrue(
            CardSectionWaiting.examples(
                hasExamples = false,
                status = EnrichmentStatus.PREPARING,
                stillPolling = true,
                examplesPending = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.examples(
                hasExamples = true,
                status = EnrichmentStatus.PREPARING,
                stillPolling = true,
                examplesPending = true,
            ),
        )
        assertFalse(
            CardSectionWaiting.examples(
                hasExamples = false,
                status = EnrichmentStatus.PREPARING,
                stillPolling = true,
                examplesPending = false,
            ),
        )
        assertTrue(
            CardSectionWaiting.examples(
                hasExamples = false,
                status = EnrichmentStatus.PENDING,
                stillPolling = true,
                examplesPending = null,
            ),
        )
        assertFalse(
            CardSectionWaiting.examples(
                hasExamples = false,
                status = EnrichmentStatus.LEARNABLE,
                stillPolling = true,
                examplesPending = null,
            ),
        )
    }
}
