package com.vocabulario.app.ui.card

import android.speech.tts.TextToSpeech
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
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
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.res.stringResource
import com.vocabulario.app.R
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.conjugationFromContent
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.examplesForUserLevel
import com.vocabulario.app.data.tenseLabelForProfile
import com.vocabulario.app.data.resolveVisibleTenseKeys
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.SpeakIconButton
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.util.Locale

private fun esPersonOrder() = listOf("yo", "tú", "él", "nosotros", "vosotros", "ellos")

private fun conjugationUiMeta(conjugation: JsonObject?): JsonObject? =
    conjugation?.get("ui_meta").asJsonObject()

private fun personOrderFrom(conjugation: JsonObject?, learningLang: String): List<String> {
    val meta = conjugationUiMeta(conjugation)
    val order = meta?.get("person_order").asJsonArray()
        ?.mapNotNull { it.asJsonString()?.takeIf { s -> s.isNotBlank() } }
        .orEmpty()
    if (order.isNotEmpty()) return order
    return if (learningLang.equals("es", ignoreCase = true)) esPersonOrder() else emptyList()
}

private fun tenseLabel(
    key: String,
    profile: LanguageProfileResponse?,
    conjugation: JsonObject? = null,
): String = tenseLabelForProfile(profile, key, conjugation)

private fun personLabel(key: String, conjugation: JsonObject?): String {
    val labels = conjugationUiMeta(conjugation)?.get("person_labels").asJsonObject()
    return labels?.get(key).asJsonString()?.takeIf { it.isNotBlank() } ?: key
}

private fun isPlaceholderForm(value: String?): Boolean {
    val v = value?.trim().orEmpty()
    return v.isEmpty() || v == "—" || v == "-" || v == "–" || v.equals("n/a", ignoreCase = true)
}

/** Resolve person form; supports flat keys (ja_m) and nested (ja -> m/ż). */
private fun resolvePersonForm(forms: JsonObject, personKey: String): String? {
    forms[personKey].asJsonString()?.let { return it }
    val parts = personKey.split("_", limit = 2)
    if (parts.size != 2) return null
    val base = parts[0]
    val variant = parts[1].trim().lowercase().trimEnd('.')
    val nested = forms[base].asJsonObject() ?: return null
    val aliases = when (variant) {
        "m", "masc", "masculine", "meski", "męski" -> listOf("m", "m.", "masc", "masculine", "męski", "meski")
        "z", "ż", "f", "fem", "feminine", "zenski", "żeński", "zenska" ->
            listOf("ż", "ż.", "z", "z.", "f", "f.", "fem", "feminine", "żeński", "żeńska")
        else -> listOf(variant, parts[1])
    }
    for (alias in aliases) {
        nested[alias].asJsonString()?.let { return it }
    }
    return null
}

private fun orderedPersons(
    forms: JsonObject,
    conjugation: JsonObject? = null,
    learningLang: String = "en",
): List<Pair<String, String>> {
    val order = personOrderFrom(conjugation, learningLang)
    val known = order.mapNotNull { person ->
        val form = resolvePersonForm(forms, person) ?: forms[person].asJsonString()
        form?.let { personLabel(person, conjugation) to it }
    }
    val rest = forms.entries
        .filter { it.key !in order }
        .mapNotNull { (key, value) ->
            value.asJsonString()?.let { personLabel(key, conjugation) to it }
        }
    return known + rest
}

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
            if (!pos.isNullOrBlank()) {
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

        if (showPeriphrases && !periphrases.isNullOrEmpty()) {
            SectionLabel(stringResource(R.string.section_periphrases))
            periphrases.forEachIndexed { index, item ->
                val p = item.asJsonObject() ?: return@forEachIndexed
                val key = "p$index"
                val formula = p["formula_l2"].asJsonString().orEmpty()
                CollapsibleSection(
                    title = formula.ifBlank { stringResource(R.string.periphrase_n, index + 1) },
                    expanded = expandedPeri[key] == true,
                    onToggle = { expandedPeri[key] = expandedPeri[key] != true },
                ) {
                    p["gloss_l1"].asJsonString()?.let {
                        Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(10.dp))
                    }
                    p["examples"].asJsonArray()?.firstOrNull().asJsonObject()?.let { ex ->
                        val periL2 = ex["l2"].asJsonString().orEmpty()
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
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
                                            onClick = { tts.speak(periL2, "peri-$key") },
                                            compact = true,
                                        )
                                    }
                                }
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    ex["l1"].asJsonString().orEmpty(),
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

        if (conjugationEnabled && (finiteKeys.isNotEmpty() || nonFiniteKeys.isNotEmpty())) {
            SectionLabel(stringResource(R.string.section_conjugation))
            nonFiniteKeys.forEach { key ->
                val form = nonFinite?.get(key).asJsonString().orEmpty()
                if (form.isNotBlank()) {
                    CollapsibleSection(
                        title = tenseLabel(key, profile, conjugation),
                        expanded = expandedTenses[key] == true,
                        onToggle = { expandedTenses[key] = expandedTenses[key] != true },
                    ) {
                        Text(
                            form,
                            fontWeight = FontWeight.SemiBold,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
            finiteKeys.forEach { key ->
                val forms = tenseMap?.get(key).asJsonObject() ?: return@forEach
                val rows = orderedPersons(forms, conjugation, lang)
                if (rows.isNotEmpty() && rows.all { isPlaceholderForm(it.second) }) {
                    return@forEach
                }
                CollapsibleSection(
                    title = tenseLabel(key, profile, conjugation),
                    expanded = expandedTenses[key] == true,
                    onToggle = { expandedTenses[key] = expandedTenses[key] != true },
                ) {
                    ConjugationTable(rows)
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
private fun SectionLabel(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 4.dp),
    )
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
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.primary,
                textAlign = TextAlign.Center,
                letterSpacing = 0.6.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggle)
                    .padding(vertical = 14.dp),
            )
            if (expanded) {
                HorizontalDivider(
                    color = MaterialTheme.colorScheme.outline.copy(alpha = 0.28f),
                )
                Spacer(Modifier.height(14.dp))
                content()
                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

@Composable
private fun ConjugationTable(rows: List<Pair<String, String>>) {
    val scheme = MaterialTheme.colorScheme
    val personStyle = MaterialTheme.typography.bodyMedium
    val formStyle = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.SemiBold)
    val textMeasurer = rememberTextMeasurer()
    val density = LocalDensity.current
    val personColumnWidth = remember(rows, personStyle, density) {
        val maxPx = rows.maxOfOrNull { (person, _) ->
            textMeasurer.measure(text = person, style = personStyle).size.width
        } ?: 0
        with(density) { maxPx.toDp() + 2.dp }
    }
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = scheme.surfaceVariant.copy(alpha = 0.55f),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
            rows.forEach { (person, form) ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        person,
                        modifier = Modifier.width(personColumnWidth),
                        textAlign = TextAlign.End,
                        style = personStyle,
                        color = scheme.onSurfaceVariant,
                        maxLines = 1,
                        softWrap = false,
                    )
                    Spacer(Modifier.width(10.dp))
                    Box(
                        modifier = Modifier
                            .width(1.dp)
                            .height(18.dp)
                            .background(scheme.outline.copy(alpha = 0.5f)),
                    )
                    Spacer(Modifier.width(10.dp))
                    ConjugationFormText(
                        text = form,
                        style = formStyle,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun ConjugationFormText(
    text: String,
    style: androidx.compose.ui.text.TextStyle,
    modifier: Modifier = Modifier,
) {
    Text(
        text = text,
        modifier = modifier,
        textAlign = TextAlign.Start,
        style = style,
        softWrap = true,
        overflow = TextOverflow.Clip,
    )
}

@Composable
private fun RelatedWordsList(
    words: List<RelatedWord>,
    onAdd: ((RelatedWord) -> Unit)?,
    learningLemmas: Set<String> = emptySet(),
) {
    words.forEachIndexed { index, word ->
        if (index > 0) {
            HorizontalDivider(
                modifier = Modifier.padding(vertical = 10.dp),
                color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f),
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    word.lemma,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
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
            }
            if (onAdd != null && !learningLemmas.contains(word.lemma.trim().lowercase())) {
                val scheme = MaterialTheme.colorScheme
                Surface(
                    onClick = { onAdd(word) },
                    shape = CircleShape,
                    color = scheme.primary,
                    contentColor = scheme.onPrimary,
                    modifier = Modifier.size(40.dp),
                ) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                        Icon(
                            Icons.Default.Add,
                            contentDescription = stringResource(R.string.action_add),
                            modifier = Modifier.size(22.dp),
                        )
                    }
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
