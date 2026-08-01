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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.ui.text.style.TextOverflow
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.vocabulario.app.data.NON_FINITE_FORMS
import com.vocabulario.app.data.VERB_TENSES
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.examplesForUserLevel
import com.vocabulario.app.data.normalizeTenseKey
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.SpeakIconButton
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
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
                val lemma = el["lemma"].asJsonString()?.trim().orEmpty()
                if (lemma.isBlank()) null
                else RelatedWord(
                    lemma = lemma,
                    glossL1 = el["gloss_l1"].asJsonString() ?: el["gloss"].asJsonString(),
                    pos = el["pos"].asJsonString(),
                )
            }
            is JsonPrimitive -> {
                val lemma = el.content.trim()
                if (lemma.isBlank()) null else RelatedWord(lemma, null, null)
            }
            else -> null
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
    onAddRelated: ((RelatedWord) -> Unit)? = null,
) {
    val context = LocalContext.current
    var tts by remember { mutableStateOf<TextToSpeech?>(null) }
    val lang = languageCode ?: content["language"].asJsonString() ?: "es"

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

    val lemma = content["lemma"].asJsonString() ?: lemmaFallback
    val pos = content["pos"].asJsonString()
    val ipa = content["ipa"].asJsonString()
    val meanings = content["meanings"].asJsonArray() ?: JsonArray(emptyList())
    val synonymsL2 = parseRelatedWords(content["synonyms_l2"].asJsonArray())
    val antonymsL2 = parseRelatedWords(content["antonyms_l2"].asJsonArray())
    val conjugation = content["conjugation"].asJsonObject()
    val tenseMap = conjugation?.get("tenses").asJsonObject()
    val nonFinite = conjugation?.get("non_finite").asJsonObject()
    val periphrases = conjugation?.get("periphrases").asJsonArray()
    val profileTenses = userTenses.orEmpty().map { normalizeTenseKey(it) }
    // Pusta lista w profilu = wszystkie czasy (jak w ustawieniach).
    val visibleFinite = (
        if (profileTenses.isNotEmpty()) profileTenses
        else VERB_TENSES.map { it.first }
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
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                lemma,
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )
            ipa?.let {
                Spacer(Modifier.height(6.dp))
                Text(
                    "[$it]",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
            }
            if (pos != null) {
                Spacer(modifier = Modifier.height(10.dp))
                TagChip(pos)
            }
            Spacer(Modifier.height(16.dp))
            HorizontalDivider(
                modifier = Modifier.fillMaxWidth(0.55f),
                color = MaterialTheme.colorScheme.outlineVariant,
            )
            Spacer(Modifier.height(14.dp))
            SpeakIconButton(onClick = { tts.speakL2(lemma, "lemma") })
        }

        if (!compact && synonymsL2.isNotEmpty()) {
            RelatedWordsSection(
                title = "Synonimy",
                words = synonymsL2,
                onAdd = onAddRelated,
            )
        }

        meanings.forEach { meaningEl ->
            val meaning = meaningEl.asJsonObject() ?: return@forEach
            AppCard {
                Column(modifier = Modifier.padding(16.dp)) {
                    val detailExampleL2 = examplesForUserLevel(
                        meaning["examples"].asJsonArray(),
                        userCefr,
                        maxCount = 1,
                    ).firstOrNull()?.get("l2").asJsonString().orEmpty()
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.Top,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            meaning["gloss_l1"].asJsonString() ?: "",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f),
                        )
                        if (detailExampleL2.isNotBlank()) {
                            SpeakIconButton(
                                onClick = { tts.speakL2(detailExampleL2, "example-gloss") },
                                compact = true,
                            )
                        }
                    }
                    val syns = meaning["synonyms_l1"].asJsonArray()?.mapNotNull { it.asJsonString() }.orEmpty()
                    if (syns.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            syns.joinToString(" · "),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    val usages = meaning["usages"].asJsonArray().orEmpty()
                    if (usages.isNotEmpty() && !compact) {
                        Spacer(Modifier.height(10.dp))
                        Text(
                            "Użycia",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        usages.forEachIndexed { index, usageEl ->
                            val (l2, l1) = when (usageEl) {
                                is JsonObject ->
                                    (usageEl["l2"].asJsonString() ?: "") to
                                        (usageEl["l1"].asJsonString() ?: "")
                                else ->
                                    (usageEl.asJsonString() ?: "") to ""
                            }
                            if (l2.isBlank()) return@forEachIndexed
                            Spacer(Modifier.height(6.dp))
                            Row(
                                verticalAlignment = Alignment.Top,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Text(
                                    l2,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Medium,
                                    modifier = Modifier.weight(1f),
                                )
                                SpeakIconButton(
                                    onClick = { tts.speakL2(l2, "usage-$index") },
                                    compact = true,
                                )
                            }
                            if (l1.isNotBlank()) {
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(
                                    l1,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    val visibleExamples = examplesForUserLevel(
                        meaning["examples"].asJsonArray(),
                        userCefr,
                        maxCount = if (compact) 1 else 2,
                    )
                    visibleExamples.forEach { exObj ->
                        val exampleL2 = exObj["l2"].asJsonString().orEmpty()
                        Spacer(modifier = Modifier.height(12.dp))
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(exampleL2, fontWeight = FontWeight.Medium)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    exObj["l1"].asJsonString() ?: "",
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
                onAdd = onAddRelated,
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
                                val form = nonFinite?.get(selectedKey).asJsonString()
                                if (form != null) {
                                    Surface(
                                        shape = RoundedCornerShape(12.dp),
                                        color = MaterialTheme.colorScheme.surfaceVariant,
                                    ) {
                                        Text(form, modifier = Modifier.padding(12.dp), fontWeight = FontWeight.Medium)
                                    }
                                }
                            } else {
                                val forms = selectedKey?.let { tenseMap?.get(it).asJsonObject() }
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
                                                    Text(form.asJsonString().orEmpty(), fontWeight = FontWeight.Medium)
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
                            val p = item.asJsonObject() ?: return@forEach
                            Spacer(Modifier.height(12.dp))
                            Text(
                                p["formula_l2"].asJsonString() ?: "",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                            p["gloss_l1"].asJsonString()?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            p["examples"].asJsonArray()?.forEachIndexed { exIndex, ex ->
                                val exObj = ex.asJsonObject() ?: return@forEachIndexed
                                val periL2 = exObj["l2"].asJsonString().orEmpty()
                                Spacer(Modifier.height(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = MaterialTheme.colorScheme.surfaceVariant,
                                ) {
                                    Column(modifier = Modifier.padding(10.dp)) {
                                        Row(
                                            verticalAlignment = Alignment.Top,
                                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                                        ) {
                                            Text(
                                                periL2,
                                                fontWeight = FontWeight.Medium,
                                                modifier = Modifier.weight(1f),
                                            )
                                            if (periL2.isNotBlank()) {
                                                SpeakIconButton(
                                                    onClick = { tts.speakL2(periL2, "peri-$exIndex") },
                                                    compact = true,
                                                )
                                            }
                                        }
                                        Text(
                                            exObj["l1"].asJsonString() ?: "",
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
    onAdd: ((RelatedWord) -> Unit)?,
) {
    AppCard {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            words.forEachIndexed { index, word ->
                if (index > 0) {
                    HorizontalDivider(
                        modifier = Modifier.padding(vertical = 12.dp),
                        color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f),
                    )
                } else {
                    Spacer(Modifier.height(12.dp))
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(word.lemma, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        word.glossL1?.takeIf { it.isNotBlank() }?.let {
                            Spacer(Modifier.height(4.dp))
                            Text(
                                it,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 3,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        word.pos?.let {
                            Spacer(Modifier.height(8.dp))
                            TagChip(it)
                        }
                    }
                    if (onAdd != null) {
                        IconButton(
                            onClick = { onAdd(word) },
                            modifier = Modifier.size(40.dp),
                        ) {
                            Icon(
                                Icons.Default.Add,
                                contentDescription = "Dodaj",
                                tint = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
            }
        }
    }
}

