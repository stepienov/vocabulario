package com.vocabulario.app.ui.card

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.vocabulario.app.R
import com.vocabulario.app.data.api.CardHistoryEventResponse
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

@Composable
fun historyEventSummary(event: CardHistoryEventResponse): String? = when (event.event_type) {
    "correction_submitted" -> historyReportSummary(event.payload)
    "restored_to_original" -> stringResource(R.string.card_history_summary_restored)
    "correction_rejected" -> event.payload?.get("reason")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
        ?: correctionResultMessage(event.result_code)
    "correction_accepted" -> historyAcceptedSummary(event)
    "self_edit_applied" -> historySelfEditDiff(event.payload)
    "self_edit_reviewed" -> event.summary?.takeIf { it.isNotBlank() }
    else -> event.summary?.takeIf { it.isNotBlank() }
}

@Composable
private fun historyReportSummary(payload: JsonObject?): String {
    val sections = payload?.get("sections")?.jsonArray
        ?.mapNotNull { element ->
            (element as? JsonPrimitive)?.content
        }
        .orEmpty()
    val labels = sections.map { sectionId ->
        correctionSections.firstOrNull { it.id == sectionId }?.labelRes?.let { stringResource(it) }
            ?: sectionId
    }
    val joined = labels.joinToString(", ").ifBlank { "—" }
    return stringResource(R.string.card_history_summary_report, joined)
}

@Composable
private fun historyAcceptedSummary(event: CardHistoryEventResponse): String? {
    val diff = historySelfEditDiff(event.payload)
    if (!diff.isNullOrBlank()) return diff
    return event.payload?.get("reason")?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
        ?: correctionResultMessage(event.result_code)
}

@Composable
private fun historySelfEditDiff(payload: JsonObject?): String? {
    val before = payload?.get("before")?.jsonObject ?: return null
    val after = payload?.get("after")?.jsonObject ?: return null
    val parts = mutableListOf<String>()
    val beforeLemma = before.stringField("lemma_l2")
    val afterLemma = after.stringField("lemma_l2")
    if (beforeLemma != afterLemma) {
        parts += stringResource(R.string.card_history_diff_lemma, beforeLemma ?: "—", afterLemma ?: "—")
    }
    val beforePos = before.stringField("pos")
    val afterPos = after.stringField("pos")
    if (beforePos != afterPos) {
        parts += stringResource(R.string.card_history_diff_pos, beforePos ?: "—", afterPos ?: "—")
    }
    val beforeGloss = before.stringField("gloss_primary")
    val afterGloss = after.stringField("gloss_primary")
    if (beforeGloss != afterGloss) {
        parts += stringResource(R.string.card_history_diff_gloss, beforeGloss ?: "—", afterGloss ?: "—")
    }
    val beforeContent = before.get("content")?.jsonObject
    val afterContent = after.get("content")?.jsonObject
    if (beforeContent?.get("ipa")?.jsonPrimitive?.content != afterContent?.get("ipa")?.jsonPrimitive?.content) {
        val from = beforeContent?.get("ipa")?.jsonPrimitive?.content ?: "—"
        val to = afterContent?.get("ipa")?.jsonPrimitive?.content ?: "—"
        parts += stringResource(R.string.card_history_diff_ipa, from, to)
    }
    if (beforeContent.jsonStable("conjugation") != afterContent.jsonStable("conjugation")) {
        parts += stringResource(R.string.card_history_diff_conjugation)
    }
    if (beforeContent.jsonStable("meanings") != afterContent.jsonStable("meanings")) {
        parts += stringResource(R.string.card_history_diff_meanings)
    }
    if (beforeContent.jsonStable("similar_words") != afterContent.jsonStable("similar_words")) {
        parts += stringResource(R.string.card_history_diff_similar)
    }
    return parts.joinToString("; ").ifBlank {
        stringResource(R.string.card_history_diff_content)
    }
}

private fun JsonObject?.stringField(key: String): String? =
    this?.get(key)?.jsonPrimitive?.content

private fun JsonObject?.jsonStable(key: String): String? =
    this?.get(key)?.let { element ->
        when (element) {
            is JsonObject, is JsonArray -> element.toString()
            is JsonPrimitive -> element.content
            else -> element.toString()
        }
    }
