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
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.SUPPORTED_LEARNING_LANGS
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.langDisplayName
import com.vocabulario.app.data.verbTensesFor
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
    val learningLang = state.activeProfile?.learning_lang
    val showTensePicker = LanguagePacks.showsTensePicker(learningLang)
    val tenseOptions = remember(learningLang) { verbTensesFor(learningLang) }

    fun openTenseModal() {
        tenseDraft = state.lastCustomTenses.ifEmpty {
            state.selectedTenses.ifEmpty { LanguagePacks.defaultSelectedTenses(learningLang).toSet() }
        }
        tenseModalOpen = true
    }

    AppScreenScaffold(title = stringResource(R.string.settings_title), onBack = onBack) { paddingModifier ->
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
            SettingsGroupLabel(stringResource(R.string.settings_group_study))

            AccordionSection(
                title = stringResource(R.string.settings_mode),
                subtitle = modeSummary(state.practiceInputPref),
                expanded = state.expanded == SettingsSection.MODE,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.MODE) },
                testTag = TestTags.SETTINGS_SECTION_MODE,
            ) {
                SettingsRadioRow(
                    stringResource(R.string.settings_mode_flash),
                    selected = state.practiceInputPref == "flashcard",
                    onSelect = { viewModel.setInputPref("flashcard") },
                    testTag = TestTags.SETTINGS_MODE_FLASH,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_mode_choice),
                    selected = state.practiceInputPref == "choice",
                    onSelect = { viewModel.setInputPref("choice") },
                    testTag = TestTags.SETTINGS_MODE_CHOICE,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_mode_type),
                    selected = state.practiceInputPref == "type",
                    onSelect = { viewModel.setInputPref("type") },
                    showDivider = false,
                    testTag = TestTags.SETTINGS_MODE_TYPE,
                )
            }

            AccordionSection(
                title = stringResource(R.string.settings_direction),
                subtitle = directionSummary(state.practiceDirection, state.activeProfile?.appLang, state.activeProfile?.learning_lang),
                expanded = state.expanded == SettingsSection.DIRECTION,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.DIRECTION) },
                testTag = TestTags.SETTINGS_SECTION_DIRECTION,
            ) {
                val native = langDisplayName(state.activeProfile?.appLang ?: "en")
                val learning = langDisplayName(state.activeProfile?.learning_lang ?: "en")
                SettingsRadioRow(
                    stringResource(R.string.settings_direction_first, native),
                    selected = state.practiceDirection == "l1_to_l2",
                    onSelect = { viewModel.setDirection("l1_to_l2") },
                    testTag = TestTags.SETTINGS_DIR_L1_TO_L2,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_direction_first, learning),
                    selected = state.practiceDirection == "l2_to_l1",
                    onSelect = { viewModel.setDirection("l2_to_l1") },
                    testTag = TestTags.SETTINGS_DIR_L2_TO_L1,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_direction_random),
                    selected = state.practiceDirection == "random",
                    onSelect = { viewModel.setDirection("random") },
                    showDivider = false,
                    testTag = TestTags.SETTINGS_DIR_RANDOM,
                )
            }

            AccordionSection(
                title = stringResource(R.string.settings_card_layout),
                subtitle = stringResource(R.string.settings_card_layout_sub),
                expanded = state.expanded == SettingsSection.CARD_LAYOUT,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.CARD_LAYOUT) },
                testTag = TestTags.SETTINGS_SECTION_CARD_LAYOUT,
            ) {
                SettingsCheckRow(
                    label = stringResource(R.string.settings_examples),
                    checked = state.showExampleSentences,
                    onCheckedChange = viewModel::setShowExampleSentences,
                    testTag = TestTags.SETTINGS_CHECK_EXAMPLES,
                )
                SettingsCheckRow(
                    label = stringResource(R.string.settings_usages),
                    checked = state.showUsages,
                    onCheckedChange = viewModel::setShowUsages,
                    testTag = TestTags.SETTINGS_CHECK_USAGES,
                )
                SettingsCheckRow(
                    label = stringResource(R.string.settings_periphrases),
                    checked = state.showPeriphrases,
                    onCheckedChange = viewModel::setShowPeriphrases,
                    testTag = TestTags.SETTINGS_CHECK_PERIPHRASES,
                )
                SettingsCheckRow(
                    label = stringResource(R.string.settings_syn_ant),
                    checked = state.showSynonyms && state.showAntonyms,
                    onCheckedChange = viewModel::setShowSynonymsAndAntonyms,
                    testTag = TestTags.SETTINGS_CHECK_SYN_ANT,
                )
                SettingsCheckRow(
                    label = stringResource(R.string.settings_conjugation),
                    checked = state.showConjugation,
                    onCheckedChange = viewModel::setShowConjugation,
                    showDivider = state.showConjugation && showTensePicker,
                    testTag = TestTags.SETTINGS_CHECK_CONJUGATION,
                )
                AnimatedVisibility(visible = state.showConjugation && showTensePicker) {
                    Column(modifier = Modifier.padding(start = 8.dp)) {
                        SettingsRadioRow(
                            label = stringResource(R.string.settings_all_tenses),
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
                title = stringResource(R.string.settings_limits),
                subtitle = stringResource(R.string.settings_new_per_day, state.newCardsPerDay),
                expanded = state.expanded == SettingsSection.LIMITS,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.LIMITS) },
                testTag = TestTags.SETTINGS_SECTION_LIMITS,
            ) {
                var text by remember(state.newCardsPerDay) { mutableStateOf(state.newCardsPerDay.toString()) }
                val draft = text.toIntOrNull()
                val canConfirm = draft != null && draft != state.newCardsPerDay && draft in 1..200
                OutlinedTextField(
                    value = text,
                    onValueChange = { raw -> text = raw.filter { it.isDigit() }.take(3) },
                    label = { Text(stringResource(R.string.settings_new_limit)) },
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
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.tertiary,
                        contentColor = MaterialTheme.colorScheme.onTertiary,
                    ),
                ) { Text(stringResource(R.string.action_confirm)) }
            }

            Spacer(Modifier.height(8.dp))
            SettingsGroupLabel(stringResource(R.string.settings_group_general))

            AccordionSection(
                title = stringResource(R.string.settings_theme),
                subtitle = themeSummary(state.theme),
                expanded = state.expanded == SettingsSection.THEME,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.THEME) },
                testTag = TestTags.SETTINGS_SECTION_THEME,
            ) {
                SettingsRadioRow(
                    stringResource(R.string.settings_theme_light),
                    selected = state.theme == "light",
                    onSelect = { viewModel.setTheme("light") },
                    testTag = TestTags.SETTINGS_THEME_LIGHT,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_theme_dark),
                    selected = state.theme == "dark",
                    onSelect = { viewModel.setTheme("dark") },
                    testTag = TestTags.SETTINGS_THEME_DARK,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_theme_system),
                    selected = state.theme == "system",
                    onSelect = { viewModel.setTheme("system") },
                    showDivider = false,
                    testTag = TestTags.SETTINGS_THEME_SYSTEM,
                )
            }

            AccordionSection(
                title = stringResource(R.string.settings_notifications),
                subtitle = stringResource(R.string.settings_notifications_summary),
                expanded = state.expanded == SettingsSection.NOTIFICATIONS,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.NOTIFICATIONS) },
                testTag = TestTags.SETTINGS_SECTION_NOTIFICATIONS,
            ) {
                SettingsCheckRow(
                    label = stringResource(R.string.settings_notif_study),
                    checked = state.studyReminderEnabled,
                    onCheckedChange = viewModel::setStudyReminderEnabled,
                    testTag = TestTags.SETTINGS_NOTIF_STUDY,
                )
                OutlinedTextField(
                    value = state.reminderHour.toString(),
                    onValueChange = { raw ->
                        raw.toIntOrNull()?.let(viewModel::setReminderHour)
                    },
                    label = { Text(stringResource(R.string.settings_reminder_hour)) },
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                )
                SettingsCheckRow(
                    label = stringResource(R.string.settings_notif_cards),
                    checked = state.cardsReadyPushEnabled,
                    onCheckedChange = viewModel::setCardsReadyPushEnabled,
                    showDivider = false,
                    testTag = TestTags.SETTINGS_NOTIF_CARDS,
                )
            }

            AccordionSection(
                title = stringResource(R.string.settings_languages),
                subtitle = languagesSummary(
                    state.activeProfile?.appLang,
                    state.activeProfile?.learning_lang,
                ),
                expanded = state.expanded == SettingsSection.LANGUAGES,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.LANGUAGES) },
                testTag = TestTags.SETTINGS_SECTION_LANGUAGES,
            ) {
                Text(
                    stringResource(R.string.settings_langs_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                )
                SettingsDropdown(
                    label = stringResource(R.string.settings_native_lang),
                    options = SUPPORTED_LEARNING_LANGS,
                    selectedCode = state.activeProfile?.appLang ?: "en",
                    onSelect = viewModel::setAppLang,
                    testTag = TestTags.SETTINGS_NATIVE_LANG,
                )
                SettingsDropdown(
                    label = stringResource(R.string.settings_learning_lang),
                    options = SUPPORTED_LEARNING_LANGS,
                    selectedCode = state.activeProfile?.learning_lang ?: "en",
                    onSelect = viewModel::setLearningLang,
                    testTag = TestTags.SETTINGS_LEARNING_LANG,
                )
                if (LanguagePacks.showsTensePicker(state.activeProfile?.learning_lang)) {
                    Text(
                        stringResource(R.string.settings_tense_labels),
                        style = MaterialTheme.typography.labelLarge,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    )
                    SettingsRadioRow(
                        stringResource(R.string.settings_tense_labels_app),
                        selected = state.tenseLabelLang == "app_lang",
                        onSelect = { viewModel.setTenseLabelLang("app_lang") },
                    )
                    SettingsRadioRow(
                        stringResource(R.string.settings_tense_labels_learning),
                        selected = state.tenseLabelLang == "learning_lang",
                        onSelect = { viewModel.setTenseLabelLang("learning_lang") },
                        showDivider = false,
                    )
                }
            }

            AccordionSection(
                title = stringResource(R.string.settings_level),
                subtitle = state.cefrLevel,
                expanded = state.expanded == SettingsSection.CEFR,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.CEFR) },
                testTag = TestTags.SETTINGS_SECTION_CEFR,
            ) {
                SettingsDropdown(
                    label = stringResource(R.string.settings_cefr_known),
                    options = CEFR_LEVELS.map { it to it },
                    selectedCode = state.cefrLevel,
                    onSelect = viewModel::setCefr,
                )
            }

            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_LOGOUT),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.action_logout)) }
            Spacer(Modifier.height(32.dp))
        }
    }

    if (tenseModalOpen && tenseOptions.isNotEmpty()) {
        TensePickerDialog(
            options = tenseOptions,
            draft = tenseDraft,
            onToggle = { key ->
                tenseDraft = tenseDraft.toMutableSet().also { set ->
                    if (key in set) set.remove(key) else set.add(key)
                }
            },
            onBack = { tenseModalOpen = false },
            onConfirm = {
                if (tenseDraft.isEmpty()) {
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
            stringResource(R.string.settings_selected_tenses),
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.weight(1f),
        )
        if (showEdit) {
            Text(
                stringResource(R.string.action_edit),
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
    options: List<Pair<String, String>>,
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
                    stringResource(R.string.settings_selected_tenses),
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
                    options.forEachIndexed { index, (key, label) ->
                        SettingsCheckRow(
                            label = label,
                            checked = key in draft,
                            onCheckedChange = { onToggle(key) },
                            showDivider = index < options.lastIndex,
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
                        Text(stringResource(R.string.action_cancel), color = scheme.error)
                    }
                    Button(
                        onClick = onConfirm,
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = scheme.tertiary,
                            contentColor = scheme.onTertiary,
                        ),
                    ) {
                        Text(stringResource(R.string.action_confirm))
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
    testTag: String? = null,
    content: @Composable () -> Unit,
) {
    AppCard {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
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
    testTag: String? = null,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedLabel = options.firstOrNull { it.first.equals(selectedCode, true) }?.second ?: selectedCode
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .then(if (testTag != null) Modifier.testTag(testTag) else Modifier),
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

@Composable
private fun modeSummary(pref: String): String = when (pref) {
    "type" -> stringResource(R.string.settings_mode_type)
    "flashcard" -> stringResource(R.string.settings_mode_flash)
    else -> stringResource(R.string.settings_mode_choice)
}

@Composable
private fun directionSummary(dir: String, native: String?, learning: String?): String {
    val n = native?.let { langDisplayName(it) } ?: "L1"
    val l = learning?.let { langDisplayName(it) } ?: "L2"
    return when (dir) {
        "l1_to_l2" -> stringResource(R.string.settings_direction_first, n)
        "l2_to_l1" -> stringResource(R.string.settings_direction_first, l)
        else -> stringResource(R.string.settings_direction_random)
    }
}

@Composable
private fun themeSummary(theme: String): String = when (theme) {
    "light" -> stringResource(R.string.settings_theme_light)
    "dark" -> stringResource(R.string.settings_theme_dark)
    else -> stringResource(R.string.settings_theme_system)
}

@Composable
private fun languagesSummary(native: String?, learning: String?): String {
    return stringResource(
        R.string.settings_languages_summary,
        langDisplayName(native ?: "?"),
        langDisplayName(learning ?: "?"),
    )
}
