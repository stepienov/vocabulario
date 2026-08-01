package com.vocabulario.app.ui.settings

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.SUPPORTED_LEARNING_LANGS
import com.vocabulario.app.data.SUPPORTED_UI_LANGS
import com.vocabulario.app.data.VERB_TENSES
import com.vocabulario.app.data.langDisplayName
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.SettingsCheckRow
import com.vocabulario.app.ui.components.SettingsRadioRow

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

    var tenseModalOpen by remember { mutableStateOf(false) }
    var tenseDraft by remember { mutableStateOf<Set<String>>(emptySet()) }
    val customTenses = state.selectedTenses.isNotEmpty()

    fun openTenseModal() {
        tenseDraft = state.lastCustomTenses.ifEmpty { state.selectedTenses }
        tenseModalOpen = true
    }

    AppScreenScaffold(title = "Ustawienia", onBack = onBack) { paddingModifier ->
        if (state.loading) {
            CircularProgressIndicator(modifier = paddingModifier.padding(24.dp))
            return@AppScreenScaffold
        }
        Column(
            modifier = paddingModifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            SettingsGroupLabel("DOSTOSUJ NAUKĘ")

            AccordionSection(
                title = "Tryb nauki",
                subtitle = modeSummary(state.practiceInputPref),
                expanded = state.expanded == SettingsSection.MODE,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.MODE) },
            ) {
                SettingsRadioRow(
                    "Test (8 opcji)",
                    selected = state.practiceInputPref == "choice",
                    onSelect = { viewModel.setInputPref("choice") },
                )
                SettingsRadioRow(
                    "Wpisz słowo",
                    selected = state.practiceInputPref == "type",
                    onSelect = { viewModel.setInputPref("type") },
                )
                AnimatedVisibility(visible = state.practiceInputPref == "type") {
                    SettingsCheckRow(
                        label = "Toleruj drobne błędy",
                        subtitle = "Literówki i diakrytyki",
                        checked = state.typingTolerance != "strict",
                        onCheckedChange = viewModel::setTypingTolerance,
                    )
                }
                SettingsRadioRow(
                    "Fiszki",
                    selected = state.practiceInputPref == "flashcard",
                    onSelect = { viewModel.setInputPref("flashcard") },
                    showDivider = false,
                )
            }

            AccordionSection(
                title = "Kierunek nauki",
                subtitle = directionSummary(state.practiceDirection, state.activeProfile?.native_lang, state.activeProfile?.learning_lang),
                expanded = state.expanded == SettingsSection.DIRECTION,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.DIRECTION) },
            ) {
                val native = langDisplayName(state.activeProfile?.native_lang ?: "pl")
                val learning = langDisplayName(state.activeProfile?.learning_lang ?: "es")
                SettingsRadioRow(
                    "Najpierw $native",
                    selected = state.practiceDirection == "l1_to_l2",
                    onSelect = { viewModel.setDirection("l1_to_l2") },
                )
                SettingsRadioRow(
                    "Najpierw $learning",
                    selected = state.practiceDirection == "l2_to_l1",
                    onSelect = { viewModel.setDirection("l2_to_l1") },
                )
                SettingsRadioRow(
                    "Losowo",
                    selected = state.practiceDirection == "random",
                    onSelect = { viewModel.setDirection("random") },
                    showDivider = false,
                )
            }

            AccordionSection(
                title = "Układ karty",
                subtitle = "Co widać po odpowiedzi",
                expanded = state.expanded == SettingsSection.CARD_LAYOUT,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.CARD_LAYOUT) },
            ) {
                SettingsCheckRow(
                    label = "Przykłady zdań",
                    checked = state.showExampleSentences,
                    onCheckedChange = viewModel::setShowExampleSentences,
                )
                SettingsCheckRow(
                    label = "Przykłady użycia",
                    checked = state.showUsages,
                    onCheckedChange = viewModel::setShowUsages,
                )
                SettingsCheckRow(
                    label = "Peryfrazy",
                    checked = state.showPeriphrases,
                    onCheckedChange = viewModel::setShowPeriphrases,
                )
                SettingsCheckRow(
                    label = "Synonimy i przeciwieństwa",
                    checked = state.showSynonyms && state.showAntonyms,
                    onCheckedChange = viewModel::setShowSynonymsAndAntonyms,
                )
                SettingsCheckRow(
                    label = "Koniugacja",
                    checked = state.showConjugation,
                    onCheckedChange = viewModel::setShowConjugation,
                    showDivider = state.showConjugation,
                )
                AnimatedVisibility(visible = state.showConjugation) {
                    Column(modifier = Modifier.padding(start = 8.dp)) {
                        SettingsRadioRow(
                            label = "Wszystkie czasy",
                            selected = !customTenses,
                            onSelect = { viewModel.setAllTenses() },
                        )
                        CustomTensesRadioRow(
                            selected = customTenses,
                            showEdit = customTenses,
                            onSelect = {
                                if (viewModel.selectCustomTenses()) openTenseModal()
                            },
                            onEdit = { openTenseModal() },
                        )
                    }
                }
            }

            AccordionSection(
                title = "Limity",
                subtitle = "${state.newCardsPerDay} nowych / dzień",
                expanded = state.expanded == SettingsSection.LIMITS,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.LIMITS) },
            ) {
                var text by remember(state.newCardsPerDay) { mutableStateOf(state.newCardsPerDay.toString()) }
                val draft = text.toIntOrNull()
                val canConfirm = draft != null && draft != state.newCardsPerDay && draft in 1..200
                OutlinedTextField(
                    value = text,
                    onValueChange = { raw -> text = raw.filter { it.isDigit() }.take(3) },
                    label = { Text("Dzienny limit nowych słówek") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    shape = AppButtonShape,
                )
                Button(
                    onClick = { draft?.let(viewModel::setNewCardsPerDay) },
                    enabled = canConfirm,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .padding(bottom = 12.dp),
                    shape = AppButtonShape,
                ) { Text("Zatwierdź") }
            }

            Spacer(Modifier.height(8.dp))
            SettingsGroupLabel("OGÓLNE")

            AccordionSection(
                title = "Motyw",
                subtitle = themeSummary(state.theme),
                expanded = state.expanded == SettingsSection.THEME,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.THEME) },
            ) {
                SettingsRadioRow("Jasny", selected = state.theme == "light", onSelect = { viewModel.setTheme("light") })
                SettingsRadioRow("Ciemny", selected = state.theme == "dark", onSelect = { viewModel.setTheme("dark") })
                SettingsRadioRow("Domyślny (system)", selected = state.theme == "system", onSelect = { viewModel.setTheme("system") }, showDivider = false)
            }

            AccordionSection(
                title = "Języki",
                subtitle = languagesSummary(state.uiLang, state.activeProfile?.learning_lang),
                expanded = state.expanded == SettingsSection.LANGUAGES,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.LANGUAGES) },
            ) {
                SettingsDropdown(
                    label = "Język aplikacji",
                    options = SUPPORTED_UI_LANGS,
                    selectedCode = state.uiLang,
                    onSelect = viewModel::setUiLang,
                )
                SettingsDropdown(
                    label = "Język nauki",
                    options = SUPPORTED_LEARNING_LANGS,
                    selectedCode = state.activeProfile?.learning_lang ?: "es",
                    onSelect = viewModel::setLearningLang,
                )
            }

            AccordionSection(
                title = "Poziom",
                subtitle = state.cefrLevel,
                expanded = state.expanded == SettingsSection.CEFR,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.CEFR) },
            ) {
                SettingsDropdown(
                    label = "Znajomość języka uczonego",
                    options = CEFR_LEVELS.map { it to it },
                    selectedCode = state.cefrLevel,
                    onSelect = viewModel::setCefr,
                )
            }

            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth(),
                shape = AppButtonShape,
            ) { Text("Wyloguj się") }
            Spacer(Modifier.height(32.dp))
        }
    }

    if (tenseModalOpen) {
        TensePickerDialog(
            draft = tenseDraft,
            onToggle = { key ->
                tenseDraft = tenseDraft.toMutableSet().also { set ->
                    if (key in set) set.remove(key) else set.add(key)
                }
            },
            onBack = { tenseModalOpen = false },
            onConfirm = {
                if (tenseDraft.isEmpty()) {
                    // Nic nie wybrano → bez zmian względem stanu sprzed otwarcia
                    tenseModalOpen = false
                } else {
                    viewModel.setCustomTenses(tenseDraft)
                    tenseModalOpen = false
                    if (state.expanded != SettingsSection.CARD_LAYOUT) {
                        viewModel.toggleSection(SettingsSection.CARD_LAYOUT)
                    }
                }
            },
        )
    }
}

@Composable
private fun SettingsGroupLabel(title: String) {
    Text(
        title,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 8.dp, bottom = 2.dp, start = 4.dp),
    )
}

@Composable
private fun CustomTensesRadioRow(
    selected: Boolean,
    showEdit: Boolean,
    onSelect: () -> Unit,
    onEdit: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onSelect)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "Wybrane czasy",
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.weight(1f),
        )
        if (showEdit) {
            Text(
                "Edytuj",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Medium,
                modifier = Modifier
                    .clickable(onClick = onEdit)
                    .padding(horizontal = 8.dp, vertical = 4.dp),
            )
        }
        CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
            RadioButton(
                selected = selected,
                onClick = onSelect,
                colors = RadioButtonDefaults.colors(selectedColor = MaterialTheme.colorScheme.primary),
            )
        }
    }
}

@Composable
private fun TensePickerDialog(
    draft: Set<String>,
    onToggle: (String) -> Unit,
    onBack: () -> Unit,
    onConfirm: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Dialog(
        onDismissRequest = onBack,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.92f)
                .padding(vertical = 24.dp),
            shape = AppDialogShape,
            color = scheme.surface,
            tonalElevation = 3.dp,
        ) {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    "Wybrane czasy",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = scheme.onSurface,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 16.dp),
                )
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .height(1.dp)
                        .background(scheme.outlineVariant),
                )
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState())
                        .padding(vertical = 4.dp),
                ) {
                    VERB_TENSES.forEachIndexed { index, (key, label) ->
                        SettingsCheckRow(
                            label = label,
                            checked = key in draft,
                            onCheckedChange = { onToggle(key) },
                            showDivider = index < VERB_TENSES.lastIndex,
                        )
                    }
                }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .height(1.dp)
                        .background(scheme.outlineVariant),
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
                ) {
                    OutlinedButton(onClick = onBack, shape = AppButtonShape) {
                        Text("Anuluj", color = scheme.error)
                    }
                    Button(onClick = onConfirm, shape = AppButtonShape) {
                        Text("Zatwierdź")
                    }
                }
            }
        }
    }
}

@Composable
private fun AccordionSection(
    title: String,
    subtitle: String,
    expanded: Boolean,
    onHeaderClick: () -> Unit,
    content: @Composable () -> Unit,
) {
    AppCard {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onHeaderClick)
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(2.dp))
                    Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically() + fadeIn(),
                exit = shrinkVertically() + fadeOut(),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 4.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp)
                            .height(1.dp)
                            .background(MaterialTheme.colorScheme.outlineVariant),
                    )
                    content()
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsDropdown(
    label: String,
    options: List<Pair<String, String>>,
    selectedCode: String,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedLabel = options.firstOrNull { it.first.equals(selectedCode, true) }?.second ?: selectedCode
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier
                .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                .fillMaxWidth(),
            shape = AppButtonShape,
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
            ),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (code, name) ->
                DropdownMenuItem(
                    text = { Text(name) },
                    onClick = {
                        expanded = false
                        onSelect(code)
                    },
                )
            }
        }
    }
}

private fun modeSummary(pref: String) = when (pref) {
    "type" -> "Wpisz słowo"
    "flashcard" -> "Fiszki"
    else -> "Test (8 opcji)"
}

private fun directionSummary(dir: String, native: String?, learning: String?): String {
    val n = native?.let { langDisplayName(it) } ?: "L1"
    val l = learning?.let { langDisplayName(it) } ?: "L2"
    return when (dir) {
        "l1_to_l2" -> "Najpierw $n"
        "l2_to_l1" -> "Najpierw $l"
        else -> "Losowo"
    }
}

private fun themeSummary(theme: String) = when (theme) {
    "light" -> "Jasny"
    "dark" -> "Ciemny"
    else -> "Domyślny"
}

private fun languagesSummary(ui: String, learning: String?): String {
    val uiName = langDisplayName(ui)
    val learn = learning?.let { langDisplayName(it) } ?: "—"
    return "$uiName · nauka: $learn"
}
