package com.vocabulario.app.ui.add

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.ui.card.CardDetailContent

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddWordScreen(
    onBack: () -> Unit,
    viewModel: AddWordViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Dodaj słowo") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Wstecz")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = state.query,
                    onValueChange = viewModel::onQueryChange,
                    label = { Text("Wpisz słowo") },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                )
                TextButton(onClick = viewModel::lookup) {
                    Text("OK")
                }
            }

            state.source?.let {
                Spacer(Modifier.height(8.dp))
                Text("Źródło: $it", style = MaterialTheme.typography.labelMedium)
            }

            if (state.loading) {
                Spacer(Modifier.height(16.dp))
                CircularProgressIndicator()
            }

            state.error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }

            state.message?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.primary)
            }

            state.createdCard?.let { card ->
                Spacer(Modifier.height(16.dp))
                CardDetailContent(
                    card.content,
                    card.lemma_l2,
                    enrichmentStatus = card.enrichment_status,
                    enrichmentError = card.enrichment_error,
                )
                TextButton(onClick = viewModel::clearCard) { Text("Schowaj kartę") }
            }

            Spacer(Modifier.height(16.dp))
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.candidates) { candidate ->
                    CandidateRow(
                        candidate = candidate,
                        onAdd = { viewModel.addToLearning(candidate) },
                    )
                }
            }
        }
    }
}

@Composable
private fun CandidateRow(
    candidate: LookupCandidate,
    onAdd: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(candidate.lemma, style = MaterialTheme.typography.titleMedium)
                Text(candidate.gloss, style = MaterialTheme.typography.bodyMedium)
                candidate.pos?.let { Text(it, style = MaterialTheme.typography.labelSmall) }
            }
            IconButton(onClick = onAdd) {
                Icon(Icons.Default.Add, contentDescription = "Dodaj")
            }
        }
    }
}
