package com.vocabulario.app.data

import java.text.Normalizer
import java.util.Locale

data class CardMembershipRow(
    val id: String,
    val lemmaL2: String,
    val pos: String?,
    val deckId: String?,
    val enrichmentStatus: String,
)

// Rodzajniki zdejmowane z czoła. Zmiana tylko razem z backend/app/core/lemma_keys.py.
private val ARTICLES = setOf(
    "el", "la", "los", "las", "le", "les", "un", "une",
    "der", "die", "das", "ein", "eine",
    "the", "a", "an",
    "il", "lo", "i", "gli",
    "o", "os", "as", "l",
)

private val PAREN = Regex("""\([^)]*\)|\[[^\]]*\]""")
private val APOS_PREFIX = Regex("""^l['’]\s*""")
private val SPACES = Regex("""\s+""")

fun canonicalLemma(raw: String?): String {
    var text = raw?.trim().orEmpty()
    if (text.isEmpty()) return ""
    text = Normalizer.normalize(text, Normalizer.Form.NFKC)
    text = text.lowercase(Locale.ROOT).replace("ß", "ss")
    text = PAREN.replace(text, " ")
    val kept = StringBuilder(text.length)
    for (ch in text) {
        val type = Character.getType(ch)
        val keptChar = type in Character.UPPERCASE_LETTER..Character.OTHER_NUMBER ||
            ch == ' ' || ch == '\'' || ch == '\u2019'
        kept.append(if (keptChar) ch else ' ')
    }
    text = SPACES.replace(kept, " ").trim()
    text = APOS_PREFIX.replace(text, "").trim()
    var parts = if (text.isEmpty()) emptyList() else text.split(" ")
    while (parts.isNotEmpty() && parts[0] in ARTICLES) {
        parts = parts.drop(1)
        if (parts.isNotEmpty()) {
            val stripped = APOS_PREFIX.replace(parts.joinToString(" "), "").trim()
            parts = if (stripped.isEmpty()) emptyList() else stripped.split(" ")
        }
    }
    return parts.joinToString(" ")
}

fun selectLiveCardForLemma(
    cards: List<CardMembershipRow>,
    lemma: String,
    pos: String?,
): CardMembershipRow? {
    val lemmaNorm = membershipText(lemma)
    val canon = canonicalLemma(lemma)
    val want = normalizePosKey(pos)
    var canonicalHit: CardMembershipRow? = null
    for (card in cards) {
        val got = normalizePosKey(card.pos)
        val posOk = if (want == "unknown") got == "unknown" else got == want
        if (!posOk) continue
        if (membershipText(card.lemmaL2) == lemmaNorm) return card
        if (canon.isNotEmpty() && canonicalLemma(card.lemmaL2) == canon) {
            val current = canonicalHit
            if (current == null || card.lemmaL2.length > current.lemmaL2.length) {
                canonicalHit = card
            }
        }
    }
    return canonicalHit
}

private fun membershipText(raw: String): String {
    val collapsed = SPACES.replace(raw.trim().lowercase(Locale.ROOT), " ")
    return Normalizer.normalize(collapsed, Normalizer.Form.NFC)
}
