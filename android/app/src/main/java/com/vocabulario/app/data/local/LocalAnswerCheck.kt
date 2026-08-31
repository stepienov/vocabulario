package com.vocabulario.app.data.local

import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.formatLemmaWithArticle
import com.vocabulario.app.data.lemmaKey
import kotlinx.serialization.json.JsonObject
import java.text.Normalizer
import kotlin.math.ceil

data class AnswerCheckResult(
    val correct: Boolean,
    val expected: String?,
    val acceptedAsTypo: Boolean,
    val acceptedAsSynonym: Boolean = false,
)

data class MatchedSynonym(
    val displayLemma: String,
    val glossL1: String?,
)

object LocalAnswerCheck {
    fun check(
        userAnswer: String,
        content: JsonObject,
        direction: String,
    ): AnswerCheckResult {
        val answers = collectAnswers(content, direction)
        val normalizedUser = normalize(userAnswer)
        val normalizedCorrect = answers.map { normalize(it) }.filter { it.isNotBlank() }

        for ((index, correct) in normalizedCorrect.withIndex()) {
            if (normalizedUser == correct) {
                return AnswerCheckResult(
                    correct = true,
                    expected = null,
                    acceptedAsTypo = false,
                    acceptedAsSynonym = index > 0,
                )
            }
        }
        for ((index, correct) in normalizedCorrect.withIndex()) {
            if (articleOnlyTypo(normalizedUser, correct)) {
                return AnswerCheckResult(
                    true,
                    correct,
                    acceptedAsTypo = true,
                    acceptedAsSynonym = index > 0,
                )
            }
        }
        for ((index, correct) in normalizedCorrect.withIndex()) {
            if (stripDiacritics(normalizedUser) == stripDiacritics(correct)) {
                return AnswerCheckResult(
                    true,
                    correct,
                    acceptedAsTypo = true,
                    acceptedAsSynonym = index > 0,
                )
            }
            if (fuzzyOk(normalizedUser, correct)) {
                return AnswerCheckResult(
                    true,
                    correct,
                    acceptedAsTypo = true,
                    acceptedAsSynonym = index > 0,
                )
            }
        }
        return AnswerCheckResult(false, normalizedCorrect.firstOrNull(), acceptedAsTypo = false)
    }

    fun collectAnswers(content: JsonObject, direction: String): List<String> {
        val out = linkedSetOf<String>()
        if (direction == "l2_to_l1") {
            content["meanings"].asJsonArray()?.forEach { m ->
                val obj = m.asJsonObject() ?: return@forEach
                obj["gloss_l1"].asJsonString()?.let { out += it }
                obj["synonyms_l1"].asJsonArray()?.forEach { s ->
                    s.asJsonString()?.let { out += it }
                }
            }
        } else {
            content["lemma"].asJsonString()?.let { out += it }
            content["synonyms_l2"].asJsonArray()?.forEach { item ->
                val obj = item.asJsonObject()
                if (obj != null) {
                    val lemma = obj["lemma"].asJsonString() ?: return@forEach
                    out += lemma
                    val withArt = formatLemmaWithArticle(lemma, obj["article"].asJsonString())
                    if (withArt != lemma) out += withArt
                } else {
                    item.asJsonString()?.let { out += it }
                }
            }
        }
        return out.toList()
    }

    fun resolveSynonym(
        content: JsonObject,
        direction: String,
        query: String,
    ): MatchedSynonym? {
        val q = normalize(query)
        if (q.isBlank()) return null
        val qStem = lemmaKey(q)
        if (direction == "l2_to_l1") {
            content["meanings"].asJsonArray()?.forEach { m ->
                val obj = m.asJsonObject() ?: return@forEach
                val gloss = obj["gloss_l1"].asJsonString()
                obj["synonyms_l1"].asJsonArray()?.forEach { s ->
                    val syn = s.asJsonString() ?: return@forEach
                    if (normalize(syn) == q) {
                        return MatchedSynonym(displayLemma = syn, glossL1 = gloss)
                    }
                }
            }
            return null
        }
        content["synonyms_l2"].asJsonArray()?.forEach { item ->
            val obj = item.asJsonObject() ?: return@forEach
            val lemma = obj["lemma"].asJsonString() ?: return@forEach
            val article = obj["article"].asJsonString()
            val gloss = obj["gloss_l1"].asJsonString() ?: obj["gloss"].asJsonString()
            val display = formatLemmaWithArticle(lemma, article)
            val candidates = listOf(lemma, display).map { normalize(it) }
            if (q in candidates || (qStem.isNotEmpty() && lemmaKey(lemma) == qStem)) {
                return MatchedSynonym(displayLemma = display, glossL1 = gloss)
            }
        }
        return null
    }

    private fun articleOnlyTypo(user: String, correct: String): Boolean {
        val corrStem = lemmaKey(correct)
        if (corrStem.isEmpty() || corrStem == correct) return false
        val userStem = lemmaKey(user).ifEmpty { user }
        if (userStem.isEmpty()) return false
        return stripDiacritics(userStem) == stripDiacritics(corrStem)
    }

    private fun normalize(text: String): String =
        text.trim().lowercase().replace(Regex("\\s+"), " ").let {
            Normalizer.normalize(it, Normalizer.Form.NFC)
        }

    private fun stripDiacritics(text: String): String {
        val nfd = Normalizer.normalize(text, Normalizer.Form.NFD)
        return nfd.replace(Regex("\\p{Mn}+"), "")
    }

    private fun fuzzyOk(a: String, b: String): Boolean {
        if (a == b) return true
        if (a.isEmpty() || b.isEmpty()) return false
        if (minOf(a.length, b.length) < 2) return false
        val distance = levenshtein(a, b)
        val n = maxOf(a.length, b.length)
        if (distance <= 1) return true
        val ratio = 1.0 - distance.toDouble() / n.toDouble()
        if (ratio >= 0.85) return true
        return distance <= maxAllowedTypos(n)
    }

    private fun maxAllowedTypos(wordLen: Int): Int {
        if (wordLen < 2) return 0
        val byRatio = ceil(wordLen * 0.15).toInt()
        return maxOf(1, byRatio)
    }

    private fun levenshtein(a: String, b: String): Int {
        val dp = Array(a.length + 1) { IntArray(b.length + 1) }
        for (i in 0..a.length) dp[i][0] = i
        for (j in 0..b.length) dp[0][j] = j
        for (i in 1..a.length) {
            for (j in 1..b.length) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                dp[i][j] = minOf(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
            }
        }
        return dp[a.length][b.length]
    }
}
