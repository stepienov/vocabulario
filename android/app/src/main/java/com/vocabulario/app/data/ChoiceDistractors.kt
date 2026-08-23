package com.vocabulario.app.data

import com.vocabulario.app.data.api.ChoiceOption
import kotlin.random.Random

data class DistractorCard(
    val id: String,
    val lemmaL2: String,
    val glossPrimary: String?,
    val pos: String?,
)

data class SimilarWordSeed(
    val lemma: String,
    val glossL1: String?,
    val pos: String?,
)

data class ChoiceDistractorsResult(
    val options: List<ChoiceOption>,
    val usedListKeys: List<String>,
    val unusedPoolWasEmpty: Boolean,
)

private const val CHOICE_COUNT = 8
private const val FROM_LIST_CAP = 3

/**
 * 1 correct + up to 3 same-POS cards from the learning list + similar_words fill.
 * Never mixes POS. List picks prefer unused lemma keys, then the bag resets.
 */
fun pickChoiceDistractors(
    direction: String,
    correctText: String,
    correctLemmaL2: String,
    correctGloss: String?,
    correctPos: String?,
    correctCardId: String,
    listCards: List<DistractorCard>,
    similar: List<SimilarWordSeed>,
    usedKeys: Set<String>,
    random: Random = Random.Default,
): ChoiceDistractorsResult {
    val wantPos = normalizePosKey(correctPos)
    val l2ToL1 = direction.equals("l2_to_l1", ignoreCase = true)
    val usedTexts = mutableSetOf(correctText.trim().lowercase())
    val distractors = ArrayList<ChoiceOption>(CHOICE_COUNT - 1)

    fun samePos(pos: String?): Boolean {
        if (wantPos == "unknown") return true
        return normalizePosKey(pos) == wantPos
    }

    fun tryAdd(
        text: String?,
        lemmaL2: String?,
        gloss: String?,
        pos: String?,
        cardId: String?,
        inLearning: Boolean,
    ): Boolean {
        val t = text?.trim().orEmpty()
        if (t.isBlank() || !isValidPracticeDistractor(t)) return false
        if (!usedTexts.add(t.lowercase())) return false
        distractors.add(
            ChoiceOption(
                text = t,
                lemma_l2 = distractorLemmaL2(direction, lemmaL2, t),
                gloss = gloss,
                pos = pos,
                card_id = cardId,
                in_learning = inLearning,
                is_correct = false,
            ),
        )
        return true
    }

    val pool = listCards.filter { it.id != correctCardId && samePos(it.pos) }
    val unused = pool.filter { lemmaKey(it.lemmaL2) !in usedKeys }
    val unusedPoolWasEmpty = unused.isEmpty() && pool.isNotEmpty()
    val pickPool = if (unused.isNotEmpty()) unused else pool
    val fromList = pickPool.shuffled(random).take(FROM_LIST_CAP)
    val usedListKeys = ArrayList<String>(fromList.size)

    for (card in fromList) {
        if (distractors.size >= CHOICE_COUNT - 1) break
        val text = if (l2ToL1) card.glossPrimary ?: card.lemmaL2 else card.lemmaL2
        if (tryAdd(text, card.lemmaL2, card.glossPrimary, card.pos, card.id, inLearning = true)) {
            val key = lemmaKey(card.lemmaL2)
            if (key.isNotEmpty()) usedListKeys.add(key)
        }
    }

    for (seed in similar.shuffled(random)) {
        if (distractors.size >= CHOICE_COUNT - 1) break
        if (wantPos != "unknown") {
            val seedPos = normalizePosKey(seed.pos)
            if (seedPos != "unknown" && seedPos != wantPos) continue
        }
        val text = if (l2ToL1) {
            seed.glossL1?.takeIf { it.isNotBlank() } ?: seed.lemma
        } else {
            seed.lemma
        }
        val source = pool.firstOrNull { lemmaKeys(it.lemmaL2).any { k -> k in lemmaKeys(seed.lemma) } }
        tryAdd(
            text,
            source?.lemmaL2 ?: seed.lemma,
            seed.glossL1 ?: source?.glossPrimary,
            seed.pos ?: source?.pos,
            source?.id,
            inLearning = source != null,
        )
    }

    for (card in pool.shuffled(random)) {
        if (distractors.size >= CHOICE_COUNT - 1) break
        val text = if (l2ToL1) card.glossPrimary ?: card.lemmaL2 else card.lemmaL2
        tryAdd(text, card.lemmaL2, card.glossPrimary, card.pos, card.id, inLearning = true)
    }

    val correct = ChoiceOption(
        text = correctText,
        lemma_l2 = correctLemmaL2,
        gloss = correctGloss,
        pos = correctPos,
        card_id = correctCardId,
        in_learning = true,
        is_correct = true,
    )
    return ChoiceDistractorsResult(
        options = (distractors + correct).shuffled(random),
        usedListKeys = usedListKeys,
        unusedPoolWasEmpty = unusedPoolWasEmpty,
    )
}
