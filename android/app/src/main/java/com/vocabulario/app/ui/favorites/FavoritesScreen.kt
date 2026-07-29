package com.vocabulario.app.ui.favorites

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.EmptyState
import com.vocabulario.app.ui.components.WordListItem

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FavoritesScreen(
    onBack: () -> Unit,
    viewModel: FavoritesViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

    AppScreenScaffold(title = "Ulubione", onBack = onBack) { paddingModifier ->
        Column(modifier = paddingModifier.fillMaxSize()) {
            if (state.loading) {
                CircularProgressIndicator()
                return@Column
            }
            state.error?.let { Text(it) }
            if (state.items.isEmpty() && state.error == null) {
                EmptyState("Brak ulubionych słówek")
            }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(state.items) { item ->
                    WordListItem(
                        lemma = item.lemma,
                        gloss = item.gloss,
                        pos = item.pos,
                        enrichmentStatus = item.enrichment_status,
                    )
                }
            }
        }
    }
}
