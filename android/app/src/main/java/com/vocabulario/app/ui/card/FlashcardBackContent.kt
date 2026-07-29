package com.vocabulario.app.ui.card

import android.speech.tts.TextToSpeech
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.vocabulario.app.data.DEFAULT_CARD_TENSES
import com.vocabulario.app.data.NON_FINITE_FORMS
import com.vocabulario.app.data.VERB_TENSES
import com.vocabulario.app.data.examplesForUserLevel
import com.vocabulario.app.data.normalizeTenseKey
import com.vocabulario.app.data.posLabelPl
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.Locale

private val PERSON_ORDER = listOf("yo", "tú", "él", "nosotros", "vosotros", "ellos")

@Composable
fun FlashcardBackContent(
    content: JsonObject,
    lemmaFallback: String,
    userTenses: List<String> = emptyList(),
    userCefr: String = "A2",
    showUsages: Boolean = true,
    showExampleSentences: Boolean = true,
    showSynonymsAntonyms: Boolean = true,
    showPeriphrases: Boolean = true,
    conjugationExpandedDefault: Boolean = false,
    relatedWordsExpandedDefault: Boolean = false,
    onAddRelatedToLearning: ((RelatedWord) -> Unit)? = null,
    onAddRelatedToFavorites: ((RelatedWord) -> Unit)? = null,
) {
    val context = LocalContext.current
    val lemma = content["lemma"]?.jsonPrimitive?.content ?: lemmaFallback
    val pos = content["pos"]?.jsonPrimitive?.content
    val ipa = content["ipa"]?.jsonPrimitive?.content
    val lang = content["language"]?.jsonPrimitive?.content ?: "es"
    val meanings = content["meanings"]?.jsonArray ?: JsonArray(emptyList())
    val synonymsL2 = parseFlashRelatedWords(content["synonyms_l2"]?.jsonArray)
    val antonymsL2 = parseFlashRelatedWords(content["antonyms_l2"]?.jsonArray)
    val conjugation = content["conjugation"]?.jsonObject
    val tenseMap = conjugation?.get("tenses")?.jsonObject
    val nonFinite = conjugation?.get("non_finite")?.jsonObject
    val periphrases = conjugation?.get("periphrases")?.jsonArray

    var tts by remember { mutableStateOf<TextToSpeech?>(null) }
    DisposableEffect(context, lang) {
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

    val profileTenses = userTenses.map { normalizeTenseKey(it) }
    val finiteKeys = (
        if (profileTenses.isNotEmpty()) profileTenses
        else DEFAULT_CARD_TENSES.filter { it != "gerundio" && it != "participio" }
        ).filter { tenseMap?.containsKey(it) == true }
    val nonFiniteKeys = listOf("gerundio", "participio").filter {
        nonFinite?.containsKey(it) == true
    }

    var usagesModal by remember { mutableStateOf<List<Pair<String, String>>?>(null) }
    var synExpanded by remember(relatedWordsExpandedDefault) { mutableStateOf(relatedWordsExpandedDefault) }
    var antExpanded by remember(relatedWordsExpandedDefault) { mutableStateOf(relatedWordsExpandedDefault) }
    val expandedTenses = remember(conjugationExpandedDefault, finiteKeys, nonFiniteKeys) {
        mutableStateMapOf<String, Boolean>().apply {
            (finiteKeys + nonFiniteKeys).forEach { put(it, conjugationExpandedDefault) }
        }
    }
    val expandedPeri = remember(periphrases) {
        mutableStateMapOf<String, Boolean>().apply {
            periphrases?.forEachIndexed { i, _ -> put("p$i", false) }
        }
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Nagłówek: lemma / IPA / POS / play
        AppCard {
            Row(
                modifier = Modifier.padding(20.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(lemma, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    if (!ipa.isNullOrBlank()) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "[$ipa]",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (!pos.isNullOrBlank()) {
                        Spacer(Modifier.height(10.dp))
                        TagChip(posLabelPl(pos).ifBlank { pos })
                    }
                }
                IconButton(
                    onClick = { tts?.speak(lemma, TextToSpeech.QUEUE_FLUSH, null, "lemma") },
                    modifier = Modifier
                        .size(48.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primaryContainer),
                ) {
                    Icon(
                        Icons.Default.VolumeUp,
                        contentDescription = "Odtwórz",
                        tint = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }

        meanings.forEach { meaningEl ->
            val meaning = meaningEl.jsonObject
            val gloss = meaning["gloss_l1"]?.jsonPrimitive?.content.orEmpty()
            val syns = meaning["synonyms_l1"]?.jsonArray?.map { it.jsonPrimitive.content }.orEmpty()
            val example = examplesForUserLevel(meaning["examples"]?.jsonArray, userCefr, maxCount = 1).firstOrNull()
            val usages = meaning["usages"]?.jsonArray.orEmpty().mapNotNull { usageEl ->
                when (usageEl) {
                    is JsonObject -> {
                        val l2 = usageEl["l2"]?.jsonPrimitive?.content.orEmpty()
                        val l1 = usageEl["l1"]?.jsonPrimitive?.content.orEmpty()
                        if (l2.isBlank()) null else l2 to l1
                    }
                    else -> runCatching {
                        val l2 = usageEl.jsonPrimitive.content
                        if (l2.isBlank()) null else l2 to ""
                    }.getOrNull()
                }
            }

            AppCard {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        gloss.ifBlank { lemmaFallback },
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    if (syns.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            syns.joinToString(" · "),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (showExampleSentences && example != null) {
                        Spacer(Modifier.height(14.dp))
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(modifier = Modifier.padding(14.dp)) {
                                Text(
                                    example["l2"]?.jsonPrimitive?.content.orEmpty(),
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.Medium,
                                )
                                Spacer(Modifier.height(8.dp))
                                Text(
                                    example["l1"]?.jsonPrimitive?.content.orEmpty(),
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontStyle = FontStyle.Italic,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    if (showUsages && usages.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
                            TextButton(onClick = { usagesModal = usages }) {
                                Text("przykłady użycia →")
                            }
                        }
                    }
                }
            }
        }

        if (showSynonymsAntonyms && synonymsL2.isNotEmpty()) {
            CollapsibleSection(
                title = "Synonimy",
                expanded = synExpanded,
                onToggle = { synExpanded = !synExpanded },
            ) {
                RelatedWordsList(synonymsL2, onAddRelatedToLearning, onAddRelatedToFavorites)
            }
        }

        if (showSynonymsAntonyms && antonymsL2.isNotEmpty()) {
            CollapsibleSection(
                title = "Antonimy",
                expanded = antExpanded,
                onToggle = { antExpanded = !antExpanded },
            ) {
                RelatedWordsList(antonymsL2, onAddRelatedToLearning, onAddRelatedToFavorites)
            }
        }

        if (showPeriphrases && !periphrases.isNullOrEmpty()) {
            Text(
                "PERYFRAZY",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
            periphrases.forEachIndexed { index, item ->
                val p = item.jsonObject
                val key = "p$index"
                val formula = p["formula_l2"]?.jsonPrimitive?.content.orEmpty()
                CollapsibleSection(
                    title = formula.ifBlank { "Peryfraza ${index + 1}" },
                    expanded = expandedPeri[key] == true,
                    onToggle = { expandedPeri[key] = expandedPeri[key] != true },
                ) {
                    p["gloss_l1"]?.jsonPrimitive?.content?.let {
                        Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(10.dp))
                    }
                    p["examples"]?.jsonArray?.firstOrNull()?.jsonObject?.let { ex ->
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(ex["l2"]?.jsonPrimitive?.content.orEmpty(), fontWeight = FontWeight.Medium)
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    ex["l1"]?.jsonPrimitive?.content.orEmpty(),
                                    style = MaterialTheme.typography.bodySmall,
                                    fontStyle = FontStyle.Italic,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }

        if (finiteKeys.isNotEmpty() || nonFiniteKeys.isNotEmpty()) {
            Text(
                "ODMIANA",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
            nonFiniteKeys.forEach { key ->
                val form = nonFinite?.get(key)?.jsonPrimitive?.content.orEmpty()
                if (form.isNotBlank()) {
                    CollapsibleSection(
                        title = tenseLabel(key),
                        expanded = expandedTenses[key] == true,
                        onToggle = { expandedTenses[key] = expandedTenses[key] != true },
                    ) {
                        Text(form, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
            finiteKeys.forEach { key ->
                val forms = tenseMap?.get(key)?.jsonObject ?: return@forEach
                CollapsibleSection(
                    title = tenseLabel(key),
                    expanded = expandedTenses[key] == true,
                    onToggle = { expandedTenses[key] = expandedTenses[key] != true },
                ) {
                    orderedPersons(forms).forEach { (person, form) ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(person, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(form, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        }
    }

    usagesModal?.let { usages ->
        Dialog(
            onDismissRequest = { usagesModal = null },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable { usagesModal = null }
                    .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = MaterialTheme.colorScheme.surface,
                    tonalElevation = 6.dp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable(enabled = false) {},
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text("Przykłady użycia", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        usages.forEach { (l2, l1) ->
                            Spacer(Modifier.height(14.dp))
                            Text(l2, fontWeight = FontWeight.Medium)
                            if (l1.isNotBlank()) {
                                Spacer(Modifier.height(4.dp))
                                Text(l1, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Spacer(Modifier.height(12.dp))
                        Text(
                            "Dotknij poza oknem, aby zamknąć",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CollapsibleSection(
    title: String,
    expanded: Boolean,
    onToggle: () -> Unit,
    content: @Composable () -> Unit,
) {
    AppCard {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggle)
                    .padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                )
            }
            if (expanded) {
                content()
                Spacer(Modifier.height(10.dp))
            }
        }
    }
}

@Composable
private fun RelatedWordsList(
    words: List<RelatedWord>,
    onAddToLearning: ((RelatedWord) -> Unit)?,
    onAddToFavorites: ((RelatedWord) -> Unit)?,
) {
    words.forEach { word ->
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(word.lemma, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                word.glossL1?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            word.pos?.let { TagChip(posLabelPl(it).ifBlank { it }) }
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

private fun parseFlashRelatedWords(raw: JsonArray?): List<RelatedWord> {
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

private fun tenseLabel(key: String): String =
    VERB_TENSES.firstOrNull { it.first == key }?.second
        ?: NON_FINITE_FORMS.firstOrNull { it.first == key }?.second
        ?: key.replace("_", " ")

private fun orderedPersons(forms: JsonObject): List<Pair<String, String>> {
    val known = PERSON_ORDER.mapNotNull { person ->
        forms[person]?.jsonPrimitive?.content?.let { person to it }
    }
    val rest = forms.entries
        .filter { it.key !in PERSON_ORDER }
        .map { it.key to it.value.jsonPrimitive.content }
    return known + rest
}
