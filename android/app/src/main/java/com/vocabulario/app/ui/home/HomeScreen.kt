package com.vocabulario.app.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.automirrored.outlined.FormatListBulleted
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.data.langDisplayName
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppCard
import com.vocabulario.app.ui.components.NavTile
import com.vocabulario.app.ui.components.TagChip

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onPractice: () -> Unit,
    onFavorites: () -> Unit,
    onLearning: () -> Unit,
    onPacks: () -> Unit,
    onSettings: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    state.addedWordModal?.let { lemma ->
        AlertDialog(
            onDismissRequest = viewModel::dismissAddedModal,
            shape = RoundedCornerShape(20.dp),
            title = { Text("Dodano do nauki") },
            text = { Text("„$lemma” jest teraz w Twojej liście nauki.") },
            confirmButton = { TextButton(onClick = viewModel::dismissAddedModal) { Text("OK") } },
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.primary)
                .padding(horizontal = 20.dp, vertical = 20.dp),
        ) {
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    state.activeProfile?.let { profile ->
                        Text(
                            "${langDisplayName(profile.native_lang)} → ${langDisplayName(profile.learning_lang)}",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    }
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Ustawienia", tint = MaterialTheme.colorScheme.onPrimary)
                    }
                }
                Spacer(Modifier.height(16.dp))
                OutlinedTextField(
                    value = state.query,
                    onValueChange = viewModel::onQueryChange,
                    placeholder = { Text("Szukaj słowa…") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    shape = RoundedCornerShape(28.dp),
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { viewModel.search() }),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = MaterialTheme.colorScheme.surface,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                        focusedTextColor = MaterialTheme.colorScheme.onSurface,
                        unfocusedTextColor = MaterialTheme.colorScheme.onSurface,
                        focusedBorderColor = Color.Transparent,
                        unfocusedBorderColor = Color.Transparent,
                        cursorColor = MaterialTheme.colorScheme.primary,
                        focusedLeadingIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        unfocusedLeadingIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        focusedPlaceholderColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        unfocusedPlaceholderColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    ),
                )
            }
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 20.dp),
        ) {
            if (state.searchExpanded) {
                Spacer(Modifier.height(16.dp))
                if (state.loading) {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally).padding(24.dp))
                }
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(state.candidates) { candidate ->
                        CandidateRow(
                            candidate = candidate,
                            onFavorite = { viewModel.addFavorite(candidate) },
                            onAdd = { viewModel.addToLearning(candidate) },
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                Button(
                    onClick = onPractice,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape = AppButtonShape,
                ) { Text("Ćwicz") }
                Spacer(Modifier.height(16.dp))
            } else {
                Spacer(Modifier.height(24.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    NavTile("Ulubione", Icons.Outlined.StarOutline, onFavorites, Modifier.weight(1f))
                    NavTile("Nauka", Icons.Outlined.School, onLearning, Modifier.weight(1f))
                    NavTile("Listy", Icons.AutoMirrored.Outlined.FormatListBulleted, onPacks, Modifier.weight(1f))
                }
                Spacer(Modifier.weight(1f))
                Button(
                    onClick = onPractice,
                    modifier = Modifier.fillMaxWidth().height(56.dp),
                    shape = AppButtonShape,
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                ) {
                    Text("Ćwicz", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

@Composable
private fun CandidateRow(
    candidate: LookupCandidate,
    onFavorite: () -> Unit,
    onAdd: () -> Unit,
) {
    AppCard {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(candidate.lemma, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(candidate.gloss, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                candidate.pos?.let {
                    Spacer(Modifier.height(6.dp))
                    TagChip(com.vocabulario.app.data.posLabelPl(it).ifBlank { it })
                }
            }
            IconButton(onClick = onFavorite, enabled = !candidate.is_favorite) {
                Icon(
                    if (candidate.is_favorite) Icons.Default.Favorite else Icons.Outlined.FavoriteBorder,
                    contentDescription = "Ulubione",
                    tint = if (candidate.is_favorite) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (candidate.in_learning) {
                Text("✓", color = com.vocabulario.app.ui.theme.GradeKnown, fontWeight = FontWeight.Bold)
            } else {
                Surface(
                    onClick = onAdd,
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                ) {
                    Text("+", modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp), fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }
}
