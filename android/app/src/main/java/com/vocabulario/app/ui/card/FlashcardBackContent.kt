package com.vocabulario.app.ui.card

import android.speech.tts.TextToSpeech
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.unit.Dp
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.res.stringResource
import com.vocabulario.app.R
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.containsLemma
import com.vocabulario.app.data.conjugationFromContent
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.examplesForUserLevel
import com.vocabulario.app.data.resolveVisibleTenseKeys
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.AppDialogWindowChrome
import com.vocabulario.app.ui.components.LemmaActionRow
import com.vocabulario.app.ui.components.LemmaAddButton
import com.vocabulario.app.ui.components.SpeakIconButton
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.util.Locale

@Composable
fun FlashcardBackContent(
    content: JsonObject,
    lemmaFallback: String,
    userTenses: List<String> = emptyList(),
    userCefr: String = "A2",
    showUsages: Boolean = true,
    showExampleSentences: Boolean = true,
    showSynonyms: Boolean = true,
    showAntonyms: Boolean = true,
    showWordFamily: Boolean = true,
    showPeriphrases: Boolean = true,
    showConjugation: Boolean = true,
    conjugationExpandedDefault: Boolean = false,
    relatedWordsExpandedDefault: Boolean = false,
    profile: LanguageProfileResponse? = null,
    onAddRelated: ((RelatedWord) -> Unit)? = null,
    learningLemmas: Set<String> = emptySet(),
) {
    val lemma = content["lemma"].asJsonString() ?: lemmaFallback
    val pos = content["pos"].asJsonString()
    val ipa = content["ipa"].asJsonString()
    val pattern = content["pattern"].asJsonString()
    val entryKind = content["entry_kind"].asJsonString()
    val lang = content["language"].asJsonString() ?: "en"
    val meanings = content["meanings"].asJsonArray() ?: JsonArray(emptyList())
    val synonymsL2 = parseFlashRelatedWords(content["synonyms_l2"].asJsonArray())
    val antonymsL2 = parseFlashRelatedWords(content["antonyms_l2"].asJsonArray())
    val wordFamilyL2 = parseFlashRelatedWords(content["word_family_l2"].asJsonArray())
    val conjugation = conjugationFromContent(content)
    val tenseMap = conjugation?.get("tenses").asJsonObject()
    val nonFinite = conjugation?.get("non_finite").asJsonObject()
    val periphrases = conjugation?.get("periphrases").asJsonArray()
    val uiHints = content["ui_hints"].asJsonObject() ?: conjugationUiMeta(conjugation)
    val showConjHint = when (val raw = uiHints?.get("show_conjugation")) {
        null -> true
        is JsonPrimitive -> raw.contentOrNull?.equals("false", ignoreCase = true) != true &&
            raw.toString() != "false"
        else -> true
    }
    val conjugationEnabled = showConjugation && showConjHint && conjugation != null

    val tts = rememberL2Tts(lang)

    val profileTenses = userTenses
    val allTenseKeys = tenseMap?.keys?.toList().orEmpty()
    val finiteKeys = if (conjugationEnabled) {
        resolveVisibleTenseKeys(
            profileTenses = profileTenses,
            tenseMapKeys = allTenseKeys,
            catalogKeys = LanguagePacks.tenseCatalog(lang).map { it.key },
        )
    } else {
        emptyList()
    }
    val nonFiniteKeys = if (conjugationEnabled || profileTenses.isNotEmpty()) {
        val keys = nonFinite?.keys?.toList().orEmpty()
        keys.ifEmpty {
            LanguagePacks.get(lang).nonFinite.map { it.key }
                .filter { nonFinite?.containsKey(it) == true }
        }
    } else {
        emptyList()
    }

    var usagesModal by remember { mutableStateOf<List<Pair<String, String>>?>(null) }
    var synExpanded by remember(relatedWordsExpandedDefault) { mutableStateOf(relatedWordsExpandedDefault) }
    var antExpanded by remember(relatedWordsExpandedDefault) { mutableStateOf(relatedWordsExpandedDefault) }
    var familyExpanded by remember(relatedWordsExpandedDefault) { mutableStateOf(relatedWordsExpandedDefault) }
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Nagłówek lematu — bez kafla, żeby nie zlewał się z tłumaczeniami
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
            if (!ipa.isNullOrBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    "[$ipa]",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
            }
            if (!pos.isNullOrBlank() && !pos.equals("imported", ignoreCase = true)) {
                Spacer(Modifier.height(10.dp))
                TagChip(localizedPosLabel(pos).ifBlank { pos })
            }
            Spacer(modifier = Modifier.height(16.dp))
            HorizontalDivider(
                modifier = Modifier.fillMaxWidth(0.55f),
                color = MaterialTheme.colorScheme.outlineVariant,
            )
            Spacer(modifier = Modifier.height(14.dp))
            SpeakIconButton(
                onClick = { tts.speak(lemma, "lemma") },
            )
        }

        if (!pattern.isNullOrBlank() || (!entryKind.isNullOrBlank() && entryKind != "lemma")) {
            SectionLabel(
                when (entryKind) {
                    "construction" -> stringResource(R.string.kind_construction).uppercase()
                    "phrase" -> stringResource(R.string.kind_phrase).uppercase()
                    "sentence" -> stringResource(R.string.kind_sentence).uppercase()
                    else -> stringResource(R.string.card_headword).uppercase()
                }
            )
            if (!pattern.isNullOrBlank()) {
                Text(
                    pattern,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(8.dp))
            }
        }

        if (meanings.isNotEmpty()) {
            SectionLabel(stringResource(R.string.section_meanings))
        }
        meanings.forEach { meaningEl ->
            val meaning = meaningEl.asJsonObject() ?: return@forEach
            val gloss = meaning["gloss_l1"].asJsonString().orEmpty()
            val syns = meaning["synonyms_l1"].asJsonArray()?.mapNotNull { it.asJsonString() }.orEmpty()
            val example = examplesForUserLevel(meaning["examples"].asJsonArray(), userCefr, maxCount = 1).firstOrNull()
            val usages = meaning["usages"].asJsonArray().orEmpty().mapNotNull { usageEl ->
                when (usageEl) {
                    is JsonObject -> {
                        val l2 = usageEl["l2"].asJsonString().orEmpty()
                        val l1 = usageEl["l1"].asJsonString().orEmpty()
                        if (l2.isBlank()) null else l2 to l1
                    }
                    else -> {
                        val l2 = usageEl.asJsonString().orEmpty()
                        if (l2.isBlank()) null else l2 to ""
                    }
                }
            }

            AppCard {
                val hasUsagesLink = showUsages && usages.isNotEmpty()
                Column(
                    modifier = Modifier.padding(
                        start = 16.dp,
                        end = 16.dp,
                        top = 16.dp,
                        bottom = if (hasUsagesLink) 2.dp else 16.dp,
                    ),
                ) {
                    val exampleL2 = if (showExampleSentences && example != null) {
                        example["l2"].asJsonString().orEmpty()
                    } else {
                        ""
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.Top,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                gloss.ifBlank { lemmaFallback },
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            if (syns.isNotEmpty()) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    syns.joinToString(" · "),
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        if (exampleL2.isNotBlank()) {
                            SpeakIconButton(
                                onClick = { tts.speak(exampleL2, "example-$gloss") },
                                compact = true,
                            )
                        }
                    }
                    if (showExampleSentences && example != null && exampleL2.isNotBlank()) {
                        val exampleL1 = example["l1"].asJsonString().orEmpty()
                        Spacer(modifier = Modifier.height(12.dp))
                        Surface(
                            shape = RoundedCornerShape(14.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                                Text(
                                    exampleL2,
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.Medium,
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    exampleL1,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontStyle = FontStyle.Italic,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    if (hasUsagesLink) {
                        Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
                            CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
                                TextButton(
                                    onClick = { usagesModal = usages },
                                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                                ) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                                    ) {
                                        Text(stringResource(R.string.section_usages))
                                        Icon(
                                            Icons.AutoMirrored.Filled.ArrowForward,
                                            contentDescription = null,
                                            modifier = Modifier.size(18.dp),
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if ((showSynonyms && synonymsL2.isNotEmpty()) || (showAntonyms && antonymsL2.isNotEmpty())) {
            SectionLabel(stringResource(R.string.section_syn_ant))
            if (showSynonyms && synonymsL2.isNotEmpty()) {
                CollapsibleSection(
                    title = stringResource(R.string.section_synonyms_short),
                    expanded = synExpanded,
                    onToggle = { synExpanded = !synExpanded },
                ) {
                    RelatedWordsList(synonymsL2, onAddRelated, learningLemmas)
                }
            }
            if (showAntonyms && antonymsL2.isNotEmpty()) {
                CollapsibleSection(
                    title = stringResource(R.string.section_antonyms_title),
                    expanded = antExpanded,
                    onToggle = { antExpanded = !antExpanded },
                ) {
                    RelatedWordsList(antonymsL2, onAddRelated, learningLemmas)
                }
            }
        }

        if (showWordFamily && wordFamilyL2.isNotEmpty()) {
            CollapsibleSection(
                title = stringResource(R.string.section_word_family),
                expanded = familyExpanded,
                onToggle = { familyExpanded = !familyExpanded },
            ) {
                RelatedWordsList(wordFamilyL2, onAddRelated, learningLemmas)
            }
        }

        if (showPeriphrases && !periphrases.isNullOrEmpty()) {
            PeriphrasesSection(periphrases = periphrases, tts = tts)
        }

        if (conjugationEnabled) {
            ConjugationTenseAccordions(
                finiteKeys = finiteKeys,
                nonFiniteKeys = nonFiniteKeys,
                tenseMap = tenseMap,
                nonFinite = nonFinite,
                conjugation = conjugation,
                lang = lang,
                profile = profile,
                expandedDefault = conjugationExpandedDefault,
            )
        }
    }

    usagesModal?.let { usages ->
        Dialog(
            onDismissRequest = { usagesModal = null },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            AppDialogWindowChrome()
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable { usagesModal = null }
                    .padding(24.dp),
                contentAlignment = Alignment.Center,
            ) {
                Surface(
                    shape = AppDialogShape,
                    color = MaterialTheme.colorScheme.surface,
                    tonalElevation = 6.dp,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) {
                        usages.forEachIndexed { index, (l2, l1) ->
                            if (index > 0) {
                                HorizontalDivider(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 10.dp),
                                    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
                                )
                            }
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.Top,
                                horizontalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(l2, fontWeight = FontWeight.Medium)
                                    if (l1.isNotBlank()) {
                                        Spacer(modifier = Modifier.height(2.dp))
                                        Text(
                                            l1,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                                if (l2.isNotBlank()) {
                                    SpeakIconButton(
                                        onClick = { tts.speak(l2, "usage-$index") },
                                        compact = true,
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

@Composable
private fun RelatedWordsList(
    words: List<RelatedWord>,
    onAdd: ((RelatedWord) -> Unit)?,
    learningLemmas: Set<String> = emptySet(),
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        words.forEach { word ->
            LemmaActionRow(
                lemma = word.lemma,
                gloss = word.glossL1,
                belowGloss = {
                    word.pos?.takeIf { it.isNotBlank() }?.let { pos ->
                        Spacer(Modifier.height(8.dp))
                        TagChip(localizedPosLabel(pos).ifBlank { pos })
                    }
                },
                trailing = {
                    if (onAdd != null && !learningLemmas.containsLemma(word.lemma)) {
                        LemmaAddButton(
                            onClick = { onAdd(word) },
                            contentDescription = stringResource(R.string.action_add),
                        )
                    }
                },
            )
        }
    }
}

private fun parseFlashRelatedWords(raw: JsonArray?): List<RelatedWord> {
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
