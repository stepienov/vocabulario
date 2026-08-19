package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.api.ChoiceOption
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PracticeChoiceAddTest {

    @Test
    fun plusUsesLemmaNotDisplayedL1Gloss() {
        val choice = wrong(text = "pasek", lemma = "la correa")
        assertEquals("la correa", choice.quizAddLemma())
    }

    @Test
    fun plusHiddenUntilRevealedWrong() {
        val choice = wrong(text = "pasek", lemma = "la tira")
        assertFalse(choice.showQuizAdd(revealedWrong = false, learningLemmas = emptySet()))
        assertTrue(choice.showQuizAdd(revealedWrong = true, learningLemmas = emptySet()))
    }

    @Test
    fun plusHiddenWhenLemmaMissing() {
        val choice = wrong(text = "pasek", lemma = null)
        assertNull(choice.quizAddLemma())
        assertFalse(choice.showQuizAdd(revealedWrong = true, learningLemmas = emptySet()))
    }

    @Test
    fun plusHiddenForCorrectAndAlreadyLearned() {
        val correct = ChoiceOption(
            text = "la correa",
            lemma_l2 = "la correa",
            in_learning = true,
            is_correct = true,
        )
        val learned = wrong(text = "el cinturón", lemma = "el cinturón", inLearning = true)
        assertFalse(correct.showQuizAdd(revealedWrong = true, learningLemmas = emptySet()))
        assertFalse(learned.showQuizAdd(revealedWrong = true, learningLemmas = emptySet()))
        assertFalse(
            wrong(text = "la tira", lemma = "la tira")
                .showQuizAdd(revealedWrong = true, learningLemmas = setOf("la tira")),
        )
    }

    private fun wrong(
        text: String,
        lemma: String?,
        inLearning: Boolean = false,
    ) = ChoiceOption(
        text = text,
        lemma_l2 = lemma,
        gloss = text,
        in_learning = inLearning,
        is_correct = false,
    )
}
