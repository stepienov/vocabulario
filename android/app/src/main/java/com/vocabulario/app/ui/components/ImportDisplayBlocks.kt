package com.vocabulario.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.data.api.ImportDisplayBlock
import com.vocabulario.app.data.api.ImportDisplayPayload
import com.vocabulario.app.data.api.ImportDisplaySide
import com.vocabulario.app.ui.card.L2TtsSpeaker
import com.vocabulario.app.ui.card.rememberL2Tts
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull

@Composable
fun ImportDisplayFlip(
    display: ImportDisplayPayload,
    modifier: Modifier = Modifier,
    showPrompt: Boolean = true,
    /** Lista: bez głośnika. Otwarta karta: tylko L2 (patrz [learningLang]). */
    enableTts: Boolean = true,
    learningLang: String? = null,
    /** true = od razu cała karta (np. po „Pokaż odpowiedź” w nauce); bez przycisku Odkryj. */
    revealed: Boolean = false,
) {
    var showAnswer by remember(display) { mutableStateOf(revealed) }
    val answerVisible = revealed || showAnswer
    val scheme = MaterialTheme.colorScheme
    Column(modifier = modifier.fillMaxWidth()) {
        if (showPrompt) {
            ImportDisplayBlocks(
                display.prompt,
                enableTts = enableTts,
                learningLang = learningLang,
            )
            Spacer(modifier = Modifier.height(12.dp))
        }
        if (!answerVisible) {
            Surface(
                onClick = { showAnswer = true },
                shape = RoundedCornerShape(12.dp),
                color = scheme.primaryContainer,
                contentColor = scheme.onPrimaryContainer,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.BTN_REVEAL),
            ) {
                Text(
                    stringResource(R.string.action_reveal),
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        } else {
            ImportDisplayBlocks(
                display.answer,
                enableTts = enableTts,
                learningLang = learningLang,
            )
        }
    }
}

@Composable
fun ListRevealAnswer(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    var revealed by remember { mutableStateOf(false) }
    val scheme = MaterialTheme.colorScheme
    Column(modifier = modifier.fillMaxWidth()) {
        if (!revealed) {
            Surface(
                onClick = { revealed = true },
                shape = RoundedCornerShape(12.dp),
                color = scheme.primaryContainer,
                contentColor = scheme.onPrimaryContainer,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.BTN_REVEAL),
            ) {
                Text(
                    stringResource(R.string.action_reveal),
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        } else {
            Column(modifier = Modifier.fillMaxWidth()) {
                content()
            }
        }
    }
}


@Composable
fun ImportDisplayBlocks(
    side: ImportDisplaySide,
    enableTts: Boolean = true,
    learningLang: String? = null,
) {
    val speaker = rememberL2Tts(learningLang ?: "en")
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        side.blocks.forEach { block ->
            ImportDisplayBlockView(
                block,
                speaker,
                enableTts = enableTts,
                learningLang = learningLang,
            )
        }
    }
}

@Composable
private fun ImportDisplayBlockView(
    block: ImportDisplayBlock,
    speaker: L2TtsSpeaker,
    enableTts: Boolean = true,
    learningLang: String? = null,
) {
    val scheme = MaterialTheme.colorScheme
    val resolvedType = when (block.type) {
        "title" -> when {
            block.emphasis == "lemma" || block.size == "lemma" || block.semantic == "headword" -> "headword"
            block.emphasis == "gloss" || block.size == "gloss" || block.semantic == "translation" -> "gloss"
            else -> "headword"
        }
        "paragraph", "pre" -> "text"
        "meta" -> "chip"
        "note" -> "note"
        else -> block.type
    }
    val alignMod = when (block.align) {
        "center" -> Modifier.fillMaxWidth()
        else -> Modifier
    }
    val textAlign = when (block.align) {
        "center" -> androidx.compose.ui.text.style.TextAlign.Center
        else -> null
    }
    val style = when (block.size) {
        "display" -> MaterialTheme.typography.headlineMedium
        "lemma" -> MaterialTheme.typography.headlineSmall
        "gloss" -> MaterialTheme.typography.titleLarge
        "caption" -> MaterialTheme.typography.labelMedium
        "body" -> MaterialTheme.typography.bodyLarge
        else -> null
    }

    when (resolvedType) {
        "chip", "note" -> {
            val t = block.text?.takeIf { it.isNotBlank() } ?: return
            Surface(
                shape = RoundedCornerShape(999.dp),
                color = scheme.secondaryContainer,
                contentColor = scheme.onSecondaryContainer,
                modifier = alignMod,
            ) {
                Text(
                    t,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    style = style ?: MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium,
                    textAlign = textAlign,
                )
            }
        }
        "headword" -> {
            val t = block.text?.takeIf { it.isNotBlank() } ?: return
            ImportSpeakableText(
                text = t,
                block = block,
                speaker = speaker,
                utteranceId = "import-headword",
                modifier = alignMod,
                style = style ?: MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = scheme.onSurface,
                textAlign = textAlign,
                enableTts = enableTts,
                learningLang = learningLang,
            )
        }
        "gloss" -> {
            val t = block.text?.takeIf { it.isNotBlank() } ?: return
            ImportSpeakableText(
                text = t,
                block = block,
                speaker = speaker,
                utteranceId = "import-gloss",
                modifier = alignMod,
                style = style ?: MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                color = scheme.onSurface,
                textAlign = textAlign,
                enableTts = enableTts,
                learningLang = learningLang,
            )
        }
        "text" -> {
            val t = block.text?.takeIf { it.isNotBlank() } ?: return
            Text(
                t,
                modifier = alignMod,
                style = style ?: MaterialTheme.typography.bodyLarge,
                color = scheme.onSurface,
                textAlign = textAlign,
            )
        }
        "bilingual" -> {
            val l2 = block.text?.takeIf { it.isNotBlank() }
            val l1 = block.items?.firstOrNull()?.takeIf { it.isNotBlank() }
            if (l2 == null && l1 == null) return
            Column(
                modifier = alignMod,
                verticalArrangement = Arrangement.spacedBy(2.dp),
                horizontalAlignment = if (block.align == "center") Alignment.CenterHorizontally else Alignment.Start,
            ) {
                if (l2 != null) {
                    Text(l2, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                }
                if (l1 != null) {
                    Text(l1, style = MaterialTheme.typography.bodyMedium, color = scheme.onSurfaceVariant)
                }
            }
        }
        "list" -> {
            val items = block.items.orEmpty().filter { it.isNotBlank() }
            if (items.isEmpty()) return
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                items.forEach { item ->
                    Text("• $item", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        "table" -> {
            val headers = block.headers.orEmpty()
            val rows = block.rows.orEmpty()
            if (headers.isEmpty() && rows.isEmpty()) return
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                if (headers.isNotEmpty()) {
                    Text(
                        headers.joinToString(" · "),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = scheme.onSurfaceVariant,
                    )
                }
                rows.forEach { row ->
                    Text(row.joinToString(" · "), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        "divider" -> HorizontalDivider(color = scheme.outline.copy(alpha = 0.4f))
        "section" -> {
            val heading = block.heading?.takeIf { it.isNotBlank() } ?: stringResource(R.string.section_fallback)
            val startCollapsed = block.collapsed != false
            val openMap = remember { mutableStateMapOf<String, Boolean>() }
            val key = heading
            val open = openMap[key] ?: !startCollapsed
            Column {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { openMap[key] = !open },
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        heading,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = scheme.primary,
                    )
                    Text(
                        if (open) "▾" else "▸",
                        color = scheme.onSurfaceVariant,
                    )
                }
                AnimatedVisibility(visible = open) {
                    Column(
                        modifier = Modifier.padding(top = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        (block.children.orEmpty()).forEach { child ->
                            ImportDisplayBlockView(
                                child,
                                speaker,
                                enableTts = enableTts,
                                learningLang = learningLang,
                            )
                        }
                    }
                }
            }
        }
        else -> {
            val t = block.text?.takeIf { it.isNotBlank() } ?: return
            Text(t, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun ImportSpeakableText(
    text: String,
    block: ImportDisplayBlock,
    speaker: L2TtsSpeaker,
    utteranceId: String,
    modifier: Modifier,
    style: androidx.compose.ui.text.TextStyle,
    fontWeight: FontWeight,
    color: androidx.compose.ui.graphics.Color,
    textAlign: androidx.compose.ui.text.style.TextAlign?,
    enableTts: Boolean = true,
    learningLang: String? = null,
) {
    val tts = block.tts
    val allowSpeak = enableTts &&
        tts?.enabled == true &&
        isLearningLanguageTts(tts.lang, learningLang, block)
    if (!allowSpeak) {
        Text(
            text,
            modifier = modifier,
            style = style,
            fontWeight = fontWeight,
            color = color,
            textAlign = textAlign,
        )
        return
    }
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = if (block.align == "center") Arrangement.Center else Arrangement.Start,
    ) {
        Text(
            text,
            modifier = Modifier.weight(1f, fill = false),
            style = style,
            fontWeight = fontWeight,
            color = color,
            textAlign = textAlign,
        )
        SpeakIconButton(
            onClick = { speaker.speak(text, utteranceId, tts?.lang) },
            compact = true,
        )
    }
}

/** TTS tylko dla języka uczonego (L2), nie dla glossu L1. */
private fun isLearningLanguageTts(
    ttsLang: String?,
    learningLang: String?,
    block: ImportDisplayBlock,
): Boolean {
    val learn = learningLang?.trim()?.lowercase().orEmpty()
    val tag = ttsLang?.trim()?.lowercase().orEmpty()
    if (learn.isNotEmpty() && tag.isNotEmpty()) {
        val learnBase = learn.take(2)
        val tagBase = tag.take(2)
        return tagBase == learnBase || tag.startsWith(learn) || learn.startsWith(tagBase)
    }
    // Bez jawnego lang — tylko headword / lemma (nigdy gloss/translation).
    if (block.semantic == "translation" || block.type == "gloss" || block.size == "gloss") {
        return false
    }
    return block.semantic == "headword" ||
        block.type == "headword" ||
        block.size == "lemma" ||
        block.emphasis == "lemma"
}

fun isImportPreserveContent(content: JsonObject): Boolean {
    val schema = content.stringOrNull("schema_version")
    if (schema == "import_display.v1") return true
    if (content.stringOrNull("card_kind") == "imported") return true
    return content.stringOrNull("pos").equals("imported", ignoreCase = true)
}

fun parseImportDisplayFromContent(content: JsonObject): ImportDisplayPayload? {
    return runCatching {
        val schema = content.stringOrNull("schema_version")
        if (schema != "import_display.v1") return null
        val display = content.jsonObjectOrNull("display") ?: return null
        ImportDisplayPayload(
            prompt = parseSide(display.jsonObjectOrNull("prompt")),
            answer = parseSide(display.jsonObjectOrNull("answer")),
            prompt_style = display.stringOrNull("prompt_style") ?: "word",
            bidirectional = display.booleanOrNull("bidirectional") ?: false,
        )
    }.getOrNull()
}

private fun parseSide(obj: JsonObject?): ImportDisplaySide {
    if (obj == null) return ImportDisplaySide()
    val blocks = obj.jsonArrayOrNull("blocks")?.mapNotNull { el ->
        (el as? JsonObject)?.let { runCatching { parseBlock(it) }.getOrNull() }
    }.orEmpty()
    return ImportDisplaySide(blocks = blocks)
}

private fun parseBlock(obj: JsonObject): ImportDisplayBlock {
    val items = obj.jsonArrayOrNull("items")?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
    val headers = obj.jsonArrayOrNull("headers")?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
    val rows = obj.jsonArrayOrNull("rows")?.mapNotNull { row ->
        (row as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
    }
    val children = obj.jsonArrayOrNull("children")?.mapNotNull { el ->
        (el as? JsonObject)?.let { runCatching { parseBlock(it) }.getOrNull() }
    }
    val ttsObj = obj.jsonObjectOrNull("tts")
    val tts = ttsObj?.let {
        com.vocabulario.app.data.api.ImportTts(
            enabled = it.booleanOrNull("enabled") ?: false,
            lang = it.stringOrNull("lang"),
        )
    }
    return ImportDisplayBlock(
        type = obj.stringOrNull("type") ?: "text",
        text = obj.stringOrNull("text"),
        emphasis = obj.stringOrNull("emphasis"),
        heading = obj.stringOrNull("heading"),
        collapsed = obj.booleanOrNull("collapsed"),
        items = items,
        headers = headers,
        rows = rows,
        children = children,
        align = obj.stringOrNull("align"),
        size = obj.stringOrNull("size"),
        semantic = obj.stringOrNull("semantic"),
        tts = tts,
    )
}

private fun JsonObject.stringOrNull(key: String): String? =
    (this[key] as? JsonPrimitive)?.contentOrNull

private fun JsonObject.booleanOrNull(key: String): Boolean? =
    (this[key] as? JsonPrimitive)?.booleanOrNull

private fun JsonObject.jsonObjectOrNull(key: String): JsonObject? =
    this[key] as? JsonObject

private fun JsonObject.jsonArrayOrNull(key: String): JsonArray? =
    this[key] as? JsonArray

