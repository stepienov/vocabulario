package com.vocabulario.app.ui.practice

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.ui.card.FlashcardBackContent
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.ChoiceTile
import com.vocabulario.app.ui.components.EmptyState
import com.vocabulario.app.ui.components.GradeRow
import com.vocabulario.app.ui.components.PracticeProgressBar
import com.vocabulario.app.ui.components.PromptCard

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PracticeScreen(
    onBack: () -> Unit,
    viewModel: PracticeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadQueue() }

    val item = state.queue.getOrNull(state.currentIndex)
    val prompt = item?.let {
        if ((it.direction ?: "l2_to_l1") == "l2_to_l1") it.lemma_l2 else (it.gloss_primary ?: "?")
    }
    val progress = if (state.queue.isEmpty()) 0f else (state.currentIndex + 1f) / state.queue.size

    if (state.phase == PracticePhase.WRONG_MODAL && state.selectedChoice != null) {
        val wrong = state.selectedChoice!!
        val lemma = wrong.lemma_l2 ?: wrong.text
        val gloss = wrong.gloss ?: "?"
        AlertDialog(
            onDismissRequest = viewModel::dismissWrongModal,
            shape = RoundedCornerShape(20.dp),
            title = { Text("Błąd") },
            text = {
                Text(
                    "„$lemma” oznacza „$gloss”",
                    style = MaterialTheme.typography.bodyLarge,
                )
            },
            confirmButton = {
                TextButton(onClick = viewModel::dismissWrongModal) { Text("Powrót") }
            },
            dismissButton = {},
        )
    }

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
                                            ChoiceTile(
                                                text = choice.text,
                                                selected = false,
                                                isCorrect = null,
                                                enabled = !disabled && state.phase == PracticePhase.ANSWERING,
                                                dimmed = disabled,
                                                gloss = choice.gloss,
                                                showActions = disabled,
                                                canFavorite = !choice.is_favorite,
                                                canAddLearning = !choice.in_learning,
                                                onFavorite = { viewModel.addWrongToFavorites(choice) },
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
                                                "Wpisałeś „${state.typedAnswer}” — prawidłowa pisownia: „${state.expectedAnswer ?: "?"}”",
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
                                        showSynonymsAntonyms = state.showSynonymsAntonyms,
                                        showPeriphrases = state.showPeriphrases,
                                        conjugationExpandedDefault = state.conjugationExpandedDefault,
                                        relatedWordsExpandedDefault = state.relatedWordsExpandedDefault,
                                        onAddRelatedToLearning = viewModel::addRelatedToLearning,
                                        onAddRelatedToFavorites = viewModel::addRelatedToFavorites,
                                    )
                                    Spacer(Modifier.height(8.dp))
                                }
                                GradeRow(
                                    onHard = { viewModel.grade("hard") },
                                    onLearning = { viewModel.grade("easy") },
                                    onKnown = { viewModel.grade("know_well") },
                                )
                                Spacer(Modifier.height(8.dp))
                            }
                        }
                    }
                }
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
