package com.vocabulario.app.data.local

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import java.text.Normalizer
import kotlin.math.abs
import kotlin.math.max

object LocalAnswerCheck {
    fun check(
        userAnswer: String,
        content: JsonObject,
        direction: String,
    ): Triple<Boolean, String?, Boolean> {
        val answers = collectAnswers(content, direction)
        val normalizedUser = normalize(userAnswer)
        val normalizedCorrect = answers.map { normalize(it) }.filter { it.isNotBlank() }

        for (correct in normalizedCorrect) {
            if (normalizedUser == correct) return Triple(true, null, false)
        }
        for (correct in normalizedCorrect) {
            if (stripDiacritics(normalizedUser) == stripDiacritics(correct)) {
                return Triple(true, correct, true)
            }
            if (fuzzyOk(normalizedUser, correct)) {
                return Triple(true, correct, true)
            }
        }
        return Triple(false, normalizedCorrect.firstOrNull(), false)
    }

    fun collectAnswers(content: JsonObject, direction: String): List<String> {
        val out = linkedSetOf<String>()
        if (direction == "l2_to_l1") {
            content["meanings"]?.jsonArray?.forEach { m ->
                val obj = m as? JsonObject ?: return@forEach
                obj["gloss_l1"]?.jsonPrimitive?.contentOrNull?.let { out += it }
                obj["synonyms_l1"]?.jsonArray?.forEach { s ->
                    s.jsonPrimitive.contentOrNull?.let { out += it }
                }
            }
        } else {
            content["lemma"]?.jsonPrimitive?.contentOrNull?.let { out += it }
            content["synonyms_l2"]?.jsonArray?.forEach { item ->
                when (item) {
                    is JsonObject -> item["lemma"]?.jsonPrimitive?.contentOrNull?.let { out += it }
                    else -> item.jsonPrimitive.contentOrNull?.let { out += it }
                }
            }
        }
        return out.toList()
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
        if (abs(a.length - b.length) > 1) return false
        val ratio = similarity(a, b)
        return ratio >= 0.85
    }

    private fun similarity(a: String, b: String): Double {
        if (a.isEmpty() && b.isEmpty()) return 1.0
        val dist = levenshtein(a, b)
        return 1.0 - dist.toDouble() / max(a.length, b.length).toDouble()
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
