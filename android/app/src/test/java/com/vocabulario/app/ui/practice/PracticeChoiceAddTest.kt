package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.RelatedMembership
import com.vocabulario.app.data.RelatedMembershipIndex
import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.lemmaKeys
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

    @Test
    fun onListHiddenUntilRevealedWrong() {
        val learned = wrong(text = "pensativo", lemma = "pensativo", inLearning = true)
        assertFalse(learned.showQuizOnList(revealedWrong = false, learningLemmas = emptySet()))
        assertTrue(learned.showQuizOnList(revealedWrong = true, learningLemmas = emptySet()))
        assertNull(learned.quizListChipLabel(false, emptySet(), RelatedMembershipIndex.Empty, "Uczę się"))
        assertEquals(
            "Uczę się",
            learned.quizListChipLabel(true, emptySet(), RelatedMembershipIndex.Empty, "Uczę się"),
        )
    }

    @Test
    fun onListHiddenForCorrectAnswer() {
        val correct = ChoiceOption(
            text = "limitado",
            lemma_l2 = "limitado",
            in_learning = true,
            is_correct = true,
        )
        assertFalse(correct.showQuizOnList(revealedWrong = true, learningLemmas = emptySet()))
        assertNull(correct.quizListChipLabel(true, emptySet(), RelatedMembershipIndex.Empty, "Uczę się"))
    }

    @Test
    fun onListUsesCustomListNameFromMembership() {
        val choice = wrong(text = "torpe", lemma = "torpe", pos = "adj")
        val membership = RelatedMembershipIndex(
            listOf(
                RelatedMembership(
                    displayLemma = "torpe",
                    listName = "Przymiotniki",
                    isSystemList = false,
                    cardId = "c1",
                    pos = "adj",
                    lemmaKeys = lemmaKeys("torpe"),
                ),
            ),
        )
        assertEquals(
            "Przymiotniki",
            choice.quizListChipLabel(true, emptySet(), membership, "Uczę się"),
        )
    }

    @Test
    fun onListUsesLocalizedSystemListName() {
        val choice = wrong(text = "específico", lemma = "específico", pos = "adj", inLearning = true)
        val membership = RelatedMembershipIndex(
            listOf(
                RelatedMembership(
                    displayLemma = "específico",
                    listName = "Learning",
                    isSystemList = true,
                    cardId = "c1",
                    pos = "adj",
                    lemmaKeys = lemmaKeys("específico"),
                ),
            ),
        )
        assertEquals(
            "Uczę się",
            choice.quizListChipLabel(true, emptySet(), membership, "Uczę się"),
        )
    }

    private fun wrong(
        text: String,
        lemma: String?,
        inLearning: Boolean = false,
        pos: String? = null,
    ) = ChoiceOption(
        text = text,
        lemma_l2 = lemma,
        gloss = text,
        pos = pos,
        in_learning = inLearning,
        is_correct = false,
    )
}
