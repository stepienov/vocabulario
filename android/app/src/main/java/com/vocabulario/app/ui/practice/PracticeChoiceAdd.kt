package com.vocabulario.app.ui.practice

import com.vocabulario.app.data.api.ChoiceOption
import com.vocabulario.app.data.containsLemma

fun ChoiceOption.quizAddLemma(): String? =
    lemma_l2?.trim()?.takeIf { it.isNotEmpty() }

/**
 * Plus only after the user picked this option and it was revealed as wrong.
 * Showing it earlier would mark distractors (and leak the correct answer).
 */
fun ChoiceOption.showQuizAdd(
    revealedWrong: Boolean,
    learningLemmas: Set<String>,
): Boolean {
    if (!revealedWrong || is_correct) return false
    val lemma = quizAddLemma() ?: return false
    return !in_learning && !learningLemmas.containsLemma(lemma)
}