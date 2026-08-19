package com.vocabulario.app.data

/**
 * L2 lemma to persist when the user adds a quiz option.
 * L2→L1 shows an L1 gloss as [optionText]; never treat that gloss as a lemma.
 */
fun distractorLemmaL2(direction: String, knownLemma: String?, optionText: String): String? {
    knownLemma?.trim()?.takeIf { it.isNotEmpty() }?.let { return it }
    if (direction.equals("l2_to_l1", ignoreCase = true)) return null
    return optionText.trim().takeIf { it.isNotEmpty() }
}
