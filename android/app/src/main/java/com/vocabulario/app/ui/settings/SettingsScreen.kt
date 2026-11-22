package com.vocabulario.app.ui.settings

import android.Manifest
import android.content.Intent
import android.os.Build
import android.provider.Settings
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
import androidx.compose.foundation.isSystemInDarkTheme
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.Style
import androidx.compose.material.icons.outlined.SwapHoriz
import androidx.compose.material.icons.outlined.ViewAgenda
import androidx.compose.material.icons.outlined.TrackChanges
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalMinimumInteractiveComponentSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.res.pluralStringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.vocabulario.app.R
import com.vocabulario.app.ui.report.SupportHelpDialog
import com.vocabulario.app.ui.auth.VerifyEmailViewModel
import com.vocabulario.app.ui.auth.deliveryText
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.publicSiteUrl
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.SUPPORTED_LEARNING_LANGS
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.langDisplayName
import com.vocabulario.app.data.TenseHeading
import com.vocabulario.app.data.tenseHeadingsForPicker
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.AppDialogWindowChrome
import com.vocabulario.app.notifications.NotificationHelper
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.AppToggle
import com.vocabulario.app.ui.components.SettingsCheckRow
import com.vocabulario.app.ui.components.SettingsRadioRow
import com.vocabulario.app.ui.components.SettingsValueSlider
import com.vocabulario.app.ui.theme.usesDarkTheme
import kotlinx.coroutines.delay
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
    accountViewModel: AccountSettingsViewModel = hiltViewModel(),
    verifyEmailViewModel: VerifyEmailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val account by accountViewModel.account.collectAsState()
    val changePassword by accountViewModel.changePassword.collectAsState()
    val deleteAccount by accountViewModel.deleteAccount.collectAsState()
    val linkGoogle by accountViewModel.linkGoogle.collectAsState()
    val addPassword by accountViewModel.addPassword.collectAsState()
    val verification by verifyEmailViewModel.state.collectAsState()
    val context = LocalContext.current
    deleteAccount?.let { form ->
        DeleteAccountDialog(
            form = form,
            onPasswordChange = { accountViewModel.updateDeleteAccount(password = it) },
            onConfirmedChange = { accountViewModel.updateDeleteAccount(confirmed = it) },
            onSubmit = { accountViewModel.submitDeleteAccount(context) },
            onDismiss = accountViewModel::closeDeleteAccount,
        )
    }
    linkGoogle?.let { form ->
        LinkGoogleDialog(
            form = form,
            accountEmail = account.email,
            onPasswordChange = accountViewModel::updateLinkGoogle,
            onSubmit = { accountViewModel.submitLinkGoogle(context) },
            onDismiss = accountViewModel::closeLinkGoogle,
        )
    }
    addPassword?.let { form ->
        AddPasswordDialog(
            form = form,
            onNewChange = { accountViewModel.updateAddPassword(new = it) },
            onRepeatChange = { accountViewModel.updateAddPassword(repeat = it) },
            onSubmit = { accountViewModel.submitAddPassword(context) },
            onDismiss = accountViewModel::closeAddPassword,
        )
    }
    changePassword?.let { form ->
        ChangePasswordDialog(
            form = form,
            onCurrentChange = { accountViewModel.updateChangePassword(current = it) },
            onNewChange = { accountViewModel.updateChangePassword(new = it) },
            onRepeatChange = { accountViewModel.updateChangePassword(repeat = it) },
            onSubmit = accountViewModel::submitChangePassword,
            onDismiss = accountViewModel::closeChangePassword,
        )
    }
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
    LaunchedEffect(Unit) {
        viewModel.load()
        accountViewModel.load()
    }
    var systemBlocked by remember { mutableStateOf(!NotificationHelper.canPost(context)) }
    var supportOpen by remember { mutableStateOf(false) }
    var verifyOpen by remember { mutableStateOf(false) }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                systemBlocked = !NotificationHelper.canPost(context)
                if (verifyOpen) verifyEmailViewModel.check(userAsked = false)
                else accountViewModel.load()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(verifyOpen, verification.verified) {
        if (verifyOpen && verification.verified) {
            verifyOpen = false
            accountViewModel.load()
        }
    }
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
    val tenseOptions = remember(state.activeProfile?.id, learningLang, state.activeProfile?.appLang) {
        tenseHeadingsForPicker(state.activeProfile)
    }

    fun openTenseModal() {
        tenseDraft = state.lastCustomTenses.ifEmpty {
            state.selectedTenses.ifEmpty { LanguagePacks.defaultSelectedTenses(learningLang).toSet() }
        }
        tenseModalOpen = true
    }

    val darkTheme = usesDarkTheme(state.theme, isSystemInDarkTheme())
    val nextTheme = if (darkTheme) "light" else "dark"
    AppScreenScaffold(
        title = stringResource(R.string.settings_title),
        onBack = onBack,
        actions = {
            IconButton(
                onClick = { viewModel.setTheme(nextTheme) },
                enabled = !state.loading,
                modifier = Modifier.testTag(TestTags.SETTINGS_THEME_TOGGLE),
            ) {
                Icon(
                    if (darkTheme) Icons.Outlined.LightMode else Icons.Outlined.DarkMode,
                    contentDescription = "${stringResource(R.string.settings_theme)}: " +
                        stringResource(if (darkTheme) R.string.settings_theme_light else R.string.settings_theme_dark),
                )
            }
        },
    ) { paddingModifier ->
        if (state.loading) {
            CircularProgressIndicator(modifier = paddingModifier.padding(24.dp))
            return@AppScreenScaffold
        }
        Column(
            modifier = paddingModifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            SettingsGroupLabel(stringResource(R.string.settings_group_study))
            AppCard {
                Column {
                    AccordionSection(
                        title = stringResource(R.string.settings_mode),
                        icon = Icons.Outlined.Style,
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
                        icon = Icons.Outlined.SwapHoriz,
                        subtitle = directionChoice(
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
                            native,
                            selected = state.practiceDirection == "l1_to_l2",
                            onSelect = { viewModel.setDirection("l1_to_l2") },
                            testTag = TestTags.SETTINGS_DIR_L1_TO_L2,
                        )
                        SettingsRadioRow(
                            learning,
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

                    val contentCount = listOf(
                        state.showExampleSentences, state.showUsages, state.showPeriphrases,
                        state.showSynonyms && state.showAntonyms, state.showWordFamily,
                        state.showAssociations, state.showConjugation,
                    ).count { it }
                    AccordionSection(
                        title = stringResource(R.string.settings_card_layout),
                        icon = Icons.Outlined.ViewAgenda,
                        subtitle = pluralStringResource(R.plurals.settings_card_content_count, contentCount, contentCount),
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
                            label = stringResource(R.string.settings_associations),
                            checked = state.showAssociations,
                            onCheckedChange = viewModel::setShowAssociations,
                            testTag = TestTags.SETTINGS_CHECK_ASSOCIATIONS,
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
                        icon = Icons.Outlined.TrackChanges,
                        subtitle = if (state.expanded == SettingsSection.LIMITS) null else state.newCardsPerDay.toString(),
                        expanded = state.expanded == SettingsSection.LIMITS,
                        onHeaderClick = { viewModel.toggleSection(SettingsSection.LIMITS) },
                        testTag = TestTags.SETTINGS_SECTION_LIMITS,
                        showDivider = false,
                    ) {
                        SettingsValueSlider(
                            value = state.newCardsPerDay.coerceIn(5, 50),
                            onValueChange = viewModel::setNewCardsPerDay,
                            valueRange = 5..50,
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))
            SettingsGroupLabel(stringResource(R.string.settings_group_general))

            AppCard {
                Column {
                    AccordionSection(
                        title = stringResource(R.string.settings_notifications),
                        icon = Icons.Outlined.Notifications,
                        subtitle = if (state.notificationsEnabled) {
                            "${stringResource(R.string.settings_notifications_on)} · ${formatReminderTime(state.reminderHour, state.reminderMinute)}"
                        } else {
                            stringResource(R.string.settings_notifications_off)
                        },
                        expanded = state.expanded == SettingsSection.NOTIFICATIONS,
                        onHeaderClick = { viewModel.toggleSection(SettingsSection.NOTIFICATIONS) },
                        testTag = TestTags.SETTINGS_SECTION_NOTIFICATIONS,
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(stringResource(R.string.settings_notif_enabled), modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                            AppToggle(
                                checked = state.notificationsEnabled,
                                onCheckedChange = { enabled ->
                                    if (enabled) onRequestNotificationPermission()
                                    else viewModel.setNotificationsEnabled(false)
                                },
                                modifier = Modifier.testTag(TestTags.SETTINGS_NOTIF_STUDY),
                            )
                        }
                        AnimatedVisibility(
                            visible = state.notificationsEnabled,
                            enter = expandVertically() + fadeIn(),
                            exit = shrinkVertically() + fadeOut(),
                        ) {
                            Column(modifier = Modifier.fillMaxWidth()) {
                                if (systemBlocked) {
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 16.dp, vertical = 8.dp)
                                            .testTag(TestTags.SETTINGS_NOTIF_BLOCKED),
                                    ) {
                                        Text(
                                            stringResource(R.string.notif_blocked_hint),
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.error,
                                        )
                                        TextButton(
                                            onClick = {
                                                context.startActivity(
                                                    Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                                        .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                                                )
                                            },
                                        ) { Text(stringResource(R.string.notif_open_settings)) }
                                    }
                                }
                                ReminderTimeInput(
                                    hour = state.reminderHour,
                                    minute = state.reminderMinute,
                                    onTimeChange = viewModel::setReminderTime,
                                )
                            }
                        }
                    }

                    Column(Modifier.testTag(TestTags.SETTINGS_SECTION_LANGUAGES)) {
                        SettingsLanguageRow(
                            label = stringResource(R.string.settings_native_lang),
                            options = SUPPORTED_LEARNING_LANGS,
                            selectedCode = state.activeProfile?.appLang ?: "en",
                            excludedCode = state.activeProfile?.learning_lang,
                            icon = Icons.Outlined.Language,
                            onSelect = viewModel::setAppLang,
                            testTag = TestTags.SETTINGS_NATIVE_LANG,
                        )
                        SettingsLanguageRow(
                            label = stringResource(R.string.settings_i_learn),
                            options = SUPPORTED_LEARNING_LANGS,
                            selectedCode = state.activeProfile?.learning_lang ?: "en",
                            excludedCode = state.activeProfile?.appLang,
                            icon = Icons.Outlined.Style,
                            onSelect = viewModel::setLearningLang,
                            testTag = TestTags.SETTINGS_LEARNING_LANG,
                        )
                    }

                    AccordionSection(
                        title = stringResource(R.string.settings_level),
                        icon = Icons.Outlined.School,
                        subtitle = state.cefrLevel,
                        expanded = state.expanded == SettingsSection.CEFR,
                        onHeaderClick = { viewModel.toggleSection(SettingsSection.CEFR) },
                        testTag = TestTags.SETTINGS_SECTION_CEFR,
                    ) {
                        androidx.compose.foundation.layout.FlowRow(
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            CEFR_LEVELS.forEach { level ->
                                androidx.compose.material3.FilterChip(
                                    selected = state.cefrLevel == level,
                                    onClick = { viewModel.setCefr(level) },
                                    label = { Text(level) },
                                )
                            }
                        }
                    }

                    state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

                    AccordionSection(
                        title = stringResource(R.string.settings_account),
                        icon = Icons.Outlined.Person,
                        subtitle = account.email,
                        expanded = state.expanded == SettingsSection.ACCOUNT,
                        onHeaderClick = { viewModel.toggleSection(SettingsSection.ACCOUNT) },
                        testTag = TestTags.SETTINGS_SECTION_ACCOUNT,
                        showDivider = false,
                        bodyIndent = 24.dp,
                    ) {
                        AccountSectionBody(
                            account,
                            onChangePassword = accountViewModel::openChangePassword,
                            onSendReset = accountViewModel::sendPasswordReset,
                            onDeleteAccount = accountViewModel::openDeleteAccount,
                            onLinkGoogle = accountViewModel::openLinkGoogle,
                            onAddPassword = accountViewModel::openAddPassword,
                            onVerifyEmail = {
                                verifyOpen = true
                                verifyEmailViewModel.check(userAsked = false)
                            },
                            onLogout = onLogout,
                            onRetry = accountViewModel::load,
                        )
                    }
                }
            }
            account.info?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }

            val uriHandler = LocalUriHandler.current
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                TextButton(
                    onClick = { uriHandler.openUri(publicSiteUrl(ApiBaseUrl.resolve(), "/legal")) },
                    modifier = Modifier.testTag(TestTags.SETTINGS_LEGAL),
                ) { Text(stringResource(R.string.settings_legal)) }
                TextButton(
                    onClick = { supportOpen = true },
                    modifier = Modifier.testTag(TestTags.SETTINGS_SUPPORT),
                ) { Text(stringResource(R.string.support_title)) }
            }
            Spacer(Modifier.height(80.dp))
        }
    }

    if (supportOpen) SupportHelpDialog(onDismiss = { supportOpen = false })
    if (verifyOpen) {
        var now by remember { mutableStateOf(System.currentTimeMillis()) }
        LaunchedEffect(verification.resendAtMillis) {
            now = System.currentTimeMillis()
            while (now < verification.resendAtMillis) {
                delay(1_000)
                now = System.currentTimeMillis()
            }
        }
        val waitSeconds = ((verification.resendAtMillis - now + 999) / 1000).coerceAtLeast(0)
        AppAlertDialog(
            onDismissRequest = { verifyOpen = false },
            title = stringResource(R.string.verify_email_title),
            text = {
                Column(Modifier.heightIn(max = 400.dp).verticalScroll(rememberScrollState())) {
                    Text(
                        account.email?.let { stringResource(R.string.verify_email_body, it) }
                            ?: stringResource(R.string.verify_email_body_no_address),
                    )
                    deliveryText(verification.delivery)?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    verification.info?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    verification.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    TextButton(onClick = { verifyEmailViewModel.check(userAsked = true) }, enabled = !verification.busy) {
                        Text(stringResource(R.string.verify_email_check))
                    }
                    TextButton(onClick = verifyEmailViewModel::resend, enabled = !verification.busy && waitSeconds == 0L) {
                        Text(if (waitSeconds > 0) stringResource(R.string.verify_email_resend_in, waitSeconds.toInt()) else stringResource(R.string.verify_email_resend))
                    }
                }
            },
            buttons = { TextButton(onClick = { verifyOpen = false }) { Text(stringResource(R.string.action_close)) } },
        )
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
    onSelect: () -> Unit,
    onEdit: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier.weight(1f, fill = false).heightIn(min = 44.dp).selectable(selected = selected, role = Role.RadioButton, onClick = onSelect),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
                RadioButton(selected = selected, onClick = null)
            }
            Spacer(Modifier.width(10.dp))
            Text(
                stringResource(R.string.settings_selected_tenses),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Spacer(Modifier.width(12.dp))
        CompositionLocalProvider(LocalMinimumInteractiveComponentSize provides Dp.Unspecified) {
            TextButton(onClick = onEdit, enabled = selected) { Text(stringResource(R.string.action_edit)) }
        }
    }
}

@Composable
private fun TensePickerDialog(
    options: List<Pair<String, TenseHeading>>,
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
                    options.forEachIndexed { index, (key, heading) ->
                        SettingsCheckRow(
                            label = heading.original,
                            subtitle = heading.translation,
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
    icon: ImageVector,
    expanded: Boolean,
    onHeaderClick: () -> Unit,
    testTag: String? = null,
    subtitle: String? = null,
    showDivider: Boolean = true,
    bodyIndent: Dp = 52.dp,
    content: @Composable () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val bringIntoViewRequester = remember { BringIntoViewRequester() }
    LaunchedEffect(expanded) {
        if (expanded) {
            delay(340)
            bringIntoViewRequester.bringIntoView()
        }
    }
    Column(modifier = Modifier.bringIntoViewRequester(bringIntoViewRequester)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .then(if (testTag != null) Modifier.testTag(testTag) else Modifier)
                .clickable(onClick = onHeaderClick)
                .heightIn(min = 64.dp)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SettingsGlyph(icon)
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                if (subtitle != null) {
                    Spacer(Modifier.height(2.dp))
                    Text(subtitle, style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
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
                    .padding(start = bodyIndent, bottom = 8.dp),
            ) {
                content()
            }
        }
        if (showDivider) SettingsDivider()
    }
}

@Composable
private fun SettingsGlyph(icon: ImageVector) {
    Box(
        modifier = Modifier.size(36.dp).background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(12.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun SettingsDivider() {
    Box(Modifier.fillMaxWidth().padding(horizontal = 16.dp).height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
}

internal fun formatReminderTime(hour: Int, minute: Int): String =
    String.format(Locale.ROOT, "%02d:%02d", hour, minute)

internal fun parseReminderTime(value: String): Pair<Int, Int>? {
    if (!Regex("^[0-9]{2}:[0-9]{2}$").matches(value)) return null
    val hour = value.substring(0, 2).toInt()
    val minute = value.substring(3, 5).toInt()
    return if (hour in 0..23 && minute in 0..59) hour to minute else null
}

internal fun formatReminderInput(value: String): String {
    val digits = value.filter { it in '0'..'9' }.take(4)
    return if (digits.length > 2) "${digits.take(2)}:${digits.drop(2)}" else digits
}

@Composable
private fun ReminderTimeInput(hour: Int, minute: Int, onTimeChange: (Int, Int) -> Unit) {
    val focusManager = LocalFocusManager.current
    var value by remember { mutableStateOf(TextFieldValue(formatReminderTime(hour, minute))) }
    var focused by remember { mutableStateOf(false) }
    var edited by remember { mutableStateOf(false) }
    val invalid = edited && parseReminderTime(value.text) == null && (!focused || value.text.length == 5)
    LaunchedEffect(hour, minute) {
        if (!focused && !edited) value = TextFieldValue(formatReminderTime(hour, minute))
    }
    LaunchedEffect(focused) {
        if (focused && !edited) {
            value = TextFieldValue("")
        } else if (!focused && !edited) {
            value = TextFieldValue(formatReminderTime(hour, minute))
        }
    }
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.settings_study_hour), modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            OutlinedTextField(
                value = value,
                onValueChange = { input ->
                    if (input.text == value.text) {
                        value = input
                    } else {
                        val formatted = formatReminderInput(input.text)
                        val digitCount = formatted.count { it in '0'..'9' }
                        val beforeCursor = input.text.take(input.selection.end).count { it in '0'..'9' }.coerceAtMost(digitCount)
                        val cursor = beforeCursor + if (beforeCursor > 2) 1 else 0
                        value = TextFieldValue(formatted, TextRange(cursor.coerceAtMost(formatted.length)))
                        edited = true
                        parseReminderTime(formatted)?.let { (newHour, newMinute) ->
                            if (newHour != hour || newMinute != minute) onTimeChange(newHour, newMinute)
                            edited = false
                        }
                    }
                },
                modifier = Modifier.width(88.dp).testTag(TestTags.SETTINGS_NOTIF_TIME).onFocusChanged { focused = it.isFocused },
                textStyle = MaterialTheme.typography.bodyMedium.copy(textAlign = TextAlign.Center),
                placeholder = { Text("HH:mm", modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center) },
                singleLine = true,
                isError = invalid,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() }),
            )
        }
        if (invalid) {
            Text(stringResource(R.string.settings_invalid_time), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalComposeUiApi::class)
@Composable
private fun SettingsLanguageRow(
    label: String,
    options: List<Pair<String, String>>,
    selectedCode: String,
    excludedCode: String?,
    icon: ImageVector,
    onSelect: (String) -> Unit,
    testTag: String,
) {
    var expanded by remember { mutableStateOf(false) }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(testTag)
            .clickable { expanded = true }
            .heightIn(min = 64.dp)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SettingsGlyph(icon)
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(2.dp))
            Text(langDisplayName(selectedCode), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Icon(
            Icons.AutoMirrored.Filled.KeyboardArrowRight,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    SettingsDivider()

    if (expanded) {
        val listState = rememberLazyListState(
            initialFirstVisibleItemIndex = options.indexOfFirst { it.first.equals(selectedCode, ignoreCase = true) }.coerceAtLeast(0),
        )
        ModalBottomSheet(
            onDismissRequest = { expanded = false },
            modifier = Modifier
                .semantics { testTagsAsResourceId = true }
                .testTag("${testTag}__sheet"),
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = MaterialTheme.colorScheme.surface,
        ) {
            AppDialogWindowChrome()
            Text(
                label,
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp),
                style = MaterialTheme.typography.titleMedium,
            )
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = (LocalConfiguration.current.screenHeightDp * 0.65f).dp)
                    .padding(bottom = 16.dp),
            ) {
                items(options, key = { it.first }) { (code, name) ->
                    val selected = code.equals(selectedCode, ignoreCase = true)
                    val enabled = !code.equals(excludedCode, ignoreCase = true)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("${testTag}__$code")
                            .selectable(
                                selected = selected,
                                enabled = enabled,
                                role = Role.RadioButton,
                                onClick = { expanded = false; onSelect(code) },
                            )
                            .heightIn(min = 48.dp)
                            .padding(horizontal = 24.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            name,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyLarge,
                            color = if (enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f),
                        )
                        if (selected) {
                            Icon(Icons.Default.Check, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
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
private fun directionChoice(dir: String, native: String?, learning: String?): String {
    val n = native?.let { langDisplayName(it) } ?: stringResource(R.string.settings_native_lang)
    val l = learning?.let { langDisplayName(it) } ?: stringResource(R.string.settings_learning_lang)
    return when (dir) {
        "l1_to_l2" -> n
        "l2_to_l1" -> l
        else -> stringResource(R.string.settings_direction_random)
    }
}
