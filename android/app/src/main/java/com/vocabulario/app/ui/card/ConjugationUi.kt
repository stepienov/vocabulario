package com.vocabulario.app.ui.card

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.vocabulario.app.R
import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.asJsonArray
import com.vocabulario.app.data.asJsonObject
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.data.tenseHeadingForProfile
import com.vocabulario.app.ui.components.AppCard
import kotlinx.serialization.json.JsonObject

private fun esPersonOrder() = listOf("yo", "tú", "él", "nosotros", "vosotros", "ellos")

internal fun conjugationUiMeta(conjugation: JsonObject?): JsonObject? =
    conjugation?.get("ui_meta").asJsonObject()

private fun personOrderFrom(conjugation: JsonObject?, learningLang: String): List<String> {
    val meta = conjugationUiMeta(conjugation)
    val order = meta?.get("person_order").asJsonArray()
        ?.mapNotNull { it.asJsonString()?.takeIf { s -> s.isNotBlank() } }
        .orEmpty()
    if (order.isNotEmpty()) return order
    return if (learningLang.equals("es", ignoreCase = true)) esPersonOrder() else emptyList()
}

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

internal fun orderedPersons(
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
internal fun SectionLabel(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 4.dp),
    )
}

@Composable
internal fun CollapsibleSection(
    title: String,
    expanded: Boolean,
    onToggle: () -> Unit,
    subtitle: String? = null,
    content: @Composable () -> Unit,
) {
    AppCard {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggle)
                    .padding(vertical = 14.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    textAlign = TextAlign.Center,
                    letterSpacing = 0.6.sp,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Normal,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 2.dp),
                    )
                }
            }
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
internal fun ConjugationTenseAccordions(
    finiteKeys: List<String>,
    nonFiniteKeys: List<String>,
    tenseMap: JsonObject?,
    nonFinite: JsonObject?,
    conjugation: JsonObject?,
    lang: String,
    profile: LanguageProfileResponse?,
    expandedDefault: Boolean = false,
) {
    if (finiteKeys.isEmpty() && nonFiniteKeys.isEmpty()) return
    val expandedTenses = remember(expandedDefault, finiteKeys, nonFiniteKeys) {
        mutableStateMapOf<String, Boolean>().apply {
            (finiteKeys + nonFiniteKeys).forEach { put(it, expandedDefault) }
        }
    }
    SectionLabel(stringResource(R.string.section_conjugation))
    nonFiniteKeys.forEach { key ->
        val form = nonFinite?.get(key).asJsonString().orEmpty()
        if (form.isNotBlank()) {
            val heading = tenseHeadingForProfile(profile, key, conjugation)
            CollapsibleSection(
                title = heading.original,
                subtitle = heading.translation,
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
        val heading = tenseHeadingForProfile(profile, key, conjugation)
        CollapsibleSection(
            title = heading.original,
            subtitle = heading.translation,
            expanded = expandedTenses[key] == true,
            onToggle = { expandedTenses[key] = expandedTenses[key] != true },
        ) {
            ConjugationTable(rows)
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
                    Text(
                        text = form,
                        modifier = Modifier.weight(1f),
                        textAlign = TextAlign.Start,
                        style = formStyle,
                        softWrap = true,
                        overflow = TextOverflow.Clip,
                    )
                }
            }
        }
    }
}
