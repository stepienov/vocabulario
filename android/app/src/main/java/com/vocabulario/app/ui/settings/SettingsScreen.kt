package com.vocabulario.app.ui.settings

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.data.NEW_CARDS_OPTIONS
import com.vocabulario.app.data.langDisplayName
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppScreenScaffold
import com.vocabulario.app.ui.components.SettingsCheckRow
import com.vocabulario.app.ui.components.SettingsGroup
import com.vocabulario.app.ui.components.SettingsRadioRow

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

    AppScreenScaffold(title = "Ustawienia", onBack = onBack) { paddingModifier ->
        if (state.loading) {
            CircularProgressIndicator(modifier = paddingModifier.padding(24.dp))
            return@AppScreenScaffold
        }
        Column(
            modifier = paddingModifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
        ) {
            SettingsGroup("Forma odpowiedzi") {
                SettingsRadioRow("Wybór (8 opcji)", selected = state.practiceInputPref == "choice", onSelect = { viewModel.setInputPref("choice") })
                SettingsRadioRow("Wpisz", selected = state.practiceInputPref == "type", onSelect = { viewModel.setInputPref("type") })
                SettingsRadioRow("Fiszki", selected = state.practiceInputPref == "flashcard", onSelect = { viewModel.setInputPref("flashcard") }, showDivider = false)
            }

            SettingsGroup("Pokazuj najpierw słowo w języku") {
                state.activeProfile?.let { profile ->
                    val learningName = langDisplayName(profile.learning_lang)
                    val nativeName = langDisplayName(profile.native_lang)
                    SettingsRadioRow(learningName, selected = state.practiceDirection == "l2_to_l1", onSelect = { viewModel.setDirection("l2_to_l1") })
                    SettingsRadioRow(nativeName, selected = state.practiceDirection == "l1_to_l2", onSelect = { viewModel.setDirection("l1_to_l2") })
                }
                SettingsRadioRow("Losowo", selected = state.practiceDirection == "random", onSelect = { viewModel.setDirection("random") }, showDivider = false)
            }

            SettingsGroup("Wygląd karty odpowiedzi") {
                SettingsCheckRow(
                    label = "Zdania przykładowe",
                    subtitle = "Pokazuj przykład w sekcji znaczenia",
                    checked = state.showExampleSentences,
                    onCheckedChange = viewModel::setShowExampleSentences,
                )
                SettingsCheckRow(
                    label = "Użycia",
                    subtitle = "Przycisk „przykłady użycia →” i modal",
                    checked = state.showUsages,
                    onCheckedChange = viewModel::setShowUsages,
                )
                SettingsCheckRow(
                    label = "Synonimy i antonimy",
                    checked = state.showSynonymsAntonyms,
                    onCheckedChange = viewModel::setShowSynonymsAntonyms,
                )
                SettingsCheckRow(
                    label = "Rozwijaj synonimy / antonimy",
                    checked = state.relatedWordsExpandedDefault,
                    onCheckedChange = viewModel::setRelatedWordsExpandedDefault,
                )
                SettingsCheckRow(
                    label = "Peryfrazy",
                    checked = state.showPeriphrases,
                    onCheckedChange = viewModel::setShowPeriphrases,
                )
                SettingsCheckRow(
                    label = "Rozwijaj tabele odmiany",
                    subtitle = "Czasy wybierasz w Profilu",
                    checked = state.conjugationExpandedDefault,
                    onCheckedChange = viewModel::setConjugationExpandedDefault,
                    showDivider = false,
                )
            }

            SettingsGroup("Limit nowych kart / dzień") {
                NEW_CARDS_OPTIONS.forEachIndexed { index, (value, label) ->
                    SettingsRadioRow(
                        label,
                        selected = state.newCardsPerDay == value,
                        onSelect = { viewModel.setNewCardsPerDay(value) },
                        showDivider = index < NEW_CARDS_OPTIONS.lastIndex,
                    )
                }
            }

            SettingsGroup("Motyw") {
                SettingsRadioRow("Systemowy", selected = state.theme == "system", onSelect = { viewModel.setTheme("system") })
                SettingsRadioRow("Jasny", selected = state.theme == "light", onSelect = { viewModel.setTheme("light") })
                SettingsRadioRow("Ciemny", selected = state.theme == "dark", onSelect = { viewModel.setTheme("dark") }, showDivider = false)
            }

            state.message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = onLogout, modifier = Modifier.fillMaxWidth(), shape = AppButtonShape) {
                Text("Wyloguj się")
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}
