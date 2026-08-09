package com.vocabulario.app.ui.home

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.outlined.DriveFileMove
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.automirrored.outlined.Article
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import com.vocabulario.app.R
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.api.CardResponse
import com.vocabulario.app.data.api.DashboardForecastDay
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.api.WordListResponse
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import com.vocabulario.app.data.normalizePosKey
import com.vocabulario.app.ui.theme.LocalVocabExtraColors
import com.vocabulario.app.ui.components.AddToListSheet
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.AppChipShape
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.BrandLogo
import com.vocabulario.app.ui.components.ButtonLabel
import com.vocabulario.app.ui.components.TagChip
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import androidx.compose.ui.platform.testTag
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.i18n.localizedPosLabel
import com.vocabulario.app.ui.card.ListCardDetailOverlay
import com.vocabulario.app.ui.card.CardCorrectionReportSheet
import com.vocabulario.app.ui.card.CardCorrectionResultDialog
import com.vocabulario.app.ui.card.CardHistorySheet
import com.vocabulario.app.ui.card.CardSelfEditSheet
import com.vocabulario.app.ui.card.CardSelfEditWarningDialog
import com.vocabulario.app.ui.card.CorrectionActivityColor
import com.vocabulario.app.ui.card.cardActivityStatusLabel
import com.vocabulario.app.ui.card.CardActivitySpinner
import com.vocabulario.app.ui.home.voice.VoiceSearchSheet

private val ScreenPad = 20.dp
private val TileRadius = RoundedCornerShape(28.dp)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onPractice: () -> Unit,
    onSettings: () -> Unit,
    onOpenCard: (String) -> Unit = {},
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val isOnline by viewModel.connectivity.collectAsState()
    val scheme = MaterialTheme.colorScheme
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                viewModel.onHomeResumed()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Learning steps bywają w minutach — odświeżaj dashboard w tle.
    LaunchedEffect(state.tab) {
        if (state.tab != HomeTab.DASHBOARD) return@LaunchedEffect
        while (isActive) {
            delay(30_000)
            viewModel.loadStats()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(scheme.background)
            .statusBarsPadding()
            .navigationBarsPadding(),
    ) {
        if (state.importJobActive) {
            ImportProgressBar(progress = state.importProgress)
        }
        HomeHeader(onSettings = onSettings)
        HomeTabs(
            selected = state.tab,
            onSelect = viewModel::selectTab,
            importBusy = state.importJobActive,
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
        ) {
            when (state.tab) {
                HomeTab.DASHBOARD -> DashboardTab(state = state)
                HomeTab.ADD -> AddTab(
                    state = state,
                    isOnline = isOnline,
                    onQueryChange = viewModel::onQueryChange,
                    onSearch = viewModel::search,
                    onPrepareVoiceSearch = viewModel::prepareVoiceSearch,
                    onAdd = viewModel::openAddSheet,
                    onOpenWord = viewModel::openWordOnList,
                    onImportText = viewModel::startImportFromText,
                    onImportFileBytes = viewModel::startImportFromFileBytes,
                    onImportError = viewModel::setImportError,
                    onRemoveImportWord = viewModel::removeImportWord,
                    onRemoveImportDisplayCard = viewModel::removeImportDisplayCard,
                )
                HomeTab.LISTS -> ListsTab(
                    state = state,
                    isOnline = isOnline,
                    onSelectList = viewModel::selectList,
                    onCreateList = viewModel::createEmptyList,
                    onCreateListAndMove = viewModel::createListAndMoveWord,
                    onCreateListAndMoveSelected = viewModel::createListAndMoveSelected,
                    onCreateListAndMoveAll = viewModel::createListAndMoveAll,
                    onRenameList = viewModel::renameList,
                    onDeleteList = viewModel::deleteList,
                    onDeleteWord = viewModel::deleteWord,
                    onMoveWord = viewModel::moveWord,
                    onStartWordSelection = viewModel::startWordSelection,
                    onToggleWordSelection = viewModel::toggleWordSelection,
                    onClearWordSelection = viewModel::clearWordSelection,
                    onDeleteSelectedWords = viewModel::deleteSelectedWords,
                    onMoveSelectedWords = viewModel::moveSelectedWords,
                    onMoveAllWords = viewModel::moveAllWordsFromCurrentList,
                    onClearAllWords = viewModel::clearAllWordsFromCurrentList,
                    onSetSort = viewModel::setListSortOrder,
                    onSetFilter = viewModel::setListFilter,
                    onClearFilter = viewModel::clearListFilter,
                    onFixCard = viewModel::openCorrection,
                    onCardHistory = viewModel::openCardHistory,
                    onReviewWord = viewModel::openPendingReview,
                    onClearWordFocus = viewModel::clearWordFocus,
                )
            }
        }
        when {
            state.importActive -> {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = ScreenPad, vertical = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedButton(
                        onClick = viewModel::cancelImport,
                        modifier = Modifier
                            .weight(1f)
                            .height(54.dp)
                            .testTag(TestTags.BTN_IMPORT_CANCEL),
                        shape = AppButtonShape,
                        enabled = !state.importCommitting,
                    ) {
                        Text(stringResource(R.string.action_cancel), color = scheme.error)
                    }
                    Button(
                        onClick = viewModel::openImportDestination,
                        modifier = Modifier
                            .weight(1f)
                            .height(54.dp)
                            .testTag(TestTags.BTN_IMPORT_CONFIRM),
                        shape = AppButtonShape,
                        enabled = (state.importValid.isNotEmpty() || state.importDisplayCards.isNotEmpty()) &&
                            !state.importCommitting,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = scheme.tertiary,
                            contentColor = scheme.onTertiary,
                        ),
                    ) {
                        Text(
                            stringResource(R.string.action_confirm),
                            fontWeight = FontWeight.SemiBold,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
            state.selectionMode -> Unit // akcje multi-select w ListsTab
            else -> {
                Button(
                    onClick = onPractice,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = ScreenPad, vertical = 16.dp)
                        .height(54.dp)
                        .testTag(TestTags.BTN_LEARN),
                    shape = AppButtonShape,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = scheme.primary,
                        contentColor = scheme.onPrimary,
                    ),
                    elevation = ButtonDefaults.buttonElevation(defaultElevation = 0.dp),
                ) {
                    Text(
                        stringResource(R.string.action_learn),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }

    if (state.importDestinationOpen) {
        val importCount = if (state.importMode == "preserve") {
            state.importDisplayCards.size
        } else {
            state.importValid.size
        }
        AddToListSheet(
            lemma = stringResource(R.string.import_cards_count, importCount),
            gloss = stringResource(R.string.list_pick_target),
            lists = state.lists,
            pickListOpen = state.pickListOpen,
            showCreateListPrompt = state.showCreateListPrompt,
            createListName = state.createListName,
            createNameError = listNameConflictMessage(
                LocalContext.current,
                state.lists,
                state.createListName,
            ),
            onDismiss = viewModel::dismissImportDestination,
            onLearning = viewModel::commitImportToLearning,
            onOther = viewModel::openOtherLists,
            onPickList = viewModel::commitImportToList,
            onCreateNameChange = viewModel::onCreateListNameChange,
            onCreateAndAdd = viewModel::createListAndCommitImport,
            onShowCreatePrompt = viewModel::openCreateListPrompt,
            onBackFromCreatePrompt = viewModel::backFromCreateListPrompt,
            onBackFromListPicker = viewModel::backFromListPicker,
        )
    }

    state.addTarget?.let { target ->
        AddToListSheet(
            lemma = target.lemma,
            gloss = target.gloss,
            lists = state.lists,
            pickListOpen = state.pickListOpen,
            showCreateListPrompt = state.showCreateListPrompt,
            createListName = state.createListName,
            createNameError = listNameConflictMessage(
                LocalContext.current,
                state.lists,
                state.createListName,
            ),
            onDismiss = viewModel::dismissAddSheet,
            onLearning = viewModel::addToLearning,
            onOther = viewModel::openOtherLists,
            onPickList = viewModel::addToList,
            onCreateNameChange = viewModel::onCreateListNameChange,
            onCreateAndAdd = viewModel::createListAndAdd,
            onShowCreatePrompt = viewModel::openCreateListPrompt,
            onBackFromCreatePrompt = viewModel::backFromCreateListPrompt,
            onBackFromListPicker = viewModel::backFromListPicker,
        )
    }

    CardCorrectionReportSheet(
        visible = state.correctionCardId != null,
        submitting = state.correctionSubmitting,
        quotaRemaining = state.correctionQuotaRemaining,
        onDismiss = viewModel::dismissCorrectionReport,
        onSubmit = viewModel::submitCorrection,
        onSelfEdit = viewModel::openSelfEditFromReport,
    )
    CardCorrectionResultDialog(
        correction = state.correctionResults.active?.correction,
        cardLemma = state.correctionResults.active?.cardLemma ?: "—",
        onDismiss = viewModel::dismissCorrectionResult,
        onEditSelf = viewModel::openSelfEditFromResult,
    )
    CardSelfEditSheet(
        card = if (state.selfEditWarningOpen) null else state.selfEditCard,
        onDismiss = viewModel::dismissSelfEdit,
        onSave = viewModel::saveSelfEdit,
    )
    CardSelfEditWarningDialog(
        visible = state.selfEditWarningOpen,
        lemma = state.selfEditPendingCardId?.let { id ->
            state.listWords.firstOrNull { it.id == id }?.lemma_l2
        } ?: state.selfEditCard?.lemma_l2 ?: "—",
        issues = state.selfEditValidationIssues,
        onConfirm = viewModel::confirmSelfEditWarning,
        onRevert = viewModel::revertSelfEditWarning,
    )
    CardHistorySheet(
        visible = state.historyCardId != null,
        loading = state.historyLoading,
        restoring = state.historyRestoring,
        events = state.historyEvents,
        onDismiss = viewModel::dismissCardHistory,
        onRestore = viewModel::restoreFromHistory,
    )
    com.vocabulario.app.ui.card.PendingReviewSheet(
        visible = state.reviewCardId != null,
        word = state.reviewWord.orEmpty(),
        suggestions = state.reviewSuggestions,
        selectedIndex = state.reviewSelectedIndex,
        loading = state.reviewLoading,
        submitting = state.reviewSubmitting,
        onSelect = viewModel::selectReviewSuggestion,
        onReject = viewModel::rejectReviewWord,
        onSearchAgain = viewModel::retryReviewSearch,
        onConfirm = viewModel::approveReviewWord,
        onClose = viewModel::closePendingReview,
    )
}

@Composable
private fun ImportProgressBar(progress: Float) {
    val scheme = MaterialTheme.colorScheme
    val p = progress.coerceIn(0f, 1f)
    val label = stringResource(R.string.import_progress)
    val labelStyle = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.SemiBold)
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .height(22.dp),
    ) {
        val fullW = maxWidth
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(scheme.surfaceVariant),
        )
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .width(fullW * p)
                .background(scheme.primary),
        )
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Text(label, style = labelStyle, color = scheme.onSurfaceVariant)
        }
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .width(fullW * p)
                .clipToBounds(),
        ) {
            Box(
                modifier = Modifier
                    .width(fullW)
                    .fillMaxHeight(),
                contentAlignment = Alignment.Center,
            ) {
                Text(label, style = labelStyle, color = scheme.onPrimary)
            }
        }
    }
}

@Composable
private fun HomeHeader(onSettings: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val headerControl = 44.dp
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = ScreenPad)
            .padding(top = 10.dp, bottom = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Logo PNG has a drop-shadow below the glyphs, so geometric center sits high —
        // nudge down slightly so letterforms look vertically balanced in the header.
        Box(
            modifier = Modifier.height(headerControl),
            contentAlignment = Alignment.CenterStart,
        ) {
            BrandLogo(
                modifier = Modifier.offset(y = 2.dp),
                height = 38.dp,
                maxWidth = 236.dp,
            )
        }
        Surface(
            onClick = onSettings,
            shape = CircleShape,
            color = scheme.surfaceVariant,
            modifier = Modifier.size(headerControl).testTag(TestTags.BTN_SETTINGS),
        ) {
            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                Icon(
                    Icons.Outlined.Settings,
                    contentDescription = stringResource(R.string.cd_settings),
                    tint = scheme.onSurface,
                )
            }
        }
    }
}

@Composable
private fun HomeTabs(
    selected: HomeTab,
    onSelect: (HomeTab) -> Unit,
    importBusy: Boolean = false,
) {
    val scheme = MaterialTheme.colorScheme
    val tabs = listOf(
        HomeTab.DASHBOARD to stringResource(R.string.tab_dashboard),
        HomeTab.ADD to stringResource(R.string.tab_add),
        HomeTab.LISTS to stringResource(R.string.tab_lists),
    )
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp),
        ) {
            tabs.forEach { (tab, label) ->
                val active = selected == tab
                val tabTag = when (tab) {
                    HomeTab.DASHBOARD -> TestTags.TAB_DASHBOARD
                    HomeTab.ADD -> TestTags.TAB_ADD
                    HomeTab.LISTS -> TestTags.TAB_LISTS
                }
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .testTag(tabTag)
                        .clickable { onSelect(tab) }
                        .padding(top = 8.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text(
                            label,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                            color = if (active) scheme.onBackground else scheme.onSurfaceVariant,
                        )
                        if (tab == HomeTab.ADD && importBusy) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(12.dp),
                                strokeWidth = 1.5.dp,
                                color = scheme.primary,
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(3.dp)
                            .padding(horizontal = 18.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(if (active) scheme.onBackground else scheme.outline.copy(alpha = 0f)),
                    )
                }
            }
        }
        HorizontalDivider(color = scheme.outline, thickness = 1.dp)
    }
}


@Composable
private fun localizedWeekday(dayOffset: Int): String {
    val cal = java.util.Calendar.getInstance()
    cal.add(java.util.Calendar.DAY_OF_YEAR, dayOffset)
    // Calendar: SUNDAY=1 … SATURDAY=7 → map to Mon-first string resources
    return when (cal.get(java.util.Calendar.DAY_OF_WEEK)) {
        java.util.Calendar.MONDAY -> stringResource(R.string.weekday_mon)
        java.util.Calendar.TUESDAY -> stringResource(R.string.weekday_tue)
        java.util.Calendar.WEDNESDAY -> stringResource(R.string.weekday_wed)
        java.util.Calendar.THURSDAY -> stringResource(R.string.weekday_thu)
        java.util.Calendar.FRIDAY -> stringResource(R.string.weekday_fri)
        java.util.Calendar.SATURDAY -> stringResource(R.string.weekday_sat)
        else -> stringResource(R.string.weekday_sun)
    }
}

@Composable
private fun DashboardTab(state: HomeUiState) {
    val stats = state.stats
    val scheme = MaterialTheme.colorScheme

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = ScreenPad, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // Dziś — 3 kluczowe metryki
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = TileRadius,
            color = scheme.surface,
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 10.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                TodayStat(
                    label = stringResource(R.string.home_due_now),
                    value = stats?.due_count?.toString() ?: "–",
                    modifier = Modifier.weight(1f),
                )
                TodayStat(
                    label = stringResource(R.string.home_new_today),
                    value = stats?.new_done_today?.toString() ?: "–",
                    modifier = Modifier.weight(1f),
                )
                TodayStat(
                    label = stringResource(R.string.home_reviewed_today),
                    value = stats?.reviews_done_today?.toString() ?: "–",
                    modifier = Modifier.weight(1f),
                )
            }
        }

        // Status — kompaktowa lista
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = TileRadius,
            color = scheme.surfaceVariant,
        ) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)) {
                StatusLine(
                    label = stringResource(R.string.home_learning_now),
                    value = stats?.let { stringResource(R.string.home_words_count, it.srs_learning) } ?: "–",
                )
                HorizontalDivider(color = scheme.outline.copy(alpha = 0.25f))
                StatusLine(
                    label = stringResource(R.string.home_new_left),
                    value = stats?.let { stringResource(R.string.home_new_words_count, it.new_reserve) } ?: "–",
                )
                HorizontalDivider(color = scheme.outline.copy(alpha = 0.25f))
                StatusLine(
                    label = stringResource(R.string.home_mastered),
                    value = stats?.let { stringResource(R.string.home_words_count, it.srs_mastered) } ?: "–",
                )
            }
        }

        // Wykres 7 dni — stała wysokość, reszta miejsca bez scrolla
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f, fill = true),
            shape = TileRadius,
            color = scheme.surface,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 14.dp, vertical = 12.dp),
            ) {
                Text(
                    stringResource(R.string.home_forecast_title),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                Spacer(modifier = Modifier.height(10.dp))
                ReviewForecastBars(
                    days = stats?.forecast.orEmpty(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                )
            }
        }

        state.error?.let {
            Text(it, color = scheme.error, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun TodayStat(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            value,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = scheme.onSurface,
            textAlign = TextAlign.Center,
        )
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = scheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun StatusLine(
    label: String,
    value: String,
) {
    val scheme = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurface,
            modifier = Modifier.weight(1f),
        )
        Text(
            value,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = scheme.onSurface,
        )
    }
}

@Composable
private fun ReviewForecastBars(
    days: List<DashboardForecastDay>,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme
    val maxCount = (days.maxOfOrNull { it.due_count } ?: 0).coerceAtLeast(1)
    val barMaxHeight = 120.dp

    if (days.isEmpty()) {
        Box(modifier = modifier, contentAlignment = Alignment.Center) {
            Text("—", color = scheme.onSurfaceVariant)
        }
        return
    }

    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.Bottom,
    ) {
        days.take(7).forEachIndexed { index, day ->
            val fraction = day.due_count.toFloat() / maxCount.toFloat()
            val barHeight = if (day.due_count == 0) 4.dp else (barMaxHeight * fraction).coerceAtLeast(8.dp)
            // Odcienie primary: dziś najmocniejszy, dalej jaśniej
            val alpha = (1f - index * 0.09f).coerceIn(0.38f, 1f)
            val barColor: Color = scheme.primary.copy(alpha = alpha)

            Column(
                modifier = Modifier.weight(1f),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Bottom,
            ) {
                Text(
                    "${day.due_count}",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.72f)
                        .height(barHeight)
                        .clip(RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
                        .background(barColor),
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    localizedWeekday(day.day_offset),
                    style = MaterialTheme.typography.labelSmall,
                    color = scheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }
    }
}

@Composable
private fun AddTab(
    state: HomeUiState,
    isOnline: Boolean,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit,
    onPrepareVoiceSearch: () -> Unit,
    onAdd: (LookupCandidate) -> Unit,
    onOpenWord: (LookupCandidate) -> Unit,
    onImportText: (String, String) -> Unit,
    onImportFileBytes: (ByteArray, String, String) -> Unit,
    onImportError: (String) -> Unit,
    onRemoveImportWord: (String) -> Unit,
    onRemoveImportDisplayCard: (String) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val context = LocalContext.current
    var showFileDialog by remember { mutableStateOf(false) }
    var showPasteDialog by remember { mutableStateOf(false) }
    var showInvalidDialog by remember { mutableStateOf(false) }
    var showModeDialog by remember { mutableStateOf(false) }
    var pasteDraft by remember { mutableStateOf("") }
    var pendingFileBytes by remember { mutableStateOf<ByteArray?>(null) }
    var pendingFileName by remember { mutableStateOf<String?>(null) }
    var pendingPasteText by remember { mutableStateOf<String?>(null) }
    var pickingFile by remember { mutableStateOf(false) }
    var showVoiceSheet by remember { mutableStateOf(false) }
    val speechAvailable = remember { android.speech.SpeechRecognizer.isRecognitionAvailable(context) }
    val nativeLang = state.activeProfile?.appLang ?: "pl"
    val learningLang = state.activeProfile?.learning_lang ?: "es"

    val fileLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri ->
        pickingFile = false
        if (uri == null) {
            showFileDialog = true
            return@rememberLauncherForActivityResult
        }
        runCatching {
            val name = context.contentResolver.query(
                uri,
                arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),
                null,
                null,
                null,
            )?.use { cursor ->
                val idx = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (cursor.moveToFirst() && idx >= 0) cursor.getString(idx) else null
            } ?: uri.lastPathSegment ?: "import.bin"
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                ?: error(context.getString(R.string.import_file_errors))
            name to bytes
        }.onSuccess { (name, bytes) ->
            pendingFileName = name
            pendingFileBytes = bytes
            showFileDialog = true
        }.onFailure {
            showFileDialog = true
            onImportError(it.message ?: context.getString(R.string.import_file_errors))
        }
    }

    fun launchFilePicker() {
        pickingFile = true
        fileLauncher.launch(
            arrayOf(
                "*/*",
                "text/*",
                "text/csv",
                "text/plain",
                "text/tab-separated-values",
                "application/zip",
                "application/octet-stream",
                "application/vnd.ms-excel",
            ),
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = ScreenPad),
    ) {
        Spacer(modifier = Modifier.height(16.dp))

        if (!state.importActive) {
            if (isOnline) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedButton(
                        onClick = {
                            pendingFileBytes = null
                            pendingFileName = null
                            showFileDialog = true
                        },
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .testTag(TestTags.BTN_IMPORT_FILE),
                        shape = AppButtonShape,
                    ) {
                        Text(stringResource(R.string.import_from_file), maxLines = 1)
                    }
                    OutlinedButton(
                        onClick = {
                            pasteDraft = ""
                            showPasteDialog = true
                        },
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .testTag(TestTags.BTN_IMPORT_PASTE),
                        shape = AppButtonShape,
                    ) {
                        Text(stringResource(R.string.import_paste), maxLines = 1)
                    }
                }
                Spacer(modifier = Modifier.height(12.dp))
            }
            if (!isOnline) {
                Surface(
                    shape = AppButtonShape,
                    color = scheme.surfaceVariant,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 12.dp),
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        Icon(
                            Icons.Outlined.CloudOff,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                            tint = scheme.onSurfaceVariant,
                        )
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                stringResource(R.string.offline_banner_title),
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = scheme.onSurface,
                            )
                            Text(
                                stringResource(R.string.offline_banner_body),
                                style = MaterialTheme.typography.bodySmall,
                                color = scheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
            OutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                placeholder = {
                    Text(
                        stringResource(
                            if (isOnline) R.string.home_search_hint else R.string.offline_search_hint,
                        ),
                    )
                },
                modifier = Modifier.fillMaxWidth().testTag(TestTags.SEARCH_INPUT),
                singleLine = true,
                shape = AppButtonShape,
                leadingIcon = {
                    Icon(Icons.Default.Search, contentDescription = null, tint = scheme.onSurfaceVariant)
                },
                trailingIcon = {
                    Row {
                        if (isOnline && speechAvailable) {
                            IconButton(
                                onClick = {
                                    onPrepareVoiceSearch()
                                    showVoiceSheet = true
                                },
                                modifier = Modifier.testTag(TestTags.BTN_VOICE_SEARCH),
                            ) {
                                Icon(
                                    Icons.Default.Mic,
                                    contentDescription = stringResource(R.string.cd_voice_search),
                                    tint = scheme.primary,
                                )
                            }
                        }
                        IconButton(onClick = onSearch, modifier = Modifier.testTag(TestTags.SEARCH_SUBMIT)) {
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowForward,
                                contentDescription = stringResource(R.string.cd_search),
                                tint = scheme.primary,
                            )
                        }
                    }
                },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onSearch() }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = scheme.surfaceVariant,
                    unfocusedContainerColor = scheme.surfaceVariant,
                    disabledContainerColor = scheme.surfaceVariant,
                    focusedBorderColor = scheme.outline,
                    unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                    cursorColor = scheme.primary,
                ),
            )
            Spacer(modifier = Modifier.height(16.dp))
        } else {
            val importedCount = if (state.importMode == "preserve") {
                state.importDisplayCards.size
            } else {
                state.importValid.size
            }
            Text(
                if (state.importMode == "preserve") stringResource(R.string.import_flashcards_count, importedCount) else stringResource(R.string.import_done_count, importedCount),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = scheme.onSurface,
            )
            if (state.importInvalid.isNotEmpty()) {
                Text(
                    stringResource(R.string.import_file_errors),
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.error,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier
                        .padding(top = 6.dp)
                        .clickable { showInvalidDialog = true },
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
        }

        if (state.loading || state.importCommitting) {
            CircularProgressIndicator(
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .padding(24.dp),
                color = scheme.primary,
                strokeWidth = 3.dp,
            )
        }
        state.error?.let { Text(it, color = scheme.error) }
        state.notice?.let { Text(it, color = scheme.onSurfaceVariant) }

        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 12.dp),
        ) {
            if (state.importActive && state.importMode == "preserve") {
                items(state.importDisplayCards, key = { it.key }) { card ->
                    ImportDisplayPreviewTile(
                        card = card,
                        onRemove = { onRemoveImportDisplayCard(card.key) },
                    )
                }
                if (state.importDisplayCards.isEmpty() && !state.loading) {
                    item {
                        Text(
                            stringResource(R.string.import_no_cards),
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 24.dp),
                        )
                    }
                }
            } else if (state.importActive) {
                items(state.importValid, key = { it.input }) { word ->
                    ImportWordTile(
                        display = word.lemma,
                        subtitle = listOfNotNull(
                            entryKindLabelPl(word.entry_kind),
                            word.gloss.takeIf { it.isNotBlank() },
                        ).joinToString(" · ").ifBlank { null },
                        onRemove = { onRemoveImportWord(word.input) },
                    )
                }
                if (state.importValid.isEmpty() && !state.loading) {
                    item {
                        Text(
                            stringResource(R.string.import_no_valid),
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 24.dp),
                        )
                    }
                }
            } else {
                items(state.candidates) { candidate ->
                    CandidateRow(
                        candidate = candidate,
                        onAdd = { onAdd(candidate) },
                        onOpenWord = onOpenWord,
                    )
                }
                if (state.candidates.isEmpty() && !state.loading && state.query.isBlank()) {
                    item {
                        if (isOnline) {
                            Text(
                                stringResource(R.string.import_empty_hint),
                                style = MaterialTheme.typography.bodyLarge,
                                color = scheme.onSurfaceVariant,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 56.dp),
                            )
                        }
                    }
                }
            }
        }
    }


    if (showModeDialog) {
        AlertDialog(
            onDismissRequest = {
                showModeDialog = false
                pendingFileBytes = null
                pendingFileName = null
                pendingPasteText = null
            },
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = {
                Text(stringResource(R.string.import_how), fontWeight = FontWeight.Bold, color = scheme.onSurface)
            },
            text = {
                Text(
                    stringResource(R.string.import_vocab_hint),
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                )
            },
            confirmButton = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = {
                            val mode = "vocabulario"
                            val bytes = pendingFileBytes
                            val name = pendingFileName
                            val paste = pendingPasteText
                            showModeDialog = false
                            pendingFileBytes = null
                            pendingFileName = null
                            pendingPasteText = null
                            when {
                                bytes != null && name != null -> onImportFileBytes(bytes, name, mode)
                                !paste.isNullOrBlank() -> onImportText(paste, mode)
                            }
                        },
                        shape = AppButtonShape,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp)
                            .testTag(TestTags.IMPORT_MODE_VOCAB),
                    ) { Text(stringResource(R.string.import_vocab_mode), fontWeight = FontWeight.SemiBold) }
                    OutlinedButton(
                        onClick = {
                            val mode = "preserve"
                            val bytes = pendingFileBytes
                            val name = pendingFileName
                            val paste = pendingPasteText
                            showModeDialog = false
                            pendingFileBytes = null
                            pendingFileName = null
                            pendingPasteText = null
                            when {
                                bytes != null && name != null -> onImportFileBytes(bytes, name, mode)
                                !paste.isNullOrBlank() -> onImportText(paste, mode)
                            }
                        },
                        shape = AppButtonShape,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp)
                            .testTag(TestTags.IMPORT_MODE_PRESERVE),
                    ) { Text(stringResource(R.string.import_preserve_mode)) }
                    TextButton(
                        onClick = {
                            showModeDialog = false
                            pendingFileBytes = null
                            pendingFileName = null
                            pendingPasteText = null
                        },
                        modifier = Modifier.fillMaxWidth().testTag(TestTags.DIALOG_CANCEL),
                    ) { Text(stringResource(R.string.action_cancel), color = scheme.error) }
                }
            },
            dismissButton = {},
        )
    }
    if (showFileDialog) {
        AlertDialog(
            onDismissRequest = {
                if (pickingFile) return@AlertDialog
                showFileDialog = false
                pendingFileBytes = null
                pendingFileName = null
            },
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = {
                Text(stringResource(R.string.import_from_file), fontWeight = FontWeight.Bold, color = scheme.onSurface)
            },
            text = {
                Column(
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (pendingFileName != null) {
                        Text(
                            stringResource(R.string.import_file_label, pendingFileName ?: ""),
                            style = MaterialTheme.typography.labelLarge,
                            color = scheme.primary,
                        )
                    }
                    OutlinedButton(
                        onClick = { launchFilePicker() },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = AppButtonShape,
                    ) {
                        Text(
                            if (pendingFileName == null) stringResource(R.string.import_add_file) else stringResource(R.string.import_other_file),
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (pendingFileBytes == null) return@Button
                        showFileDialog = false
                        showModeDialog = true
                    },
                    enabled = pendingFileBytes != null,
                    shape = AppButtonShape,
                    modifier = Modifier.testTag(TestTags.DIALOG_CONFIRM),
                ) { Text(stringResource(R.string.action_import)) }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = {
                        showFileDialog = false
                        pendingFileBytes = null
                        pendingFileName = null
                    },
                    shape = AppButtonShape,
                    modifier = Modifier.testTag(TestTags.DIALOG_CANCEL),
                ) { Text(stringResource(R.string.action_cancel), color = scheme.error) }
            },
        )
    }

    if (showPasteDialog) {
        AlertDialog(
            onDismissRequest = { showPasteDialog = false },
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = null,
            text = {
                OutlinedTextField(
                    value = pasteDraft,
                    onValueChange = { pasteDraft = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(220.dp)
                        .testTag(TestTags.IMPORT_PASTE_INPUT),
                    placeholder = { Text(stringResource(R.string.import_paste_hint)) },
                    shape = RoundedCornerShape(14.dp),
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        val text = pasteDraft
                        showPasteDialog = false
                        pasteDraft = ""
                        pendingPasteText = text
                        if (text.isNotBlank()) showModeDialog = true
                    },
                    enabled = pasteDraft.isNotBlank(),
                    shape = AppButtonShape,
                    modifier = Modifier.testTag(TestTags.DIALOG_CONFIRM),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = scheme.tertiary,
                        contentColor = scheme.onTertiary,
                    ),
                ) { Text(stringResource(R.string.action_confirm)) }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { showPasteDialog = false },
                    shape = AppButtonShape,
                    modifier = Modifier.testTag(TestTags.DIALOG_CANCEL),
                ) { Text(stringResource(R.string.action_cancel), color = scheme.error) }
            },
        )
    }

    if (showInvalidDialog) {
        AlertDialog(
            onDismissRequest = { showInvalidDialog = false },
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = {
                Text(stringResource(R.string.import_invalid_title), fontWeight = FontWeight.Bold, color = scheme.onSurface)
            },
            text = {
                Column(
                    modifier = Modifier.height(280.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    androidx.compose.foundation.lazy.LazyColumn {
                        items(state.importInvalid) { w ->
                            Text("• $w", color = scheme.onSurface)
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = { showInvalidDialog = false },
                    shape = AppButtonShape,
                ) { Text(stringResource(R.string.action_close)) }
            },
        )
    }

    VoiceSearchSheet(
        visible = showVoiceSheet,
        nativeLang = nativeLang,
        learningLang = learningLang,
        candidates = state.candidates,
        loading = state.loading,
        searchError = state.error,
        onDismiss = { showVoiceSheet = false },
        onResult = { text ->
            onQueryChange(text)
            onSearch()
        },
        onAdd = onAdd,
    )
}

@Composable
private fun ImportDisplayPreviewTile(
    card: com.vocabulario.app.data.api.ImportDisplayCard,
    onRemove: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    var expanded by remember(card.key) { mutableStateOf(false) }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = scheme.surfaceVariant,
    ) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .clickable { expanded = !expanded },
                ) {
                    Text(
                        card.lemma_l2,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Surface(
                    onClick = onRemove,
                    shape = CircleShape,
                    color = scheme.error.copy(alpha = 0.15f),
                    contentColor = scheme.error,
                    modifier = Modifier.size(34.dp),
                ) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                        Icon(Icons.Default.Close, contentDescription = stringResource(R.string.cd_delete), modifier = Modifier.size(18.dp))
                    }
                }
            }
            AnimatedVisibility(visible = expanded) {
                Column(modifier = Modifier.padding(top = 10.dp)) {
                    key(card.key, expanded) {
                        com.vocabulario.app.ui.components.ImportDisplayFlip(
                            display = card.display,
                            showPrompt = false,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun listDisplayName(list: WordListResponse): String = when {
    list.is_system -> stringResource(R.string.list_learning)
    list.is_pending_inbox -> stringResource(R.string.list_pending)
    else -> list.name
}
@Composable
private fun entryKindLabelPl(kind: String): String? = when (kind.lowercase()) {
    "lemma" -> stringResource(R.string.kind_lemma)
    "phrase" -> stringResource(R.string.kind_phrase)
    "construction" -> stringResource(R.string.kind_construction)
    "sentence" -> stringResource(R.string.kind_sentence)
    "other" -> stringResource(R.string.kind_other)
    else -> null
}

@Composable
private fun ImportWordTile(
    display: String,
    subtitle: String? = null,
    onRemove: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = scheme.surfaceVariant,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    display,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Surface(
                onClick = onRemove,
                shape = CircleShape,
                color = scheme.error.copy(alpha = 0.15f),
                contentColor = scheme.error,
                modifier = Modifier.size(34.dp),
            ) {
                Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                    Icon(Icons.Default.Close, contentDescription = stringResource(R.string.cd_delete), modifier = Modifier.size(18.dp))
                }
            }
        }
    }
}

@Composable
private fun CandidateRow(
    candidate: LookupCandidate,
    onAdd: () -> Unit,
    onOpenWord: (LookupCandidate) -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val rowContent: @Composable () -> Unit = {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    candidate.lemma,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scheme.onSurface,
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    candidate.gloss,
                    style = MaterialTheme.typography.bodyMedium,
                    color = scheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    candidate.pos?.let { TagChip(localizedPosLabel(it).ifBlank { it }) }
                    if (candidate.onList) {
                        TagChip(
                            text = candidate.list_name ?: stringResource(R.string.list_unnamed),
                            onClick = { onOpenWord(candidate) },
                        )
                    }
                }
                if (candidate.isCreating) {
                    Spacer(modifier = Modifier.height(8.dp))
                    CreatingCardHint()
                }
            }
            when {
                candidate.isCreating -> {
                    CircularProgressIndicator(
                        modifier = Modifier.size(28.dp),
                        strokeWidth = 3.dp,
                        color = scheme.primary,
                    )
                }
                candidate.onList -> {
                    Icon(
                        Icons.Default.CheckCircle,
                        contentDescription = null,
                        tint = scheme.primary,
                        modifier = Modifier.size(26.dp),
                    )
                }
                else -> {
                    Surface(
                        onClick = onAdd,
                        shape = CircleShape,
                        color = scheme.primary,
                        contentColor = scheme.onPrimary,
                        modifier = Modifier.size(40.dp).testTag(TestTags.CANDIDATE_ADD),
                    ) {
                        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                            Icon(Icons.Default.Add, contentDescription = stringResource(R.string.action_add), modifier = Modifier.size(22.dp))
                        }
                    }
                }
            }
        }
    }
    if (candidate.onList) {
        AppCard(
            modifier = Modifier.testTag(TestTags.SEARCH_RESULT),
            onClick = { onOpenWord(candidate) },
            content = rowContent,
        )
    } else {
        AppCard(
            modifier = Modifier.testTag(TestTags.SEARCH_RESULT),
            content = rowContent,
        )
    }
}

@Composable
private fun CreatingCardHint() {
    val transition = rememberInfiniteTransition(label = "creating")
    val alpha by transition.animateFloat(
        initialValue = 0.35f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(750, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "creatingAlpha",
    )
    Text(
        stringResource(R.string.creating_card),
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.primary.copy(alpha = alpha),
    )
}

private enum class ListEditDialog { None, Menu, Rename, DeleteConfirm, ClearAllConfirm, MoveAll }
private enum class WordEditDialog { None, DeleteConfirm, Move }
private enum class MultiEditDialog { None, DeleteConfirm, Move }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ListsTab(
    state: HomeUiState,
    isOnline: Boolean,
    onSelectList: (String) -> Unit,
    onCreateList: (String) -> Unit,
    onCreateListAndMove: (String, String) -> Unit,
    onCreateListAndMoveSelected: (String) -> Unit,
    onCreateListAndMoveAll: (String) -> Unit,
    onRenameList: (String, String) -> Unit,
    onDeleteList: (String) -> Unit,
    onDeleteWord: (String) -> Unit,
    onMoveWord: (String, String) -> Unit,
    onStartWordSelection: (String) -> Unit,
    onToggleWordSelection: (String) -> Unit,
    onClearWordSelection: () -> Unit,
    onDeleteSelectedWords: () -> Unit,
    onMoveSelectedWords: (String) -> Unit,
    onMoveAllWords: (String) -> Unit,
    onClearAllWords: () -> Unit,
    onSetSort: (ListSortOrder) -> Unit,
    onSetFilter: (ListFilterState) -> Unit,
    onClearFilter: () -> Unit,
    onFixCard: (String) -> Unit,
    onCardHistory: (String) -> Unit,
    onReviewWord: (String) -> Unit,
    onClearWordFocus: () -> Unit,
) {
    var showCreate by remember { mutableStateOf(false) }
    var newName by remember { mutableStateOf("") }
    var createThenMoveCardId by remember { mutableStateOf<String?>(null) }
    var createThenMoveSelected by remember { mutableStateOf(false) }
    var createThenMoveAll by remember { mutableStateOf(false) }
    var expandedId by remember { mutableStateOf<String?>(null) }
    var listDialog by remember { mutableStateOf(ListEditDialog.None) }
    var renameDraft by remember { mutableStateOf("") }
    var wordDialog by remember { mutableStateOf(WordEditDialog.None) }
    var wordTargetId by remember { mutableStateOf<String?>(null) }
    var moveTargetId by remember { mutableStateOf<String?>(null) }
    var moveMenuOpen by remember { mutableStateOf(false) }
    var multiDialog by remember { mutableStateOf(MultiEditDialog.None) }
    var showSortSheet by remember { mutableStateOf(false) }
    var showFilterSheet by remember { mutableStateOf(false) }
    var draftFilter by remember { mutableStateOf(ListFilterState()) }
    var detailCard by remember { mutableStateOf<CardResponse?>(null) }
    val listState = rememberLazyListState()
    val scheme = MaterialTheme.colorScheme
    val selectedList = state.lists.firstOrNull { it.id == state.selectedListId }
    val pendingInboxSelected = selectedList?.is_pending_inbox == true
    val moveTargets = state.lists.filter { it.id != state.selectedListId }
    val selectionMode = state.selectionMode
    val visibleWords = state.visibleListWords

    LaunchedEffect(state.focusWordId, state.focusLemma, state.listWords, state.loading) {
        if (state.loading) return@LaunchedEffect
        if (state.focusWordId == null && state.focusLemma.isNullOrBlank()) return@LaunchedEffect
        val targetId = state.focusWordId
            ?: state.focusLemma?.let { lemma ->
                state.listWords.find { it.lemma_l2.equals(lemma, ignoreCase = true) }?.id
            }
        if (targetId == null) {
            onClearWordFocus()
            return@LaunchedEffect
        }
        val index = visibleWords.indexOfFirst { it.id == targetId }
        if (index >= 0) {
            expandedId = targetId
            listState.scrollToItem(index)
        } else if (state.listWords.any { it.id == targetId }) {
            expandedId = targetId
        }
        onClearWordFocus()
    }

    fun closeListDialogs() {
        listDialog = ListEditDialog.None
        renameDraft = ""
        moveTargetId = null
        moveMenuOpen = false
    }

    fun closeWordDialogs() {
        wordDialog = WordEditDialog.None
        wordTargetId = null
        moveTargetId = null
        moveMenuOpen = false
    }

    fun closeMultiDialogs() {
        multiDialog = MultiEditDialog.None
        moveTargetId = null
        moveMenuOpen = false
    }

    fun closeCreateDialog() {
        showCreate = false
        newName = ""
        createThenMoveCardId = null
        createThenMoveSelected = false
        createThenMoveAll = false
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = ScreenPad),
    ) {
        Spacer(modifier = Modifier.height(16.dp))
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(top = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items(state.lists) { list ->
                ListChip(
                    list = list,
                    selected = list.id == state.selectedListId,
                    showMenu = list.id == state.selectedListId,
                    showSpinner = state.importJobActive && list.id == state.importTargetListId,
                    onClick = {
                        expandedId = null
                        closeWordDialogs()
                        closeListDialogs()
                        closeMultiDialogs()
                        onSelectList(list.id)
                    },
                    onMenu = {
                        renameDraft = list.name
                        listDialog = ListEditDialog.Menu
                    },
                )
            }
            item {
                Surface(
                    onClick = { showCreate = true },
                    shape = AppChipShape,
                    color = scheme.surfaceVariant,
                    contentColor = scheme.onSurface,
                    modifier = Modifier.testTag(TestTags.BTN_NEW_LIST),
                ) {
                    Box(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            Icons.Default.Add,
                            contentDescription = stringResource(R.string.new_list_cd),
                            modifier = Modifier.size(18.dp),
                            tint = scheme.onSurface,
                        )
                    }
                }
            }
        }

        ListWordsMetaBar(
            modifier = Modifier.padding(top = 4.dp, bottom = 4.dp),
            filter = state.listFilter,
            onSort = { showSortSheet = true },
            onFilter = {
                draftFilter = state.listFilter
                showFilterSheet = true
            },
        )

        when {
            state.loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(40.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(color = scheme.primary, strokeWidth = 3.dp)
                }
            }
            state.listWords.isEmpty() -> {
                    Text(
                        stringResource(R.string.list_empty),
                    style = MaterialTheme.typography.bodyLarge,
                    color = scheme.onSurfaceVariant,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 40.dp),
                    textAlign = TextAlign.Center,
                )
            }
            visibleWords.isEmpty() -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 40.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        stringResource(R.string.list_filter_empty),
                        style = MaterialTheme.typography.bodyLarge,
                        color = scheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                    TextButton(onClick = onClearFilter) {
                        Text(stringResource(R.string.action_clear_filters))
                    }
                }
            }
            else -> {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = PaddingValues(bottom = 72.dp),
                ) {
                    items(
                        visibleWords,
                        key = { card ->
                            if (pendingInboxSelected) {
                                card.lemma_l2.trim().lowercase()
                            } else {
                                card.id
                            }
                        },
                    ) { card ->
                        val selected = card.id in state.selectedWordIds
                        ListWordTile(
                            card = card,
                            flushInProgress = isOnline && card.enrichment_status == "awaiting_network",
                            expanded = expandedId == card.id && !selectionMode,
                            selected = selected,
                            selectionMode = selectionMode,
                            editProcessing = card.id == state.selfEditProgressCardId,
                            onToggle = {
                                if (selectionMode) {
                                    onToggleWordSelection(card.id)
                                    return@ListWordTile
                                }
                                if (card.enrichment_status == "pending" ||
                                    card.enrichment_status == "awaiting_network" ||
                                    card.id.startsWith("pending-")
                                ) {
                                    return@ListWordTile
                                }
                                expandedId = if (expandedId == card.id) null else card.id
                                closeWordDialogs()
                            },
                            onLongPress = {
                                if (card.enrichment_status == "pending" ||
                                    card.enrichment_status == "awaiting_network" ||
                                    card.id.startsWith("pending-")
                                ) {
                                    return@ListWordTile
                                }
                                expandedId = null
                                closeWordDialogs()
                                if (selectionMode) {
                                    onToggleWordSelection(card.id)
                                } else {
                                    onStartWordSelection(card.id)
                                }
                            },
                            onDelete = {
                                wordTargetId = card.id
                                wordDialog = WordEditDialog.DeleteConfirm
                            },
                            onMove = {
                                wordTargetId = card.id
                                if (moveTargets.isNotEmpty()) {
                                    moveTargetId = moveTargets.firstOrNull()?.id
                                    wordDialog = WordEditDialog.Move
                                } else {
                                    newName = ""
                                    createThenMoveCardId = card.id
                                    showCreate = true
                                }
                            },
                            onFixCard = { onFixCard(card.id) },
                            onViewCard = { detailCard = card },
                            onHistory = { onCardHistory(card.id) },
                            onReview = { onReviewWord(card.id) },
                        )
                    }
                }
            }
        }

        if (selectionMode) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                val btnPad = PaddingValues(horizontal = 10.dp, vertical = 0.dp)
                OutlinedButton(
                    onClick = {
                        closeMultiDialogs()
                        onClearWordSelection()
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp)
                        .testTag(TestTags.MULTI_CANCEL),
                    shape = AppButtonShape,
                    contentPadding = btnPad,
                ) {
                    ButtonLabel(stringResource(R.string.action_cancel), color = scheme.error)
                }
                OutlinedButton(
                    onClick = { multiDialog = MultiEditDialog.DeleteConfirm },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp)
                        .testTag(TestTags.MULTI_DELETE),
                    shape = AppButtonShape,
                    contentPadding = btnPad,
                ) {
                    ButtonLabel(stringResource(R.string.list_delete_selected), color = scheme.error)
                }
                Button(
                    onClick = {
                        if (moveTargets.isNotEmpty()) {
                            moveTargetId = moveTargets.firstOrNull()?.id
                            multiDialog = MultiEditDialog.Move
                        } else {
                            createThenMoveSelected = true
                            showCreate = true
                        }
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp)
                        .testTag(TestTags.MULTI_MOVE),
                    shape = AppButtonShape,
                    contentPadding = btnPad,
                ) {
                    ButtonLabel(stringResource(R.string.action_move))
                }
            }
        }
    }

    if (showCreate) {
        val trimmedCreate = newName.trim()
        val createNameError = listNameConflictMessage(LocalContext.current, state.lists, trimmedCreate)
        val reservedName = isReservedListNameMessage(LocalContext.current, trimmedCreate)
        val movingWord = createThenMoveCardId != null
        val movingSelected = createThenMoveSelected
        val movingAll = createThenMoveAll
        AlertDialog(
            onDismissRequest = { closeCreateDialog() },
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = {
                Text(stringResource(R.string.list_new), fontWeight = FontWeight.Bold, color = scheme.onSurface)
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (movingWord || movingSelected || movingAll) {
                        Text(
                            when {
                                movingAll -> stringResource(R.string.list_create_move_all)
                                movingSelected -> stringResource(R.string.list_create_move_sel)
                                else -> stringResource(R.string.list_create_move_one)
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                        )
                    }
                    OutlinedTextField(
                        value = newName,
                        onValueChange = { newName = it },
                        placeholder = { Text(stringResource(R.string.list_name_hint), color = scheme.onSurfaceVariant) },
                        singleLine = true,
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.fillMaxWidth().testTag(TestTags.SHEET_LIST_NAME),
                        isError = createNameError != null && !reservedName,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = scheme.onSurface,
                            unfocusedTextColor = scheme.onSurface,
                            focusedContainerColor = scheme.surfaceVariant,
                            unfocusedContainerColor = scheme.surfaceVariant,
                            unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                            cursorColor = scheme.primary,
                        ),
                    )
                    if (createNameError != null) {
                        Text(
                            createNameError,
                            style = MaterialTheme.typography.labelMedium,
                            color = if (reservedName) scheme.onSurfaceVariant else scheme.error,
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        when {
                            createThenMoveCardId != null -> {
                                onCreateListAndMove(newName, createThenMoveCardId!!)
                                expandedId = null
                            }
                            createThenMoveSelected -> onCreateListAndMoveSelected(newName)
                            createThenMoveAll -> onCreateListAndMoveAll(newName)
                            else -> onCreateList(newName)
                        }
                        closeCreateDialog()
                    },
                    shape = AppButtonShape,
                    enabled = trimmedCreate.isNotBlank() && createNameError == null,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = scheme.tertiary,
                        contentColor = scheme.onTertiary,
                    ),
                ) { Text(stringResource(R.string.action_create)) }
            },
            dismissButton = {
                OutlinedButton(onClick = { closeCreateDialog() }, shape = AppButtonShape) {
                    Text(stringResource(R.string.action_cancel), color = scheme.error)
                }
            },
        )
    }

    when (listDialog) {
        ListEditDialog.Menu -> {
            val systemList = selectedList?.is_system == true
            val pendingInbox = selectedList?.is_pending_inbox == true
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(
                        selectedList?.let { listDisplayName(it) }
                            ?: stringResource(R.string.list_fallback),
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                    )
                },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (systemList) {
                            OutlinedButton(
                                onClick = { listDialog = ListEditDialog.ClearAllConfirm },
                                modifier = Modifier.fillMaxWidth(),
                                shape = AppButtonShape,
                                enabled = state.listWords.isNotEmpty(),
                            ) {
                                ButtonLabel(
                                    stringResource(R.string.list_clear_all),
                                    color = scheme.error,
                                )
                            }
                        } else if (pendingInbox) {
                            Button(
                                onClick = {
                                    if (state.listWords.isEmpty()) {
                                        closeListDialogs()
                                        return@Button
                                    }
                                    if (moveTargets.isNotEmpty()) {
                                        moveTargetId = moveTargets.firstOrNull()?.id
                                        listDialog = ListEditDialog.MoveAll
                                    } else {
                                        closeListDialogs()
                                        createThenMoveAll = true
                                        showCreate = true
                                    }
                                },
                                modifier = Modifier.fillMaxWidth(),
                                shape = AppButtonShape,
                                enabled = state.listWords.isNotEmpty(),
                            ) { ButtonLabel(stringResource(R.string.list_move_all)) }
                            OutlinedButton(
                                onClick = { listDialog = ListEditDialog.DeleteConfirm },
                                modifier = Modifier.fillMaxWidth(),
                                shape = AppButtonShape,
                            ) {
                                ButtonLabel(
                                    stringResource(R.string.list_delete),
                                    color = scheme.error,
                                )
                            }
                        } else {
                            Button(
                                onClick = {
                                    renameDraft = selectedList?.name.orEmpty()
                                    listDialog = ListEditDialog.Rename
                                },
                                modifier = Modifier.fillMaxWidth(),
                                shape = AppButtonShape,
                            ) { ButtonLabel(stringResource(R.string.list_rename)) }
                            Button(
                                onClick = {
                                    if (state.listWords.isEmpty()) {
                                        closeListDialogs()
                                        return@Button
                                    }
                                    if (moveTargets.isNotEmpty()) {
                                        moveTargetId = moveTargets.firstOrNull()?.id
                                        listDialog = ListEditDialog.MoveAll
                                    } else {
                                        closeListDialogs()
                                        createThenMoveAll = true
                                        showCreate = true
                                    }
                                },
                                modifier = Modifier.fillMaxWidth(),
                                shape = AppButtonShape,
                                enabled = state.listWords.isNotEmpty(),
                            ) { ButtonLabel(stringResource(R.string.list_move_all)) }
                            OutlinedButton(
                                onClick = { listDialog = ListEditDialog.DeleteConfirm },
                                modifier = Modifier.fillMaxWidth(),
                                shape = AppButtonShape,
                            ) {
                                ButtonLabel(
                                    stringResource(R.string.action_delete),
                                    color = scheme.error,
                                )
                            }
                        }
                    }
                },
                confirmButton = {},
                dismissButton = {
                    TextButton(onClick = { closeListDialogs() }) {
                        Text(stringResource(R.string.action_back), color = scheme.onSurfaceVariant)
                    }
                },
            )
        }
        ListEditDialog.Rename -> {
            val trimmedRename = renameDraft.trim()
            val renameNameError = listNameConflictMessage(
                LocalContext.current,
                state.lists,
                trimmedRename,
                excludeId = selectedList?.id,
            )
            val reservedRename = isReservedListNameMessage(LocalContext.current, trimmedRename)
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(stringResource(R.string.list_rename), fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = renameDraft,
                            onValueChange = { renameDraft = it },
                            singleLine = true,
                            shape = RoundedCornerShape(14.dp),
                            modifier = Modifier.fillMaxWidth(),
                            isError = renameNameError != null && !reservedRename,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = scheme.onSurface,
                                unfocusedTextColor = scheme.onSurface,
                                focusedContainerColor = scheme.surfaceVariant,
                                unfocusedContainerColor = scheme.surfaceVariant,
                                unfocusedBorderColor = scheme.outline.copy(alpha = 0f),
                            ),
                        )
                        if (renameNameError != null) {
                            Text(
                                renameNameError,
                                style = MaterialTheme.typography.labelMedium,
                                color = if (reservedRename) scheme.onSurfaceVariant else scheme.error,
                            )
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val id = selectedList?.id
                            if (id != null) onRenameList(id, renameDraft)
                            closeListDialogs()
                        },
                        shape = AppButtonShape,
                        enabled = trimmedRename.isNotBlank() && renameNameError == null,
                    ) { Text(stringResource(R.string.action_ok)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeListDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_cancel), color = scheme.onSurface)
                    }
                },
            )
        }
        ListEditDialog.DeleteConfirm -> {
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(stringResource(R.string.list_delete_confirm_title), fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    Text(
                        stringResource(
                            R.string.list_delete_confirm_body,
                            selectedList?.let { listDisplayName(it) }.orEmpty(),
                        ),
                        color = scheme.onSurfaceVariant,
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val id = selectedList?.id
                            if (id != null) onDeleteList(id)
                            expandedId = null
                            closeListDialogs()
                        },
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.error),
                    ) { Text(stringResource(R.string.action_delete)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeListDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_back), color = scheme.onSurface)
                    }
                },
            )
        }
        ListEditDialog.ClearAllConfirm -> {
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(
                        stringResource(R.string.list_clear_all_title),
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                    )
                },
                text = {
                    Text(
                        stringResource(
                            R.string.list_clear_all_body,
                            selectedList?.let { listDisplayName(it) }.orEmpty(),
                        ),
                        color = scheme.onSurfaceVariant,
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            onClearAllWords()
                            expandedId = null
                            closeListDialogs()
                        },
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.error),
                        enabled = state.listWords.isNotEmpty(),
                    ) { Text(stringResource(R.string.list_clear_all)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeListDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_cancel), color = scheme.onSurface)
                    }
                },
            )
        }
        ListEditDialog.MoveAll -> {
            val selectedMove = moveTargets.firstOrNull { it.id == moveTargetId } ?: moveTargets.firstOrNull()
            AlertDialog(
                onDismissRequest = { closeListDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(stringResource(R.string.list_move_to), fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        ExposedDropdownMenuBox(
                            expanded = moveMenuOpen,
                            onExpandedChange = { moveMenuOpen = it },
                        ) {
                            OutlinedTextField(
                                value = selectedMove?.let { listDisplayName(it) }.orEmpty(),
                                onValueChange = {},
                                readOnly = true,
                                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = moveMenuOpen) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .menuAnchor(MenuAnchorType.PrimaryNotEditable),
                                shape = RoundedCornerShape(14.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = scheme.onSurface,
                                    unfocusedTextColor = scheme.onSurface,
                                    focusedContainerColor = scheme.surfaceVariant,
                                    unfocusedContainerColor = scheme.surfaceVariant,
                                ),
                            )
                            ExposedDropdownMenu(
                                expanded = moveMenuOpen,
                                onDismissRequest = { moveMenuOpen = false },
                            ) {
                                moveTargets.forEach { list ->
                                    DropdownMenuItem(
                                        text = { Text(listDisplayName(list)) },
                                        onClick = {
                                            moveTargetId = list.id
                                            moveMenuOpen = false
                                        },
                                    )
                                }
                            }
                        }
                        TextButton(
                            onClick = {
                                closeListDialogs()
                                createThenMoveAll = true
                                showCreate = true
                            },
                        ) {
                            Text(stringResource(R.string.list_new), color = scheme.primary)
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val target = moveTargetId ?: selectedMove?.id
                            if (target != null) onMoveAllWords(target)
                            expandedId = null
                            closeListDialogs()
                        },
                        shape = AppButtonShape,
                        enabled = (moveTargetId ?: selectedMove?.id) != null,
                    ) { Text(stringResource(R.string.action_move)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeListDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_cancel), color = scheme.error)
                    }
                },
            )
        }
        ListEditDialog.None -> Unit
    }

    when (wordDialog) {
        WordEditDialog.DeleteConfirm -> {
            AlertDialog(
                onDismissRequest = { closeWordDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(
                        stringResource(R.string.list_delete_word_confirm),
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            wordTargetId?.let(onDeleteWord)
                            expandedId = null
                            closeWordDialogs()
                        },
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.error),
                    ) { Text(stringResource(R.string.action_delete)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeWordDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_back), color = scheme.onSurface)
                    }
                },
            )
        }
        WordEditDialog.Move -> {
            val selectedMove = moveTargets.firstOrNull { it.id == moveTargetId } ?: moveTargets.firstOrNull()
            AlertDialog(
                onDismissRequest = { closeWordDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(stringResource(R.string.list_move_word), fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    ExposedDropdownMenuBox(
                        expanded = moveMenuOpen,
                        onExpandedChange = { moveMenuOpen = it },
                    ) {
                        OutlinedTextField(
                            value = selectedMove?.let { listDisplayName(it) }.orEmpty(),
                            onValueChange = {},
                            readOnly = true,
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = moveMenuOpen) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .menuAnchor(MenuAnchorType.PrimaryNotEditable),
                            shape = RoundedCornerShape(14.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = scheme.onSurface,
                                unfocusedTextColor = scheme.onSurface,
                                focusedContainerColor = scheme.surfaceVariant,
                                unfocusedContainerColor = scheme.surfaceVariant,
                            ),
                        )
                        ExposedDropdownMenu(
                            expanded = moveMenuOpen,
                            onDismissRequest = { moveMenuOpen = false },
                        ) {
                            moveTargets.forEach { list ->
                                DropdownMenuItem(
                                    text = { Text(listDisplayName(list)) },
                                    onClick = {
                                        moveTargetId = list.id
                                        moveMenuOpen = false
                                    },
                                )
                            }
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val cardId = wordTargetId
                            val target = moveTargetId ?: selectedMove?.id
                            if (cardId != null && target != null) onMoveWord(cardId, target)
                            expandedId = null
                            closeWordDialogs()
                        },
                        shape = AppButtonShape,
                        enabled = (moveTargetId ?: selectedMove?.id) != null,
                    ) { Text(stringResource(R.string.action_move)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeWordDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_cancel), color = scheme.error)
                    }
                },
            )
        }
        WordEditDialog.None -> Unit
    }

    when (multiDialog) {
        MultiEditDialog.DeleteConfirm -> {
            AlertDialog(
                onDismissRequest = { closeMultiDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(
                        stringResource(R.string.list_delete_selected_title),
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                    )
                },
                text = {
                    Text(
                        stringResource(R.string.list_delete_selected_body, state.selectedWordIds.size),
                        color = scheme.onSurfaceVariant,
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            onDeleteSelectedWords()
                            expandedId = null
                            closeMultiDialogs()
                        },
                        shape = AppButtonShape,
                        colors = ButtonDefaults.buttonColors(containerColor = scheme.error),
                    ) { Text(stringResource(R.string.action_delete)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeMultiDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_back), color = scheme.onSurface)
                    }
                },
            )
        }
        MultiEditDialog.Move -> {
            val selectedMove = moveTargets.firstOrNull { it.id == moveTargetId } ?: moveTargets.firstOrNull()
            AlertDialog(
                onDismissRequest = { closeMultiDialogs() },
                shape = AppDialogShape,
                containerColor = scheme.surface,
                title = {
                    Text(stringResource(R.string.list_move_to), fontWeight = FontWeight.Bold, color = scheme.onSurface)
                },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        ExposedDropdownMenuBox(
                            expanded = moveMenuOpen,
                            onExpandedChange = { moveMenuOpen = it },
                        ) {
                            OutlinedTextField(
                                value = selectedMove?.let { listDisplayName(it) }.orEmpty(),
                                onValueChange = {},
                                readOnly = true,
                                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = moveMenuOpen) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .menuAnchor(MenuAnchorType.PrimaryNotEditable),
                                shape = RoundedCornerShape(14.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = scheme.onSurface,
                                    unfocusedTextColor = scheme.onSurface,
                                    focusedContainerColor = scheme.surfaceVariant,
                                    unfocusedContainerColor = scheme.surfaceVariant,
                                ),
                            )
                            ExposedDropdownMenu(
                                expanded = moveMenuOpen,
                                onDismissRequest = { moveMenuOpen = false },
                            ) {
                                moveTargets.forEach { list ->
                                    DropdownMenuItem(
                                        text = { Text(listDisplayName(list)) },
                                        onClick = {
                                            moveTargetId = list.id
                                            moveMenuOpen = false
                                        },
                                    )
                                }
                            }
                        }
                        TextButton(
                            onClick = {
                                closeMultiDialogs()
                                createThenMoveSelected = true
                                showCreate = true
                            },
                        ) {
                            Text(stringResource(R.string.list_new), color = scheme.primary)
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val target = moveTargetId ?: selectedMove?.id
                            if (target != null) onMoveSelectedWords(target)
                            expandedId = null
                            closeMultiDialogs()
                        },
                        shape = AppButtonShape,
                        enabled = (moveTargetId ?: selectedMove?.id) != null,
                    ) { Text(stringResource(R.string.action_move)) }
                },
                dismissButton = {
                    OutlinedButton(onClick = { closeMultiDialogs() }, shape = AppButtonShape) {
                        Text(stringResource(R.string.action_cancel), color = scheme.error)
                    }
                },
            )
        }
        MultiEditDialog.None -> Unit
    }

    if (showSortSheet) {
        ModalBottomSheet(
            onDismissRequest = { showSortSheet = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 8.dp)
                    .navigationBarsPadding(),
            ) {
                Text(
                    stringResource(R.string.sort_title),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(8.dp))
                ListSortOrder.entries.forEach { order ->
                    val selected = state.listSortOrder == order
                    Surface(
                        onClick = {
                            onSetSort(order)
                            showSortSheet = false
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("${TestTags.SORT_OPTION_PREFIX}${order.name.lowercase()}"),
                        color = if (selected) scheme.primaryContainer else Color.Transparent,
                        shape = RoundedCornerShape(12.dp),
                    ) {
                        Text(
                            order.label(),
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 14.dp),
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                        )
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }

    if (showFilterSheet) {
        ModalBottomSheet(
            onDismissRequest = { showFilterSheet = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 8.dp)
                    .navigationBarsPadding(),
            ) {
                Text(
                    stringResource(R.string.filter_title),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    stringResource(R.string.filter_section_pos),
                    style = MaterialTheme.typography.labelLarge,
                    color = scheme.onSurfaceVariant,
                )
                Spacer(modifier = Modifier.height(8.dp))
                FlowRowChips {
                    LIST_FILTER_POS_KEYS.forEach { key ->
                        val selected = key in draftFilter.pos
                        FilterToggleChip(
                            label = if (key == "unknown") {
                                stringResource(R.string.filter_pos_unknown)
                            } else {
                                localizedPosLabel(key).ifBlank { key }
                            },
                            selected = selected,
                            onClick = {
                                draftFilter = draftFilter.copy(
                                    pos = if (selected) draftFilter.pos - key else draftFilter.pos + key,
                                )
                            },
                        )
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    stringResource(R.string.filter_section_state),
                    style = MaterialTheme.typography.labelLarge,
                    color = scheme.onSurfaceVariant,
                )
                Spacer(modifier = Modifier.height(8.dp))
                FlowRowChips {
                    CardStateFilter.entries.forEach { st ->
                        val selected = st in draftFilter.states
                        FilterToggleChip(
                            label = st.label(),
                            selected = selected,
                            onClick = {
                                draftFilter = draftFilter.copy(
                                    states = if (selected) draftFilter.states - st else draftFilter.states + st,
                                )
                            },
                        )
                    }
                }
                Spacer(modifier = Modifier.height(20.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedButton(
                        onClick = {
                            draftFilter = ListFilterState()
                            onClearFilter()
                            showFilterSheet = false
                        },
                        modifier = Modifier.weight(1f),
                        shape = AppButtonShape,
                    ) {
                        Text(stringResource(R.string.action_clear_all))
                    }
                    Button(
                        onClick = {
                            onSetFilter(draftFilter)
                            showFilterSheet = false
                        },
                        modifier = Modifier
                            .weight(1f)
                            .testTag(TestTags.FILTER_APPLY),
                        shape = AppButtonShape,
                    ) {
                        Text(stringResource(R.string.action_apply))
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }

    detailCard?.let { card ->
        ListCardDetailOverlay(
            card = card,
            profile = state.activeProfile,
            onDismiss = { detailCard = null },
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ListWordTile(
    card: CardResponse,
    expanded: Boolean,
    selected: Boolean = false,
    selectionMode: Boolean = false,
    editProcessing: Boolean = false,
    flushInProgress: Boolean = false,
    onToggle: () -> Unit,
    onLongPress: () -> Unit = {},
    onViewCard: () -> Unit = {},
    onDelete: () -> Unit,
    onMove: () -> Unit,
    onFixCard: () -> Unit = {},
    onHistory: () -> Unit = {},
    onReview: () -> Unit = {},
) {
    val scheme = MaterialTheme.colorScheme
    var actionsMenuExpanded by remember(card.id) { mutableStateOf(false) }
    val bringIntoViewRequester = remember(card.id) { BringIntoViewRequester() }
    LaunchedEffect(expanded) {
        if (!expanded) {
            actionsMenuExpanded = false
            return@LaunchedEffect
        }
        // Po animacji rozwinięcia — przewiń tak, by cały kafelek był widoczny.
        delay(320)
        bringIntoViewRequester.bringIntoView()
    }
    val needsReview = card.enrichment_status == "needs_review"
    val awaitingNetwork = card.enrichment_status == "awaiting_network" && !flushInProgress
    val pending = card.enrichment_status == "pending" || flushInProgress
    val activityProcessing = !card.card_activity_status.isNullOrBlank() || editProcessing
    val failed = card.enrichment_status == "failed"
    val posKey = normalizePosKey(card.pos)
    val posLabelText = if (posKey == "unknown") {
        null
    } else {
        localizedPosLabel(card.pos).takeIf { it.isNotBlank() }
    }
    val statusLabel = when {
        needsReview -> stringResource(R.string.status_needs_review)
        awaitingNetwork -> stringResource(R.string.status_awaiting_network)
        pending -> null
        failed -> stringResource(R.string.status_error)
        card.srs_status.isNullOrBlank() -> null
        card.srs_status == "new" -> stringResource(R.string.status_new)
        card.srs_status == "learning" || card.srs_status == "relearning" -> stringResource(R.string.status_learning)
        card.srs_status == "review" && (card.srs_interval_days ?: 0.0) >= 21.0 -> stringResource(R.string.status_mastered)
        card.srs_status == "review" -> stringResource(R.string.status_review)
        else -> null
    }
    val meanings = remember(card.id, card.content) { cardMeaningGlosses(card.content) }
    val imported = remember(card.id, card.content) {
        com.vocabulario.app.ui.components.parseImportDisplayFromContent(card.content)
    }
    val muted = awaitingNetwork || activityProcessing || needsReview
    val tileColor = when {
        selected -> scheme.primary.copy(alpha = 0.12f)
        muted -> scheme.surfaceVariant.copy(alpha = 0.55f)
        else -> scheme.surfaceVariant
    }
    val textColor = if (muted) scheme.onSurface.copy(alpha = 0.45f) else scheme.onSurface
    val headerScroll = rememberScrollState()
    val tileHeaderHeight = 40.dp

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .bringIntoViewRequester(bringIntoViewRequester)
            .testTag(TestTags.LIST_WORD_TILE)
            .then(
                if (selected) Modifier.border(2.dp, scheme.primary, RoundedCornerShape(20.dp))
                else Modifier,
            ),
        shape = RoundedCornerShape(20.dp),
        color = tileColor,
        contentColor = scheme.onSurface,
    ) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = tileHeaderHeight, max = tileHeaderHeight)
                    .combinedClickable(
                        enabled = needsReview || (!pending && !awaitingNetwork && !activityProcessing),
                        onClick = { if (needsReview) onReview() else onToggle() },
                        onLongClick = onLongPress,
                    ),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .horizontalScroll(headerScroll),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        cardListHeadword(card).ifBlank { "—" },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = textColor,
                        maxLines = 1,
                        softWrap = false,
                    )
                    if (!pending && posLabelText != null) {
                        ListPosChip(label = posLabelText)
                    }
                }
                when {
                    needsReview -> {
                        Spacer(modifier = Modifier.width(8.dp))
                        StatusChip(
                            label = statusLabel ?: stringResource(R.string.status_needs_review),
                            failed = false,
                            muted = true,
                        )
                        IconButton(
                            onClick = onReview,
                            modifier = Modifier
                                .size(32.dp)
                                .testTag(TestTags.BTN_REVIEW_WORD),
                        ) {
                            Icon(
                                Icons.Default.ErrorOutline,
                                contentDescription = stringResource(R.string.status_needs_review),
                                tint = scheme.error,
                                modifier = Modifier.size(22.dp),
                            )
                        }
                    }
                    activityProcessing -> {
                        Spacer(modifier = Modifier.width(8.dp))
                        CardActivitySpinner(color = CorrectionActivityColor)
                    }
                    pending -> {
                        Spacer(modifier = Modifier.width(8.dp))
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            strokeWidth = 2.5.dp,
                            color = scheme.primary,
                        )
                    }
                    selected -> {
                        Spacer(modifier = Modifier.width(8.dp))
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = stringResource(R.string.cd_selected),
                            tint = scheme.primary,
                            modifier = Modifier.size(22.dp),
                        )
                    }
                    !selectionMode && statusLabel != null -> {
                        Spacer(modifier = Modifier.width(8.dp))
                        StatusChip(
                            label = statusLabel,
                            failed = failed,
                            muted = awaitingNetwork,
                        )
                    }
                }
            }

            val activityLabel = when {
                editProcessing && card.card_activity_status.isNullOrBlank() ->
                    stringResource(R.string.self_edit_validating)
                else -> cardActivityStatusLabel(card.card_activity_status)
            }
            activityLabel?.let { label ->
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    label,
                    style = MaterialTheme.typography.labelMedium,
                    color = CorrectionActivityColor,
                )
            }

            AnimatedVisibility(
                visible = expanded && !pending && !awaitingNetwork && !activityProcessing && !selectionMode,
                enter = expandVertically() + fadeIn(),
                exit = shrinkVertically() + fadeOut(),
            ) {
                Column(modifier = Modifier.padding(top = 4.dp)) {
                    if (imported != null) {
                        key(card.id, expanded) {
                            com.vocabulario.app.ui.components.ImportDisplayFlip(
                                display = imported,
                                showPrompt = false,
                            )
                        }
                    } else {
                        key(card.id, expanded) {
                            com.vocabulario.app.ui.components.ListRevealAnswer {
                                AdaptiveOrGlossReveal(card = card, meanings = meanings, scheme = scheme)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    HorizontalDivider(color = scheme.outline.copy(alpha = 0.5f))
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        ListTileIconButton(
                            onClick = onViewCard,
                            icon = Icons.AutoMirrored.Outlined.Article,
                            contentDescription = stringResource(R.string.cd_view_card),
                            containerColor = scheme.secondaryContainer,
                            contentColor = scheme.onSecondaryContainer,
                            modifier = Modifier.testTag(TestTags.BTN_VIEW_CARD),
                        )
                        AnimatedContent(
                            targetState = actionsMenuExpanded,
                            label = "listWordActions",
                        ) { menuExpanded ->
                            if (menuExpanded) {
                                Row(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    ListTileIconButton(
                                        onClick = onDelete,
                                        icon = Icons.Default.Close,
                                        contentDescription = stringResource(R.string.cd_delete),
                                        containerColor = scheme.error.copy(alpha = 0.15f),
                                        contentColor = scheme.error,
                                    )
                                    ListTileIconButton(
                                        onClick = onMove,
                                        icon = Icons.AutoMirrored.Outlined.DriveFileMove,
                                        contentDescription = stringResource(R.string.cd_move),
                                        containerColor = scheme.primaryContainer,
                                        contentColor = scheme.onPrimaryContainer,
                                    )
                                    ListTileIconButton(
                                        onClick = onFixCard,
                                        icon = Icons.Outlined.Edit,
                                        contentDescription = stringResource(R.string.correction_fix_card),
                                        containerColor = scheme.tertiaryContainer,
                                        contentColor = scheme.onTertiaryContainer,
                                        modifier = Modifier.testTag(TestTags.BTN_FIX_CARD),
                                    )
                                    if (card.has_content_changes) {
                                        ListTileIconButton(
                                            onClick = onHistory,
                                            icon = Icons.Outlined.History,
                                            contentDescription = stringResource(R.string.cd_card_history),
                                            containerColor = CorrectionActivityColor.copy(alpha = 0.15f),
                                            contentColor = CorrectionActivityColor,
                                            modifier = Modifier.testTag(TestTags.BTN_CARD_HISTORY),
                                        )
                                    }
                                }
                            } else {
                                ListTileIconButton(
                                    onClick = { actionsMenuExpanded = true },
                                    icon = Icons.Outlined.MoreVert,
                                    contentDescription = stringResource(R.string.cd_list_word_actions),
                                    containerColor = scheme.surface,
                                    contentColor = scheme.onSurfaceVariant,
                                    modifier = Modifier.testTag(TestTags.BTN_LIST_WORD_MENU),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ListTileIconButton(
    onClick: () -> Unit,
    icon: ImageVector,
    contentDescription: String,
    containerColor: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
) {
    Surface(
        onClick = onClick,
        shape = CircleShape,
        color = containerColor,
        contentColor = contentColor,
        modifier = modifier.size(40.dp),
    ) {
        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
            Icon(icon, contentDescription = contentDescription, modifier = Modifier.size(20.dp))
        }
    }
}

private fun cardListHeadword(card: CardResponse): String {
    val fromContent = card.content["lemma"]?.jsonPrimitive?.contentOrNull
    return fromContent?.takeIf { it.isNotBlank() } ?: card.lemma_l2
}

private fun cardMeaningGlosses(content: JsonObject): List<String> {
    val meanings = content["meanings"]?.jsonArray ?: return emptyList()
    return meanings.mapNotNull { el ->
        val obj = runCatching { el.jsonObject }.getOrNull() ?: return@mapNotNull null
        obj["gloss_l1"]?.jsonPrimitive?.contentOrNull?.takeIf { it.isNotBlank() }
    }
}

@Composable
private fun AdaptiveOrGlossReveal(
    card: CardResponse,
    meanings: List<String>,
    scheme: androidx.compose.material3.ColorScheme,
) {
    val glosses = meanings.ifEmpty {
        card.gloss_primary?.takeIf { it.isNotBlank() }?.let { listOf(it) }.orEmpty()
    }
    if (glosses.isEmpty()) {
        Text(
            stringResource(R.string.no_meanings),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth(),
        )
        return
    }
    if (glosses.size == 1) {
        Text(
            glosses.first(),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurface,
            modifier = Modifier.fillMaxWidth(),
        )
        return
    }
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        glosses.forEachIndexed { index, meaning ->
            NumberedGlossRow(
                index = index + 1,
                gloss = meaning,
                scheme = scheme,
            )
        }
    }
}

@Composable
private fun NumberedGlossRow(
    index: Int,
    gloss: String,
    scheme: androidx.compose.material3.ColorScheme,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
    ) {
        Box(
            modifier = Modifier.width(24.dp),
            contentAlignment = Alignment.TopEnd,
        ) {
            Text(
                text = "$index.",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = scheme.onSurfaceVariant,
                maxLines = 1,
            )
        }
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = gloss,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            color = scheme.onSurface,
        )
    }
}

@Composable
private fun ListPosChip(label: String) {
    val colors = LocalVocabExtraColors.current
    Surface(
        shape = AppChipShape,
        color = colors.chipPosContainer,
        contentColor = colors.chipPosOnContainer,
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            color = colors.chipPosOnContainer,
            maxLines = 1,
            softWrap = false,
        )
    }
}

@Composable
private fun StatusChip(label: String, failed: Boolean = false, muted: Boolean = false) {
    val scheme = MaterialTheme.colorScheme
    val statusColors = LocalVocabExtraColors.current
    val bg = when {
        failed -> scheme.error.copy(alpha = 0.18f)
        muted -> scheme.onSurface.copy(alpha = 0.08f)
        else -> statusColors.chipStatusContainer
    }
    val fg = when {
        failed -> scheme.error
        muted -> scheme.onSurface.copy(alpha = 0.55f)
        else -> statusColors.chipStatusOnContainer
    }
    Surface(
        shape = AppChipShape,
        color = bg,
        contentColor = fg,
    ) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            color = fg,
        )
    }
}

@Composable
private fun ListChip(
    list: WordListResponse,
    selected: Boolean,
    showMenu: Boolean,
    showSpinner: Boolean = false,
    onClick: () -> Unit,
    onMenu: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val bg = if (selected) scheme.onBackground else scheme.surfaceVariant
    val fg = if (selected) scheme.background else scheme.onSurface
    Surface(
        onClick = onClick,
        shape = AppChipShape,
        color = bg,
        contentColor = fg,
        modifier = Modifier.testTag(TestTags.LIST_CHIP),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                "${listDisplayName(list)} (${list.word_count})",
                style = MaterialTheme.typography.labelLarge,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                color = fg,
                maxLines = 1,
                softWrap = false,
            )
            if (showSpinner) {
                CircularProgressIndicator(
                    modifier = Modifier.size(14.dp),
                    strokeWidth = 1.5.dp,
                    color = if (selected) scheme.background else scheme.primary,
                )
            }
            if (showMenu) {
                Icon(
                    Icons.Outlined.MoreVert,
                    contentDescription = stringResource(R.string.cd_list_options),
                    tint = fg,
                    modifier = Modifier
                        .size(16.dp)
                        .testTag(TestTags.LIST_MENU)
                        .clickable(onClick = onMenu),
                )
            }
        }
    }
}
