package com.vocabulario.app.ui.card

import android.speech.tts.TextToSpeech
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.vocabulario.app.data.DEFAULT_CARD_TENSES
import com.vocabulario.app.data.NON_FINITE_FORMS
import com.vocabulario.app.data.VERB_TENSES
import com.vocabulario.app.data.examplesForUserLevel
import com.vocabulario.app.data.normalizeTenseKey
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.Locale

data class RelatedWord(
    val lemma: String,
    val glossL1: String?,
    val pos: String?,
)

private fun parseRelatedWords(raw: JsonArray?): List<RelatedWord> {
    if (raw == null) return emptyList()
    return raw.mapNotNull { el: JsonElement ->
        when (el) {
            is JsonObject -> {
                val lemma = el["lemma"]?.jsonPrimitive?.content?.trim().orEmpty()
                if (lemma.isBlank()) null
                else RelatedWord(
                    lemma = lemma,
                    glossL1 = el["gloss_l1"]?.jsonPrimitive?.content
                        ?: el["gloss"]?.jsonPrimitive?.content,
                    pos = el["pos"]?.jsonPrimitive?.content,
                )
            }
            else -> runCatching {
                val lemma = el.jsonPrimitive.content.trim()
                if (lemma.isBlank()) null else RelatedWord(lemma, null, null)
            }.getOrNull()
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CardDetailContent(
    content: JsonObject,
    lemmaFallback: String,
    languageCode: String? = null,
    compact: Boolean = false,
    userTenses: List<String>? = null,
    userCefr: String = "A2",
    enrichmentStatus: String = "ready",
    enrichmentError: String? = null,
    onAddRelatedToLearning: ((RelatedWord) -> Unit)? = null,
    onAddRelatedToFavorites: ((RelatedWord) -> Unit)? = null,
) {
    val context = LocalContext.current
    var tts by remember { mutableStateOf<TextToSpeech?>(null) }
    val lang = languageCode ?: content["language"]?.jsonPrimitive?.content ?: "es"

    DisposableEffect(context) {
        var engine: TextToSpeech? = null
        engine = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                engine?.language = Locale.forLanguageTag(lang)
            }
        }
        tts = engine
        onDispose {
            engine?.stop()
            engine?.shutdown()
        }
    }

    val lemma = content["lemma"]?.jsonPrimitive?.content ?: lemmaFallback
    val pos = content["pos"]?.jsonPrimitive?.content
    val ipa = content["ipa"]?.jsonPrimitive?.content
    val meanings = content["meanings"]?.jsonArray ?: JsonArray(emptyList())
    val synonymsL2 = parseRelatedWords(content["synonyms_l2"]?.jsonArray)
    val antonymsL2 = parseRelatedWords(content["antonyms_l2"]?.jsonArray)
    val conjugation = content["conjugation"]?.jsonObject
    val tenseMap = conjugation?.get("tenses")?.jsonObject
    val nonFinite = conjugation?.get("non_finite")?.jsonObject
    val periphrases = conjugation?.get("periphrases")?.jsonArray
    val profileTenses = userTenses.orEmpty().map { normalizeTenseKey(it) }
    val visibleFinite = (
        if (profileTenses.isNotEmpty()) profileTenses
        else DEFAULT_CARD_TENSES.filter { it != "gerundio" && it != "participio" }
        ).filter { tenseMap?.containsKey(it) == true }
    val visibleNonFinite = listOf("gerundio", "participio").filter { nonFinite?.containsKey(it) == true }
    val conjugationTabs = visibleFinite + visibleNonFinite
    fun tenseLabel(key: String): String =
        VERB_TENSES.firstOrNull { it.first == key }?.second
            ?: NON_FINITE_FORMS.firstOrNull { it.first == key }?.second
            ?: key.replace("_", " ")
    var conjugationExpanded by remember { mutableStateOf(!compact) }
    var selectedTenseIndex by remember { mutableIntStateOf(0) }

    Column(
        modifier = if (compact) Modifier.fillMaxWidth() else Modifier.fillMaxWidth().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        when (enrichmentStatus) {
            "pending" -> {
                AppCard {
                    Text(
                        "Przygotowuję pełną kartę w tle — możesz wrócić za chwilę.",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            "failed" -> {
                AppCard {
                    Text(
                        enrichmentError ?: "Nie udało się przygotować karty.",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
        AppCard {
            Column(modifier = Modifier.padding(20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(lemma, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        ipa?.let {
                            Spacer(Modifier.height(4.dp))
                            Text("[$it]", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    IconButton(
                        onClick = { tts?.speak(lemma, TextToSpeech.QUEUE_FLUSH, null, "lemma") },
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.primaryContainer),
                    ) {
                        Icon(Icons.Default.VolumeUp, contentDescription = "Odtwórz", tint = MaterialTheme.colorScheme.primary)
                    }
                }
                if (pos != null) {
                    Spacer(Modifier.height(12.dp))
                    TagChip(pos)
                }
            }
        }

        if (!compact && synonymsL2.isNotEmpty()) {
            RelatedWordsSection(
                title = "Synonimy",
                words = synonymsL2,
                onAddToLearning = onAddRelatedToLearning,
                onAddToFavorites = onAddRelatedToFavorites,
            )
        }

        meanings.forEach { meaningEl ->
            val meaning = meaningEl.jsonObject
            AppCard {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        meaning["gloss_l1"]?.jsonPrimitive?.content ?: "",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    val syns = meaning["synonyms_l1"]?.jsonArray?.map { it.jsonPrimitive.content }.orEmpty()
                    if (syns.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            syns.joinToString(" · "),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    val usages = meaning["usages"]?.jsonArray.orEmpty()
                    if (usages.isNotEmpty() && !compact) {
                        Spacer(Modifier.height(10.dp))
                        Text(
                            "Użycia",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        usages.forEach { usageEl ->
                            val (l2, l1) = when (usageEl) {
                                is JsonObject ->
                                    (usageEl["l2"]?.jsonPrimitive?.content ?: "") to
                                        (usageEl["l1"]?.jsonPrimitive?.content ?: "")
                                else ->
                                    runCatching { usageEl.jsonPrimitive.content }.getOrDefault("") to ""
                            }
                            if (l2.isBlank()) return@forEach
                            Spacer(Modifier.height(6.dp))
                            Text(l2, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                            if (l1.isNotBlank()) {
                                Text(
                                    l1,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    val visibleExamples = examplesForUserLevel(
                        meaning["examples"]?.jsonArray,
                        userCefr,
                        maxCount = if (compact) 1 else 2,
                    )
                    visibleExamples.forEach { exObj ->
                        Spacer(Modifier.height(12.dp))
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(exObj["l2"]?.jsonPrimitive?.content ?: "", fontWeight = FontWeight.Medium)
                                Text(
                                    exObj["l1"]?.jsonPrimitive?.content ?: "",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }

        if (!compact && antonymsL2.isNotEmpty()) {
            RelatedWordsSection(
                title = "Antonimy",
                words = antonymsL2,
                onAddToLearning = onAddRelatedToLearning,
                onAddToFavorites = onAddRelatedToFavorites,
            )
        }

        if (conjugationTabs.isNotEmpty() || periphrases != null) {
            AppCard {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Odmiana", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        if (compact) {
                            IconButton(onClick = { conjugationExpanded = !conjugationExpanded }) {
                                Icon(
                                    if (conjugationExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                    contentDescription = null,
                                )
                            }
                        }
                    }
                    if (!compact || conjugationExpanded) {
                        if (conjugationTabs.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                conjugationTabs.forEachIndexed { index, name ->
                                    FilterChip(
                                        selected = index == selectedTenseIndex,
                                        onClick = { selectedTenseIndex = index },
                                        label = { Text(tenseLabel(name), style = MaterialTheme.typography.labelMedium) },
                                        colors = FilterChipDefaults.filterChipColors(
                                            selectedContainerColor = MaterialTheme.colorScheme.primary,
                                            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
                                        ),
                                    )
                                }
                            }
                            Spacer(Modifier.height(12.dp))
                            val selectedKey = conjugationTabs.getOrNull(selectedTenseIndex)
                            if (selectedKey == "gerundio" || selectedKey == "participio") {
                                val form = nonFinite?.get(selectedKey)?.jsonPrimitive?.content
                                if (form != null) {
                                    Surface(
                                        shape = RoundedCornerShape(12.dp),
                                        color = MaterialTheme.colorScheme.surfaceVariant,
                                    ) {
                                        Text(form, modifier = Modifier.padding(12.dp), fontWeight = FontWeight.Medium)
                                    }
                                }
                            } else {
                                val forms = selectedKey?.let { tenseMap?.get(it)?.jsonObject }
                                forms?.entries?.chunked(2)?.forEach { row ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    ) {
                                        row.forEach { (person, form) ->
                                            Surface(
                                                modifier = Modifier.weight(1f),
                                                shape = RoundedCornerShape(12.dp),
                                                color = MaterialTheme.colorScheme.surfaceVariant,
                                            ) {
                                                Column(modifier = Modifier.padding(10.dp)) {
                                                    Text(
                                                        person,
                                                        style = MaterialTheme.typography.labelSmall,
                                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                    )
                                                    Text(form.jsonPrimitive.content, fontWeight = FontWeight.Medium)
                                                }
                                            }
                                        }
                                        if (row.size == 1) Spacer(Modifier.weight(1f))
                                    }
                                    Spacer(Modifier.height(8.dp))
                                }
                            }
                        }
                        periphrases?.forEach { item ->
                            val p = item.jsonObject
                            Spacer(Modifier.height(12.dp))
                            Text(
                                p["formula_l2"]?.jsonPrimitive?.content ?: "",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                            p["gloss_l1"]?.jsonPrimitive?.content?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            p["examples"]?.jsonArray?.forEach { ex ->
                                val exObj = ex.jsonObject
                                Spacer(Modifier.height(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = MaterialTheme.colorScheme.surfaceVariant,
                                ) {
                                    Column(modifier = Modifier.padding(10.dp)) {
                                        Text(exObj["l2"]?.jsonPrimitive?.content ?: "", fontWeight = FontWeight.Medium)
                                        Text(
                                            exObj["l1"]?.jsonPrimitive?.content ?: "",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RelatedWordsSection(
    title: String,
    words: List<RelatedWord>,
    onAddToLearning: ((RelatedWord) -> Unit)?,
    onAddToFavorites: ((RelatedWord) -> Unit)?,
) {
    AppCard {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            words.forEach { word ->
                Spacer(Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(word.lemma, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        word.glossL1?.takeIf { it.isNotBlank() }?.let {
                            Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    word.pos?.let { TagChip(it) }
                    if (onAddToFavorites != null) {
                        IconButton(onClick = { onAddToFavorites(word) }) {
                            Icon(Icons.Default.FavoriteBorder, contentDescription = "Ulubione")
                        }
                    }
                    if (onAddToLearning != null) {
                        IconButton(onClick = { onAddToLearning(word) }) {
                            Icon(Icons.Default.Add, contentDescription = "Dodaj do nauki")
                        }
                    }
                }
            }
        }
    }
}

