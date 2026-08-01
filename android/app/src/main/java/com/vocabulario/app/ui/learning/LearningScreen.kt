package com.vocabulario.app.ui.learning

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.ui.card.CardDetailContent
import com.vocabulario.app.ui.components.AddToListSheet
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.EmptyState
import com.vocabulario.app.ui.components.WordListItem
import com.vocabulario.app.ui.home.listNameConflictMessage
import kotlinx.serialization.json.jsonPrimitive

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LearningScreen(
    onBack: () -> Unit,
    viewModel: LearningViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

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

    AppScreenScaffold(title = "Nauka", onBack = onBack) { paddingModifier ->
        Column(modifier = paddingModifier.fillMaxSize()) {
            if (state.loading) {
                CircularProgressIndicator()
                return@Column
            }
            state.error?.let { Text(it) }
            state.message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }

            state.selectedCard?.let { card ->
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    CardDetailContent(
                        card.content,
                        card.lemma_l2,
                        card.content["language"]?.jsonPrimitive?.content,
                        userTenses = state.userTenses,
                        userCefr = state.userCefr,
                        enrichmentStatus = card.enrichment_status,
                        enrichmentError = card.enrichment_error,
                        onAddRelated = viewModel::openAddRelated,
                    )
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = viewModel::clearSelection) { Text("Wróć do listy") }
                }
                return@Column
            }

            if (state.cards.isEmpty() && state.error == null) {
                EmptyState("Nie masz jeszcze słówek w nauce", "Wyszukaj słowo na ekranie głównym")
            }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(state.cards) { card ->
                    WordListItem(
                        lemma = card.lemma_l2,
                        gloss = card.gloss_primary,
                        pos = card.pos,
                        enrichmentStatus = card.enrichment_status,
                        onClick = { viewModel.selectCard(card) },
                    )
                }
            }
        }
    }
}
