package com.vocabulario.app.ui.practice

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.ScrollState
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.graphics.Color
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.asJsonString
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.card.FlashcardBackContent
import com.vocabulario.app.ui.card.StickyLemmaBar
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.ButtonLabel
import com.vocabulario.app.ui.components.EmptyState
import com.vocabulario.app.ui.components.PracticeProgressBar
import com.vocabulario.app.ui.components.PromptCard
import com.vocabulario.app.ui.theme.ActionConfirm

@Composable
fun ListFlashcardsScreen(
    onFinished: (ListFlashcardSummary) -> Unit,
    viewModel: ListFlashcardsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(state.finishedSummary) {
        val summary = state.finishedSummary ?: return@LaunchedEffect
        onFinished(summary)
    }

    BackHandler(enabled = state.finishedSummary == null) {
        viewModel.exit()
    }

    val title = state.listTitle.ifBlank { stringResource(R.string.list_flashcards) }
    AppScreenScaffold(
        title = title,
        onBack = { viewModel.exit() },
        actions = {
            IconButton(
                onClick = viewModel::exit,
                modifier = Modifier.testTag(TestTags.LIST_FLASHCARDS_CLOSE),
            ) {
                Icon(
                    Icons.Default.Close,
                    contentDescription = stringResource(R.string.action_close),
                )
            }
        },
    ) { paddingModifier ->
        Column(modifier = paddingModifier.fillMaxSize()) {
            if (!state.loading && !state.empty && state.current != null) {
                PracticeProgressBar(state.progress)
                Spacer(Modifier.height(16.dp))
            }
            when {
                state.loading -> Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }
                state.error != null && state.current == null -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(state.error!!, color = MaterialTheme.colorScheme.error)
                        Spacer(Modifier.height(16.dp))
                        Button(
                            onClick = viewModel::load,
                            shape = AppButtonShape,
                        ) { Text(stringResource(R.string.action_retry)) }
                    }
                }
                state.empty || state.current == null -> {
                    EmptyState(stringResource(R.string.list_flashcards_empty))
                    Spacer(Modifier.height(16.dp))
                    Button(
                        onClick = viewModel::exit,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(TestTags.LIST_FLASHCARDS_EMPTY_BACK),
                        shape = AppButtonShape,
                    ) { Text(stringResource(R.string.action_return)) }
                }
                !state.revealed -> {
                    val prompt = state.current!!.lemma_l2
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .clickable(enabled = !state.busy, onClick = viewModel::reveal),
                        verticalArrangement = Arrangement.Center,
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        PromptCard(prompt, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(24.dp))
                        Button(
                            onClick = viewModel::reveal,
                            enabled = !state.busy,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(52.dp)
                                .testTag(TestTags.PRACTICE_SHOW_ANSWER),
                            shape = AppButtonShape,
                        ) {
                            Text(
                                stringResource(R.string.practice_show_answer),
                                style = MaterialTheme.typography.titleMedium,
                            )
                        }
                    }
                }
                else -> {
                    val card = state.current!!
                    val cardScroll = remember(card.id) { ScrollState(0) }
                    val stickyLemma = card.content["lemma"].asJsonString() ?: card.lemma_l2
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                    ) {
                        StickyLemmaBar(
                            lemma = stickyLemma,
                            modifier = Modifier.padding(horizontal = 8.dp),
                        )
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxWidth()
                                .verticalScroll(cardScroll),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            FlashcardBackContent(
                                content = card.content,
                                lemmaFallback = card.lemma_l2,
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
                                showHeadword = false,
                            )
                            Spacer(Modifier.height(8.dp))
                        }
                        if (state.error != null) {
                            Text(
                                state.error!!,
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.padding(bottom = 8.dp),
                            )
                        }
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(MaterialTheme.colorScheme.background)
                                .padding(top = 14.dp, bottom = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Button(
                                onClick = viewModel::addToLearning,
                                enabled = !state.busy,
                                modifier = Modifier
                                    .weight(1f)
                                    .height(56.dp)
                                    .testTag(TestTags.LIST_FLASHCARDS_ADD),
                                shape = AppButtonShape,
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = MaterialTheme.colorScheme.primary,
                                    contentColor = Color.White,
                                ),
                            ) { ButtonLabel(stringResource(R.string.list_flashcards_add), color = Color.White) }
                            Button(
                                onClick = viewModel::next,
                                enabled = !state.busy,
                                modifier = Modifier
                                    .weight(1f)
                                    .height(56.dp)
                                    .testTag(TestTags.LIST_FLASHCARDS_NEXT),
                                shape = AppButtonShape,
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = ActionConfirm,
                                    contentColor = Color.White,
                                ),
                            ) { ButtonLabel(stringResource(R.string.list_flashcards_next), color = Color.White) }
                        }
                    }
                }
            }
        }
    }
}
