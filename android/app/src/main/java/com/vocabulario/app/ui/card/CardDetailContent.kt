package com.vocabulario.app.ui.card

import android.speech.tts.TextToSpeech
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
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.vocabulario.app.R
import com.vocabulario.app.data.CardSectionWaiting
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.RelatedMembershipIndex
import com.vocabulario.app.data.formatLemmaWithArticle
import com.vocabulario.app.data.conjugationFromContent
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.examplesForUserLevel
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.resolveVisibleTenseKeys
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.SpeakIconButton
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull

const val WORD_FAMILY_PAGE_SIZE = 4

data class RelatedWord(
    val lemma: String,
    val glossL1: String?,
    val pos: String?,
    val article: String? = null,
    val sourceCardId: String? = null,
    val joinWordFamily: Boolean = false,
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
                    article = el["article"].asJsonString(),
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

@Composable
fun CardDetailContent(
    content: JsonObject,
    lemmaFallback: String,
    languageCode: String? = null,
    compact: Boolean = false,
    /** Pełna karta z listy — wszystkie sekcje, bez ustawień układu trybu nauki. */
    fullDetail: Boolean = false,
    userTenses: List<String>? = null,
    userCefr: String = "A2",
    enrichmentStatus: String = "ready",
    enrichmentError: String? = null,
    /** True tylko gdy karta jest jeszcze w odpytywaniu procesu. */
    stillPolling: Boolean = false,
    profile: LanguageProfileResponse? = null,
    onAddRelated: ((RelatedWord) -> Unit)? = null,
    learningLemmas: Set<String> = emptySet(),
    relatedMembership: RelatedMembershipIndex = RelatedMembershipIndex.Empty,
    /** Gdy false — przewijanie obsługuje rodzic (np. pełny widok z listy). */
    scrollable: Boolean = true,
    /** False gdy hasło jest przyklejone poza tym kompozytem. */
    showHeadword: Boolean = true,
) {
    val lang = languageCode ?: content["language"].asJsonString() ?: "en"
    val tts = rememberL2Tts(lang)

    val lemma = content["lemma"].asJsonString() ?: lemmaFallback
    val pos = content["pos"].asJsonString()
    val headwordNote = content["headword_note"].asJsonString()
    val pattern = content["pattern"].asJsonString()
    val entryKind = content["entry_kind"].asJsonString()
    val meanings = content["meanings"].asJsonArray() ?: JsonArray(emptyList())
    val hasMeaningContent = meanings.any { el ->
        val m = el.asJsonObject() ?: return@any false
        !m["gloss_l1"].asJsonString().isNullOrBlank() ||
            !(m["examples"].asJsonArray()?.isEmpty() ?: true)
    }
    val relatedPending = content["related_pending"].let { raw ->
        when (raw) {
            is JsonPrimitive -> raw.booleanOrNull
            else -> null
        }
    }
    val synonymsL2 = parseRelatedWords(content["synonyms_l2"].asJsonArray())
    val antonymsL2 = parseRelatedWords(content["antonyms_l2"].asJsonArray())
    val wordFamilyL2 = parseRelatedWords(content["word_family_l2"].asJsonArray())
    val associationsL2 = parseRelatedWords(content["associations_l2"].asJsonArray())
    val waitMeanings = CardSectionWaiting.meanings(hasMeaningContent, enrichmentStatus, stillPolling)
    val waitRelated = { empty: Boolean ->
        CardSectionWaiting.related(empty, enrichmentStatus, stillPolling, relatedPending)
    }
    val conjugation = conjugationFromContent(content)
    val tenseMap = conjugation?.get("tenses").asJsonObject()
    val nonFinite = conjugation?.get("non_finite").asJsonObject()
    val periphrases = conjugation?.get("periphrases").asJsonArray()
    val uiMeta = conjugation?.get("ui_meta").asJsonObject()
    val uiHints = content["ui_hints"].asJsonObject() ?: uiMeta
    val showConjugationHint = when (val raw = uiHints?.get("show_conjugation")) {
        null -> {
            val p = pos?.trim()?.lowercase().orEmpty()
            p == "verb" || p == "construction"
        }
        is JsonPrimitive -> raw.contentOrNull?.equals("false", ignoreCase = true) != true &&
            raw.toString() != "false"
        else -> true
    }
    val showConjHint = conjugation != null && (fullDetail || showConjugationHint)
    val waitInflection = CardSectionWaiting.inflection(
        hasInflection = conjugation != null,
        status = enrichmentStatus,
        stillPolling = stillPolling,
        expectInflection = showConjugationHint,
    )
    val profileTenses = userTenses.orEmpty()
    val catalogKeys = LanguagePacks.tenseCatalog(lang).map { it.key }
    val visibleFinite = resolveVisibleTenseKeys(
        profileTenses = profileTenses,
        tenseMapKeys = tenseMap?.keys.orEmpty(),
        catalogKeys = catalogKeys,
        learningLang = lang,
    )
    val visibleNonFinite = (nonFinite?.keys?.toList().orEmpty())
        .ifEmpty { LanguagePacks.get(lang).nonFinite.map { it.key } }
        .filter { nonFinite?.containsKey(it) == true }

    val detailScroll = remember(lemma) { ScrollState(0) }
    LaunchedEffect(lemma) { detailScroll.scrollTo(0) }

    Column(
        modifier = when {
            compact || !scrollable -> Modifier.fillMaxWidth()
            else -> Modifier.fillMaxWidth().verticalScroll(detailScroll)
        },
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (enrichmentStatus == "failed") {
            AppCard {
                Text(
                    enrichmentError?.takeIf { it.isNotBlank() }
                        ?: stringResource(R.string.creating_card_failed),
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        if (!pattern.isNullOrBlank() || (!entryKind.isNullOrBlank() && entryKind != "lemma")) {
            AppCard {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        when (entryKind) {
                            "construction" -> stringResource(R.string.kind_construction)
                            "phrase" -> stringResource(R.string.kind_phrase)
                            "sentence" -> stringResource(R.string.kind_sentence)
                            else -> stringResource(R.string.card_headword)
                        },
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.SemiBold,
                    )
                    if (!pattern.isNullOrBlank()) {
                        Text(
                            pattern,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                }
            }
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (showHeadword) {
                Text(
                    lemma,
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                )
            }
            headwordNote?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.height(6.dp))
                Text(
                    it,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
            }
            if (pos != null && !pos.equals("unknown", ignoreCase = true)) {
                val label = localizedPosLabel(pos)
                if (label.isNotBlank()) {
                    Spacer(modifier = Modifier.height(10.dp))
                    TagChip(label)
                }
            }
            Spacer(Modifier.height(16.dp))
            HorizontalDivider(
                modifier = Modifier.fillMaxWidth(0.55f),
                color = MaterialTheme.colorScheme.outlineVariant,
            )
            Spacer(Modifier.height(14.dp))
            SpeakIconButton(onClick = { tts.speak(lemma, "lemma") })
        }

        if ((!compact || fullDetail) && (synonymsL2.isNotEmpty() || waitRelated(synonymsL2.isEmpty())) && !fullDetail) {
            if (synonymsL2.isNotEmpty()) {
                RelatedWordsSection(
                    title = stringResource(R.string.section_synonyms_short),
                    words = synonymsL2,
                    onAdd = onAddRelated,
                    learningLemmas = learningLemmas,
                    relatedMembership = relatedMembership,
                )
            } else {
                SectionLoadingCard(title = stringResource(R.string.section_synonyms_short))
            }
        }

        when {
            hasMeaningContent -> meanings.forEach { meaningEl ->
                val meaning = meaningEl.asJsonObject() ?: return@forEach
                if (fullDetail) {
                    MeaningFullDetailCard(
                        meaning = meaning,
                        userCefr = userCefr,
                        tts = tts,
                    )
                } else {
                    MeaningCompactCard(
                        meaning = meaning,
                        compact = compact,
                        userCefr = userCefr,
                        tts = tts,
                    )
                }
            }
            waitMeanings -> SectionLoadingCard(title = stringResource(R.string.card_preparing))
        }

        if ((!compact || fullDetail) && (synonymsL2.isNotEmpty() || waitRelated(synonymsL2.isEmpty())) && fullDetail) {
            if (synonymsL2.isNotEmpty()) {
                RelatedWordsSection(
                    title = stringResource(R.string.section_synonyms_short),
                    words = synonymsL2,
                    onAdd = onAddRelated,
                    learningLemmas = learningLemmas,
                    relatedMembership = relatedMembership,
                )
            } else {
                SectionLoadingCard(title = stringResource(R.string.section_synonyms_short))
            }
        }

        if ((!compact || fullDetail) && (antonymsL2.isNotEmpty() || waitRelated(antonymsL2.isEmpty()))) {
            if (antonymsL2.isNotEmpty()) {
                RelatedWordsSection(
                    title = stringResource(R.string.section_antonyms_short),
                    words = antonymsL2,
                    onAdd = onAddRelated,
                    learningLemmas = learningLemmas,
                    relatedMembership = relatedMembership,
                )
            } else {
                SectionLoadingCard(title = stringResource(R.string.section_antonyms_short))
            }
        }

        if ((!compact || fullDetail) && (wordFamilyL2.isNotEmpty() || waitRelated(wordFamilyL2.isEmpty()))) {
            if (wordFamilyL2.isNotEmpty()) {
                RelatedWordsSection(
                    title = stringResource(R.string.section_word_family),
                    words = wordFamilyL2,
                    onAdd = onAddRelated,
                    learningLemmas = learningLemmas,
                    relatedMembership = relatedMembership,
                    pageSize = WORD_FAMILY_PAGE_SIZE,
                    joinWordFamily = true,
                )
            } else {
                SectionLoadingCard(title = stringResource(R.string.section_word_family))
            }
        }

        if ((!compact || fullDetail) && (associationsL2.isNotEmpty() || waitRelated(associationsL2.isEmpty()))) {
            if (associationsL2.isNotEmpty()) {
                RelatedWordsSection(
                    title = stringResource(R.string.section_associations),
                    words = associationsL2,
                    onAdd = onAddRelated,
                    learningLemmas = learningLemmas,
                    relatedMembership = relatedMembership,
                    pageSize = WORD_FAMILY_PAGE_SIZE,
                )
            } else {
                SectionLoadingCard(title = stringResource(R.string.section_associations))
            }
        }

        if ((!compact || fullDetail) && !periphrases.isNullOrEmpty()) {
            PeriphrasesSection(periphrases = periphrases, tts = tts)
        }

        when {
            showConjHint -> ConjugationTenseAccordions(
                finiteKeys = visibleFinite,
                nonFiniteKeys = visibleNonFinite,
                tenseMap = tenseMap,
                nonFinite = nonFinite,
                conjugation = conjugation,
                lang = lang,
                profile = profile,
                resetKey = lemma,
            )
            waitInflection && (!compact || fullDetail) ->
                SectionLoadingCard(title = stringResource(R.string.section_conjugation))
        }
        if (fullDetail) {
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun SectionLoadingCard(title: String) {
    AppCard {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            CircularProgressIndicator(modifier = Modifier.size(28.dp), strokeWidth = 3.dp)
        }
    }
}

@Composable
private fun CardSubsectionDivider() {
    HorizontalDivider(
        modifier = Modifier.padding(vertical = 12.dp),
        color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f),
    )
}

@Composable
private fun CardSubsectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(12.dp))
}

@Composable
private fun L2L1PairRow(
    l2: String,
    l1: String,
    onSpeak: (() -> Unit)?,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                l2,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            if (l1.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    l1,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 4,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (onSpeak != null) {
            SpeakIconButton(onClick = onSpeak, compact = true)
        }
    }
}

@Composable
private fun MeaningFullDetailCard(
    meaning: JsonObject,
    userCefr: String,
    tts: L2TtsSpeaker,
) {
    val gloss = meaning["gloss_l1"].asJsonString().orEmpty()
    val extraGlosses = meaning["synonyms_l1"].asJsonArray()?.mapNotNull { it.asJsonString() }.orEmpty()
    val usages = meaning["usages"].asJsonArray().orEmpty()
        .mapNotNull { usageEl ->
            when (usageEl) {
                is JsonObject ->
                    (usageEl["l2"].asJsonString() ?: "") to (usageEl["l1"].asJsonString() ?: "")
                else -> (usageEl.asJsonString() ?: "") to ""
            }
        }
        .filter { it.first.isNotBlank() }
    val examples = meaning["examples"].asJsonArray()
        ?.mapNotNull { it.asJsonObject() }
        .orEmpty()

    AppCard {
        Column(modifier = Modifier.padding(16.dp)) {
            if (gloss.isNotBlank()) {
                Text(
                    gloss,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            extraGlosses.forEach { extra ->
                if (extra.isBlank()) return@forEach
                Spacer(Modifier.height(4.dp))
                Text(
                    extra,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (usages.isNotEmpty()) {
                CardSubsectionDivider()
                CardSubsectionTitle(stringResource(R.string.section_usages_short))
                usages.forEachIndexed { index, (l2, l1) ->
                    if (index > 0) CardSubsectionDivider()
                    L2L1PairRow(
                        l2 = l2,
                        l1 = l1,
                        onSpeak = { tts.speak(l2, "usage-$index") },
                    )
                }
            }

            if (examples.isNotEmpty()) {
                CardSubsectionDivider()
                CardSubsectionTitle(stringResource(R.string.correction_section_examples))
                examples.forEachIndexed { index, exObj ->
                    val exampleL2 = exObj["l2"].asJsonString().orEmpty()
                    if (exampleL2.isBlank()) return@forEachIndexed
                    if (index > 0) CardSubsectionDivider()
                    L2L1PairRow(
                        l2 = exampleL2,
                        l1 = exObj["l1"].asJsonString().orEmpty(),
                        onSpeak = { tts.speak(exampleL2, "example-$index") },
                    )
                }
            }
        }
    }
}

@Composable
private fun MeaningCompactCard(
    meaning: JsonObject,
    compact: Boolean,
    userCefr: String,
    tts: L2TtsSpeaker,
) {
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
                        onClick = { tts.speak(detailExampleL2, "example-gloss") },
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
                    stringResource(R.string.section_usages_short),
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
                            onClick = { tts.speak(l2, "usage-$index") },
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

@Composable
internal fun PeriphrasesSection(
    periphrases: JsonArray,
    tts: L2TtsSpeaker,
) {
    AppCard {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                stringResource(R.string.settings_periphrases),
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            periphrases.forEachIndexed { index, item ->
                val p = item.asJsonObject() ?: return@forEachIndexed
                if (index > 0) {
                    HorizontalDivider(
                        modifier = Modifier.padding(vertical = 12.dp),
                        color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f),
                    )
                } else {
                    Spacer(Modifier.height(12.dp))
                }
                val formula = p["formula_l2"].asJsonString().orEmpty()
                val gloss = p["gloss_l1"].asJsonString().orEmpty()
                val ex = p["examples"].asJsonArray()?.firstOrNull().asJsonObject()
                val exL2 = ex?.get("l2").asJsonString().orEmpty()
                val exL1 = ex?.get("l1").asJsonString().orEmpty()
                val speak = exL2.ifBlank { formula }
                Text(
                    formula.ifBlank { stringResource(R.string.periphrase_n, index + 1) },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                if (gloss.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        gloss,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (exL2.isNotBlank() || speak.isNotBlank()) {
                    Spacer(Modifier.height(8.dp))
                    L2L1PairRow(
                        l2 = exL2.ifBlank { formula },
                        l1 = exL1,
                        onSpeak = speak.takeIf { it.isNotBlank() }?.let {
                            { tts.speak(it, "peri-$index") }
                        },
                    )
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
    learningLemmas: Set<String> = emptySet(),
    relatedMembership: RelatedMembershipIndex = RelatedMembershipIndex.Empty,
    pageSize: Int = 0,
    joinWordFamily: Boolean = false,
) {
    var visibleCount by remember(words, pageSize) {
        mutableIntStateOf(if (pageSize > 0) minOf(pageSize, words.size) else words.size)
    }
    val shown = words.take(visibleCount)
    AppCard {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            shown.forEachIndexed { index, word ->
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
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            val hit = relatedMembership.find(word.lemma, word.pos)
                            val shownLemma = hit?.displayLemma
                                ?: formatLemmaWithArticle(word.lemma, word.article)
                            Text(
                                shownLemma,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            word.pos?.takeIf { it.isNotBlank() }?.let { pos ->
                                TagChip(localizedPosLabel(pos).ifBlank { pos })
                            }
                            if (hit != null) {
                                TagChip(
                                    if (hit.isSystemList) stringResource(R.string.list_learning)
                                    else hit.listName,
                                )
                            }
                        }
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
                    val hit = relatedMembership.find(word.lemma, word.pos)
                    when {
                        hit != null -> {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = stringResource(R.string.cd_on_list),
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(26.dp),
                            )
                        }
                        onAdd != null -> {
                            val scheme = MaterialTheme.colorScheme
                            Surface(
                                onClick = {
                                    onAdd(if (joinWordFamily) word.copy(joinWordFamily = true) else word)
                                },
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
            if (pageSize > 0 && visibleCount < words.size) {
                TextButton(onClick = { visibleCount = words.size }) {
                    Text(stringResource(R.string.action_show_more))
                }
            }
        }
    }
}

