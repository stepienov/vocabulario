package com.vocabulario.app.ui.settings

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.ExperimentalFoundationApi
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
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
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
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.AppDialogWindowChrome
import com.vocabulario.app.notifications.NotificationHelper
import com.vocabulario.app.ui.components.AppPillDropdown
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.SettingsCheckRow
import com.vocabulario.app.ui.components.SettingsRadioRow
import com.vocabulario.app.ui.components.SettingsValueSlider
import com.vocabulario.app.ui.components.WheelTimePicker
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        viewModel.setNotificationsEnabled(granted || NotificationHelper.canPost(context))
    }
    fun onRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && !NotificationHelper.canPost(context)) {
            permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            viewModel.setNotificationsEnabled(true)
        }
    }
    LaunchedEffect(Unit) { viewModel.load() }
    LaunchedEffect(state.expanded, state.notificationsEnabled) {
        if (state.expanded == SettingsSection.NOTIFICATIONS &&
            state.notificationsEnabled &&
            Build.VERSION.SDK_INT >= 33 &&
            !NotificationHelper.canPost(context)
        ) {
            permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

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
                    subtitle = stringResource(R.string.settings_mode_vocabulario_only),
                    selected = state.practiceInputPref == "choice",
                    onSelect = { viewModel.setInputPref("choice") },
                    testTag = TestTags.SETTINGS_MODE_CHOICE,
                )
                SettingsRadioRow(
                    stringResource(R.string.settings_mode_type),
                    subtitle = stringResource(R.string.settings_mode_vocabulario_only),
                    selected = state.practiceInputPref == "type",
                    onSelect = { viewModel.setInputPref("type") },
                    showDivider = false,
                    testTag = TestTags.SETTINGS_MODE_TYPE,
                )
            }

            AccordionSection(
                title = stringResource(R.string.settings_direction),
                subtitleAnnotated = directionSubtitle(
                    state.practiceDirection,
                    state.activeProfile?.appLang,
                    state.activeProfile?.learning_lang,
                ),
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
                    label = stringResource(R.string.settings_word_family),
                    checked = state.showWordFamily,
                    onCheckedChange = viewModel::setShowWordFamily,
                    testTag = TestTags.SETTINGS_CHECK_WORD_FAMILY,
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
                SettingsValueSlider(
                    value = state.newCardsPerDay.coerceIn(5, 50),
                    onValueChange = viewModel::setNewCardsPerDay,
                    valueRange = 5..50,
                )
            }

            Spacer(Modifier.height(8.dp))
            SettingsGroupLabel(stringResource(R.string.settings_group_general))

            AccordionSection(
                title = stringResource(R.string.settings_theme),
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
                expanded = state.expanded == SettingsSection.NOTIFICATIONS,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.NOTIFICATIONS) },
                testTag = TestTags.SETTINGS_SECTION_NOTIFICATIONS,
            ) {
                SettingsCheckRow(
                    label = stringResource(R.string.settings_notif_enabled),
                    checked = state.notificationsEnabled,
                    onCheckedChange = { enabled ->
                        if (enabled) onRequestNotificationPermission()
                        else viewModel.setNotificationsEnabled(false)
                    },
                    showDivider = false,
                    testTag = TestTags.SETTINGS_NOTIF_STUDY,
                )
                AnimatedVisibility(
                    visible = state.notificationsEnabled,
                    enter = expandVertically() + fadeIn(),
                    exit = shrinkVertically() + fadeOut(),
                ) {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        Text(
                            stringResource(R.string.settings_study_hour),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Medium,
                            color = MaterialTheme.colorScheme.primary,
                            textAlign = TextAlign.Center,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 4.dp),
                        )
                        WheelTimePicker(
                            hour = state.reminderHour,
                            minute = state.reminderMinute,
                            onHourChange = viewModel::setReminderHour,
                            onMinuteChange = viewModel::setReminderMinute,
                            testTag = TestTags.SETTINGS_NOTIF_TIME,
                        )
                    }
                }
            }

            AccordionSection(
                title = stringResource(R.string.settings_languages),
                expanded = state.expanded == SettingsSection.LANGUAGES,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.LANGUAGES) },
                testTag = TestTags.SETTINGS_SECTION_LANGUAGES,
            ) {
                SettingsDropdown(
                    label = stringResource(R.string.settings_native_lang),
                    options = SUPPORTED_LEARNING_LANGS,
                    selectedCode = state.activeProfile?.appLang ?: "en",
                    onSelect = viewModel::setAppLang,
                    testTag = TestTags.SETTINGS_NATIVE_LANG,
                )
                SettingsDropdown(
                    label = stringResource(R.string.settings_i_learn),
                    options = SUPPORTED_LEARNING_LANGS,
                    selectedCode = state.activeProfile?.learning_lang ?: "en",
                    onSelect = viewModel::setLearningLang,
                    testTag = TestTags.SETTINGS_LEARNING_LANG,
                )
            }

            AccordionSection(
                title = stringResource(R.string.settings_level),
                expanded = state.expanded == SettingsSection.CEFR,
                onHeaderClick = { viewModel.toggleSection(SettingsSection.CEFR) },
                testTag = TestTags.SETTINGS_SECTION_CEFR,
                showDivider = false,
            ) {
                val cefrIndex = CEFR_LEVELS.indexOf(state.cefrLevel).coerceAtLeast(0)
                SettingsValueSlider(
                    value = cefrIndex,
                    onValueChange = {},
                    onValueChangeFinished = { viewModel.setCefr(CEFR_LEVELS[it]) },
                    valueRange = 0 until CEFR_LEVELS.size,
                    tickLabels = CEFR_LEVELS,
                    showValueAbove = false,
                )
            }

            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SETTINGS_LOGOUT),
                shape = AppButtonShape,
            ) { Text(stringResource(R.string.action_logout)) }
            Spacer(Modifier.height(80.dp))
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
            .background(
                if (selected) MaterialTheme.colorScheme.primaryContainer
                else Color.Transparent,
            )
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
        AppDialogWindowChrome()
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
                AppDialogButtonRow(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                    secondaryText = stringResource(R.string.action_cancel),
                    onSecondary = onBack,
                    primaryText = stringResource(R.string.action_ok),
                    onPrimary = onConfirm,
                )
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun AccordionSection(
    title: String,
    expanded: Boolean,
    onHeaderClick: () -> Unit,
    testTag: String? = null,
    subtitle: String? = null,
    subtitleAnnotated: AnnotatedString? = null,
    showDivider: Boolean = true,
    content: @Composable () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val headerBg = if (expanded) scheme.primaryContainer else Color.Transparent
    val bodyBg = if (expanded) scheme.surfaceVariant else Color.Transparent
    val bringIntoViewRequester = remember { BringIntoViewRequester() }
    val subtitleText = subtitleAnnotated ?: subtitle?.let { AnnotatedString(it) }
    LaunchedEffect(expanded) {
        if (expanded) {
            delay(340)
            bringIntoViewRequester.bringIntoView()
        }
    }
    AppCard(modifier = Modifier.bringIntoViewRequester(bringIntoViewRequester)) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(headerBg)
                    .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
                    .clickable(onClick = onHeaderClick)
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    if (subtitleText != null) {
                        Spacer(Modifier.height(2.dp))
                        Text(subtitleText, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
                    }
                }
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    tint = scheme.onSurfaceVariant,
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
                        .background(bodyBg)
                        .padding(bottom = 4.dp),
                ) {
                    if (showDivider) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp)
                                .height(1.dp)
                                .background(scheme.outline),
                        )
                    }
                    content()
                }
            }
        }
    }
}

@Composable
private fun SettingsDropdown(
    label: String,
    options: List<Pair<String, String>>,
    selectedCode: String,
    onSelect: (String) -> Unit,
    testTag: String? = null,
) {
    AppPillDropdown(
        options = options,
        selectedCode = selectedCode,
        onSelect = onSelect,
        label = label,
        testTag = testTag,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}

@Composable
private fun modeSummary(pref: String): String = when (pref) {
    "type" -> stringResource(R.string.settings_mode_type)
    "flashcard" -> stringResource(R.string.settings_mode_flash)
    else -> stringResource(R.string.settings_mode_choice)
}

@Composable
private fun directionChoice(dir: String, native: String?, learning: String?): String {
    val n = native?.let { langDisplayName(it) } ?: stringResource(R.string.settings_native_lang)
    val l = learning?.let { langDisplayName(it) } ?: stringResource(R.string.settings_learning_lang)
    return when (dir) {
        "l1_to_l2" -> n
        "l2_to_l1" -> l
        else -> stringResource(R.string.settings_direction_random)
    }
}

@Composable
private fun directionSubtitle(dir: String, native: String?, learning: String?): AnnotatedString {
    val choice = directionChoice(dir, native, learning)
    val template = stringResource(R.string.settings_direction_sub)
    val token = "%1\$s"
    val at = template.indexOf(token)
    if (at < 0) {
        return buildAnnotatedString {
            append(template)
            withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(choice) }
        }
    }
    return buildAnnotatedString {
        append(template.substring(0, at))
        withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(choice) }
        append(template.substring(at + token.length))
    }
}
