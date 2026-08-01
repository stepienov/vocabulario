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
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.ui.card.FlashcardBackContent
import com.vocabulario.app.ui.components.AddToListSheet
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.ChoiceTile
import com.vocabulario.app.ui.components.EmptyState
import com.vocabulario.app.ui.components.GradeRow
import com.vocabulario.app.ui.components.PracticeProgressBar
import com.vocabulario.app.ui.components.PromptCard
import com.vocabulario.app.ui.home.listNameConflictMessage
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
                "to po hiszpańsku",
                wrong.lemma_l2 ?: "?",
            )
        } else {
            Triple(
                wrong.lemma_l2 ?: wrong.text,
                "oznacza",
                wrong.gloss ?: "?",
            )
        }
        AlertDialog(
            onDismissRequest = viewModel::dismissWrongModal,
            shape = AppDialogShape,
            containerColor = scheme.surface,
            title = {
                Text(
                    "Błąd",
                    fontWeight = FontWeight.Bold,
                    color = scheme.onSurface,
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
            confirmButton = {
                Button(
                    onClick = viewModel::dismissWrongModal,
                    shape = AppButtonShape,
                ) { Text("Powrót") }
            },
            dismissButton = {},
        )
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AppScreenScaffold(title = "Ćwicz", onBack = onBack) { paddingModifier ->
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
                            Button(onClick = { viewModel.loadQueue() }, shape = AppButtonShape) { Text("Spróbuj ponownie") }
                        }
                    }
                    state.emptyQueue -> {
                        EmptyState("Brak kart do ćwiczenia", "Dodaj słówka z ekranu głównego")
                        Spacer(Modifier.height(16.dp))
                        Button(onClick = onBack, modifier = Modifier.fillMaxWidth(), shape = AppButtonShape) { Text("Wróć") }
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
                                                modifier = Modifier.fillMaxWidth().height(52.dp),
                                                shape = AppButtonShape,
                                            ) {
                                                Text("Pokaż odpowiedź", style = MaterialTheme.typography.titleMedium)
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
                                                val subtitle = when {
                                                    !disabled -> null
                                                    direction == "l2_to_l1" -> choice.lemma_l2
                                                    else -> choice.gloss
                                                }
                                                ChoiceTile(
                                                    text = choice.text,
                                                    selected = false,
                                                    isCorrect = null,
                                                    enabled = !disabled && state.phase == PracticePhase.ANSWERING,
                                                    dimmed = disabled,
                                                    gloss = subtitle,
                                                    showActions = disabled,
                                                    canAddLearning = !choice.in_learning,
                                                    onAddLearning = { viewModel.addWrongToLearning(choice) },
                                                    onClick = { viewModel.submitChoice(choice) },
                                                )
                                            }
                                        }
                                    }
                                    AnswerMode.TYPE -> {
                                        prompt?.let { PromptCard(it) }
                                        Spacer(Modifier.height(20.dp))
                                        Column(modifier = Modifier.weight(1f)) {
                                            OutlinedTextField(
                                                value = state.typedAnswer,
                                                onValueChange = viewModel::onTypedAnswerChange,
                                                placeholder = { Text("Twoja odpowiedź") },
                                                modifier = Modifier.fillMaxWidth(),
                                                singleLine = true,
                                                shape = AppButtonShape,
                                                colors = OutlinedTextFieldDefaults.colors(
                                                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                                                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                                                    focusedTextColor = MaterialTheme.colorScheme.onSurface,
                                                    unfocusedTextColor = MaterialTheme.colorScheme.onSurface,
                                                ),
                                            )
                                            Spacer(Modifier.height(16.dp))
                                            Button(
                                                onClick = viewModel::submitTyped,
                                                modifier = Modifier.fillMaxWidth().height(52.dp),
                                                enabled = state.typedAnswer.isNotBlank(),
                                                shape = AppButtonShape,
                                            ) { Text("Sprawdź", style = MaterialTheme.typography.titleMedium) }
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
                                                    "Uważaj na pisownię!",
                                                    style = MaterialTheme.typography.titleMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                    color = com.vocabulario.app.ui.theme.GradeLearning,
                                                )
                                                Text(
                                                    "Wpisałeś ${state.typedAnswer} — prawidłowa pisownia: ${state.expectedAnswer ?: "?"}",
                                                    style = MaterialTheme.typography.bodyMedium,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                )
                                            }
                                            state.lastCorrect == false && state.answerMode == AnswerMode.TYPE -> {
                                                Text(
                                                    "Poprawna odpowiedź: ${state.expectedAnswer ?: "?"}",
                                                    style = MaterialTheme.typography.titleMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                )
                                            }
                                        }
                                        FlashcardBackContent(
                                            content = item.content,
                                            lemmaFallback = item.lemma_l2,
                                            userTenses = state.userTenses,
                                            userCefr = state.userCefr,
                                            showUsages = state.showUsages,
                                            showExampleSentences = state.showExampleSentences,
                                            showSynonyms = state.showSynonyms,
                                            showAntonyms = state.showAntonyms,
                                            showPeriphrases = state.showPeriphrases,
                                            showConjugation = state.showConjugation,
                                            conjugationExpandedDefault = state.conjugationExpandedDefault,
                                            relatedWordsExpandedDefault = state.relatedWordsExpandedDefault,
                                            onAddRelated = viewModel::openAddRelated,
                                        )
                                        Spacer(Modifier.height(8.dp))
                                    }
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .background(MaterialTheme.colorScheme.background)
                                            .padding(top = 14.dp, bottom = 8.dp),
                                    ) {
                                        GradeRow(
                                            onAgain = { viewModel.grade("again") },
                                            onHard = { viewModel.grade("hard") },
                                            onGood = { viewModel.grade("good") },
                                            onEasy = { viewModel.grade("easy") },
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
                createNameError = listNameConflictMessage(state.lists, state.createListName),
                onDismiss = viewModel::dismissAddSheet,
                onLearning = viewModel::addRelatedToLearning,
                onOther = viewModel::openOtherLists,
                onPickList = viewModel::addRelatedToList,
                onCreateNameChange = viewModel::onCreateListNameChange,
                onCreateAndAdd = viewModel::createListAndAddRelated,
                onShowCreatePrompt = viewModel::openCreateListPrompt,
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
                    "Dobrze!",
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = GradeKnown,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 32.dp, vertical = 20.dp),
                )
            }
        }
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
