package com.vocabulario.app.ui.practice

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.ui.card.CardActivitySpinner
import com.vocabulario.app.ui.card.CardCorrectionReportSheet
import com.vocabulario.app.ui.card.CardCorrectionResultDialog
import com.vocabulario.app.ui.card.CardHistorySheet
import com.vocabulario.app.ui.card.CardSelfEditSheet
import com.vocabulario.app.ui.card.CardSelfEditWarningDialog
import com.vocabulario.app.ui.card.CorrectionActivityColor
import com.vocabulario.app.ui.card.cardActivityStatusLabel
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.data.containsLemma
import com.vocabulario.app.data.langDisplayName
import com.vocabulario.app.ui.card.FlashcardBackContent
import com.vocabulario.app.ui.components.ImportDisplayFlip
import com.vocabulario.app.ui.components.parseImportDisplayFromContent
import com.vocabulario.app.ui.components.AddToListSheet
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogButtonRow
import com.vocabulario.app.ui.components.AppGrayField
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.ChoiceTile
import com.vocabulario.app.ui.components.EmptyState
import com.vocabulario.app.ui.components.GradeRow
import com.vocabulario.app.ui.components.PracticeProgressBar
import com.vocabulario.app.ui.components.PromptCard
import com.vocabulario.app.ui.home.listNameConflictMessage
import com.vocabulario.app.ui.theme.GradeAgain
import com.vocabulario.app.ui.theme.GradeKnown
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PracticeScreen(
    onBack: () -> Unit,
    viewModel: PracticeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadQueue() }

    LaunchedEffect(state.showCorrectToast) {
        if (state.showCorrectToast) {
            delay(1100)
            viewModel.dismissCorrectToast()
        }
    }

    LaunchedEffect(state.showWrongToast) {
        if (state.showWrongToast) {
            delay(1100)
            viewModel.dismissWrongToast()
        }
    }

    val item = state.queue.getOrNull(state.currentIndex)
    val direction = item?.direction ?: "l2_to_l1"
    val prompt = item?.let {
        if (direction == "l2_to_l1") it.lemma_l2 else (it.gloss_primary ?: "?")
    }
    val progress = if (state.queue.isEmpty()) 0f else (state.currentIndex + 1f) / state.queue.size

    if (state.phase == PracticePhase.WRONG_MODAL && state.selectedChoice != null) {
        val wrong = state.selectedChoice!!
        val scheme = MaterialTheme.colorScheme
        val (head, bridge, tail) = if (direction == "l2_to_l1") {
            Triple(
                wrong.text.ifBlank { wrong.gloss ?: "?" },
                stringResource(R.string.practice_bridge_l2, langDisplayName(state.learningLang)),
                wrong.lemma_l2 ?: "?",
            )
        } else {
            Triple(
                wrong.lemma_l2 ?: wrong.text,
                stringResource(R.string.practice_bridge_means),
                wrong.gloss ?: "?",
            )
        }
        AppAlertDialog(
            onDismissRequest = viewModel::dismissWrongModal,
            titleContent = {
                Text(
                    stringResource(R.string.practice_error_title),
                    fontWeight = FontWeight.Bold,
                    color = GradeAgain,
                )
            },
            text = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        head,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        color = scheme.onSurface,
                        textAlign = TextAlign.Center,
                    )
                    Text(
                        bridge,
                        style = MaterialTheme.typography.labelLarge,
                        color = scheme.onSurfaceVariant,
                    )
                    Text(
                        tail,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = scheme.primary,
                        textAlign = TextAlign.Center,
                    )
                }
            },
            buttons = {
                AppDialogButtonRow(
                    primaryText = stringResource(R.string.action_ok),
                    onPrimary = viewModel::dismissWrongModal,
                    primaryModifier = Modifier.testTag(TestTags.PRACTICE_WRONG_DISMISS),
                )
            },
        )
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AppScreenScaffold(
            title = stringResource(R.string.practice_title),
            onBack = onBack,
            actions = {
                IconButton(
                    onClick = viewModel::undo,
                    enabled = state.canUndo,
                    modifier = Modifier.testTag(TestTags.BTN_PRACTICE_UNDO),
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.Undo,
                        contentDescription = stringResource(R.string.cd_undo),
                    )
                }
            },
        ) { paddingModifier ->
            Column(modifier = paddingModifier.fillMaxSize()) {
                if (!state.loading && !state.emptyQueue && item != null) {
                    PracticeProgressBar(progress)
                    Spacer(Modifier.height(16.dp))
                }

                when {
                    state.loading -> BoxCentered { CircularProgressIndicator() }
                    state.error != null -> {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(state.error!!, color = MaterialTheme.colorScheme.error)
                            Spacer(Modifier.height(16.dp))
                            Button(
                                onClick = { viewModel.loadQueue() },
                                shape = AppButtonShape,
                                modifier = Modifier.testTag(TestTags.PRACTICE_RETRY),
                            ) { Text(stringResource(R.string.action_retry)) }
                        }
                    }
                    state.emptyQueue -> {
                        EmptyState(stringResource(R.string.practice_empty))
                        Spacer(Modifier.height(16.dp))
                        Button(
                            onClick = onBack,
                            modifier = Modifier.fillMaxWidth().testTag(TestTags.PRACTICE_EMPTY_BACK),
                            shape = AppButtonShape,
                        ) { Text(stringResource(R.string.action_return)) }
                    }
                    item == null -> BoxCentered { CircularProgressIndicator() }
                    state.answerMode == AnswerMode.CHOICE && state.loadingChoices -> BoxCentered { CircularProgressIndicator() }
                    else -> {
                        when (state.phase) {
                            PracticePhase.ANSWERING, PracticePhase.WRONG_MODAL -> {
                                when (state.answerMode) {
                                    AnswerMode.FLASHCARD -> {
                                        Column(
                                            modifier = Modifier
                                                .weight(1f)
                                                .fillMaxWidth()
                                                .clickable(onClick = viewModel::revealFlashcard),
                                            verticalArrangement = Arrangement.Center,
                                            horizontalAlignment = Alignment.CenterHorizontally,
                                        ) {
                                            prompt?.let { PromptCard(it, modifier = Modifier.fillMaxWidth()) }
                                            Spacer(Modifier.height(24.dp))
                                            Button(
                                                onClick = viewModel::revealFlashcard,
                                                modifier = Modifier.fillMaxWidth().height(52.dp).testTag(TestTags.PRACTICE_SHOW_ANSWER),
                                                shape = AppButtonShape,
                                            ) {
                                                Text(stringResource(R.string.practice_show_answer), style = MaterialTheme.typography.titleMedium)
                                            }
                                        }
                                    }
                                    AnswerMode.CHOICE -> {
                                        prompt?.let { PromptCard(it) }
                                        Spacer(Modifier.height(20.dp))
                                        LazyColumn(
                                            verticalArrangement = Arrangement.spacedBy(10.dp),
                                            modifier = Modifier.weight(1f),
                                        ) {
                                            items(state.choices) { choice ->
                                                val disabled = choice.text in state.disabledChoiceTexts
                                                val tileLemma = choice.lemma_l2 ?: choice.text
                                                val tileGloss = choice.gloss
                                                    ?: if (direction == "l2_to_l1") choice.text else null
                                                val displayText = if (disabled) tileLemma else choice.text
                                                val displayGloss = if (disabled) tileGloss else null
                                                val addLemma = choice.lemma_l2?.trim().orEmpty()
                                                val showAdd = disabled &&
                                                    addLemma.isNotEmpty() &&
                                                    !choice.in_learning &&
                                                    !state.learningLemmas.containsLemma(addLemma)
                                                ChoiceTile(
                                                    text = displayText,
                                                    selected = false,
                                                    isCorrect = null,
                                                    enabled = !disabled && state.phase == PracticePhase.ANSWERING,
                                                    dimmed = disabled,
                                                    gloss = displayGloss,
                                                    showActions = disabled,
                                                    onAddLearning = if (showAdd) {
                                                        { viewModel.openAddWrongChoice(choice) }
                                                    } else {
                                                        null
                                                    },
                                                    onClick = { viewModel.submitChoice(choice) },
                                                )
                                            }
                                        }
                                    }
                                    AnswerMode.TYPE -> {
                                        prompt?.let { PromptCard(it) }
                                        Spacer(Modifier.height(20.dp))
                                        Column(modifier = Modifier.weight(1f)) {
                                            AppGrayField(
                                                value = state.typedAnswer,
                                                onValueChange = viewModel::onTypedAnswerChange,
                                                placeholder = stringResource(R.string.practice_your_answer),
                                                modifier = Modifier.testTag(TestTags.PRACTICE_ANSWER_INPUT),
                                                singleLine = true,
                                            )
                                            Spacer(Modifier.height(16.dp))
                                            Button(
                                                onClick = viewModel::submitTyped,
                                                modifier = Modifier.fillMaxWidth().height(52.dp).testTag(TestTags.PRACTICE_CHECK),
                                                enabled = state.typedAnswer.isNotBlank(),
                                                shape = AppButtonShape,
                                            ) { Text(stringResource(R.string.action_check), style = MaterialTheme.typography.titleMedium) }
                                        }
                                    }
                                }
                            }
                            PracticePhase.SHOW_CARD -> {
                                Column(
                                    modifier = Modifier
                                        .weight(1f)
                                        .fillMaxWidth(),
                                ) {
                                    Column(
                                        modifier = Modifier
                                            .weight(1f)
                                            .fillMaxWidth()
                                            .verticalScroll(rememberScrollState()),
                                        verticalArrangement = Arrangement.spacedBy(12.dp),
                                    ) {
                                        when {
                                            state.typoWarning -> {
                                                Text(
                                                    stringResource(R.string.practice_spelling_warn),
                                                    style = MaterialTheme.typography.titleMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                    color = com.vocabulario.app.ui.theme.GradeLearning,
                                                )
                                                Text(
                                                    stringResource(R.string.practice_spelling_detail, state.typedAnswer, state.expectedAnswer ?: "?"),
                                                    style = MaterialTheme.typography.bodyMedium,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                )
                                            }
                                            state.lastCorrect == false && state.answerMode == AnswerMode.TYPE -> {
                                                Text(
                                                    stringResource(R.string.practice_correct_answer, state.expectedAnswer ?: "?"),
                                                    style = MaterialTheme.typography.titleMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                )
                                            }
                                        }
                                        val importDisplay = parseImportDisplayFromContent(item.content)
                                        if (importDisplay != null) {
                                            ImportDisplayFlip(
                                                display = importDisplay,
                                                enableTts = true,
                                                learningLang = state.learningLang,
                                                revealed = true,
                                            )
                                        } else {
                                            FlashcardBackContent(
                                                content = item.content,
                                                lemmaFallback = item.lemma_l2,
                                                userTenses = state.userTenses,
                                                userCefr = state.userCefr,
                                                showUsages = state.showUsages,
                                                showExampleSentences = state.showExampleSentences,
                                                showSynonyms = state.showSynonyms,
                                                showAntonyms = state.showAntonyms,
                                                showWordFamily = state.showWordFamily,
                                                showPeriphrases = state.showPeriphrases,
                                                showConjugation = state.showConjugation,
                                                conjugationExpandedDefault = state.conjugationExpandedDefault,
                                                relatedWordsExpandedDefault = state.relatedWordsExpandedDefault,
                                                profile = state.activeProfile,
                                                onAddRelated = viewModel::openAddRelated,
                                                learningLemmas = state.learningLemmas,
                                            )
                                        }
                                        Spacer(Modifier.height(8.dp))
                                    }
                                    val activityLabel = cardActivityStatusLabel(item.card_activity_status)
                                    if (activityLabel != null) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.Center,
                                            verticalAlignment = Alignment.CenterVertically,
                                        ) {
                                            CardActivitySpinner(color = CorrectionActivityColor)
                                            Spacer(Modifier.padding(horizontal = 8.dp))
                                            Text(
                                                activityLabel,
                                                style = MaterialTheme.typography.labelMedium,
                                                color = CorrectionActivityColor,
                                            )
                                        }
                                        Spacer(Modifier.height(8.dp))
                                    }
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .background(MaterialTheme.colorScheme.background)
                                            .navigationBarsPadding()
                                            .padding(top = 14.dp, bottom = 8.dp),
                                    ) {
                                        GradeRow(
                                            onAgain = { viewModel.grade("again") },
                                            onHard = { viewModel.grade("hard") },
                                            onGood = { viewModel.grade("good") },
                                            onEasy = { viewModel.grade("easy") },
                                            enabled = !state.grading,
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        state.addTarget?.let { target ->
            AddToListSheet(
                lemma = target.lemma,
                gloss = target.glossL1,
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
                onLearning = viewModel::addRelatedToLearning,
                onOther = viewModel::openOtherLists,
                onPickList = viewModel::addRelatedToList,
                onCreateNameChange = viewModel::onCreateListNameChange,
                onCreateAndAdd = viewModel::createListAndAddRelated,
                onShowCreatePrompt = viewModel::openCreateListPrompt,
                onBackFromCreatePrompt = viewModel::backFromCreateListPrompt,
                onBackFromListPicker = viewModel::backFromListPicker,
            )
        }

        AnimatedVisibility(
            visible = state.showCorrectToast,
            enter = fadeIn(tween(280)) + scaleIn(initialScale = 0.92f, animationSpec = tween(320)),
            exit = fadeOut(tween(450)),
            modifier = Modifier.align(Alignment.Center),
        ) {
            Surface(
                shape = RoundedCornerShape(28.dp),
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
                shadowElevation = 8.dp,
                tonalElevation = 2.dp,
            ) {
                Text(
                    stringResource(R.string.practice_well_done),
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = GradeKnown,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp, vertical = 20.dp),
                )
            }
        }

        AnimatedVisibility(
            visible = state.showWrongToast,
            enter = fadeIn(tween(280)) + scaleIn(initialScale = 0.92f, animationSpec = tween(320)),
            exit = fadeOut(tween(450)),
            modifier = Modifier.align(Alignment.Center),
        ) {
            Surface(
                shape = RoundedCornerShape(28.dp),
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
                shadowElevation = 8.dp,
                tonalElevation = 2.dp,
            ) {
                Text(
                    stringResource(R.string.practice_error_title),
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = GradeAgain,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp, vertical = 20.dp),
                )
            }
        }

        CardCorrectionReportSheet(
            visible = state.correctionOpen,
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
            lemma = state.selfEditCard?.lemma_l2 ?: "—",
            issues = state.selfEditValidationIssues,
            onConfirm = viewModel::confirmSelfEditWarning,
            onRevert = viewModel::revertSelfEditWarning,
        )
        CardHistorySheet(
            visible = state.historyOpen,
            loading = state.historyLoading,
            restoring = state.historyRestoring,
            events = state.historyEvents,
            onDismiss = viewModel::dismissCardHistory,
            onRestore = viewModel::restoreFromHistory,
        )
    }
}

@Composable
private fun BoxCentered(content: @Composable () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) { content() }
}
