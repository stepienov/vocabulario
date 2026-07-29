package com.vocabulario.app.ui.onboarding

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.Row
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.SUPPORTED_LEARNING_LANGS
import com.vocabulario.app.data.VERB_TENSES

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    onComplete: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text("Konfiguracja nauki", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            "Wybierz parę językową, poziom CEFR i czasy czasowników.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(24.dp))

        LangDropdown(
            label = "Język ojczysty (L1)",
            selected = state.nativeLang,
            onSelect = viewModel::setNativeLang,
        )
        Spacer(Modifier.height(12.dp))
        LangDropdown(
            label = "Język uczony (L2)",
            selected = state.learningLang,
            onSelect = viewModel::setLearningLang,
        )

        Spacer(Modifier.height(20.dp))
        Text("Poziom CEFR", style = MaterialTheme.typography.titleMedium)
        CEFR_LEVELS.forEach { level ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                RadioButton(
                    selected = state.cefrLevel == level,
                    onClick = { viewModel.setCefr(level) },
                )
                Text(level)
            }
        }

        Spacer(Modifier.height(20.dp))
        Text("Czasy czasowników", style = MaterialTheme.typography.titleMedium)
        VERB_TENSES.forEach { (key, label) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = key in state.selectedTenses,
                    onCheckedChange = { viewModel.toggleTense(key) },
                )
                Text(label)
            }
        }

        state.error?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }

        Spacer(Modifier.height(24.dp))
        if (state.loading) {
            CircularProgressIndicator()
        } else {
            Button(
                onClick = { viewModel.complete(onComplete) },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Zacznij naukę") }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LangDropdown(label: String, selected: String, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val selectedLabel = SUPPORTED_LEARNING_LANGS.firstOrNull { it.first == selected }?.second ?: selected
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            SUPPORTED_LEARNING_LANGS.forEach { (code, name) ->
                DropdownMenuItem(
                    text = { Text(name) },
                    onClick = {
                        onSelect(code)
                        expanded = false
                    },
                )
            }
        }
    }
}
