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
import androidx.compose.material3.MenuAnchorType
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.SUPPORTED_LEARNING_LANGS
import com.vocabulario.app.data.verbTensesFor
import com.vocabulario.app.ui.TestTags

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
        Text(stringResource(R.string.onboarding_title), style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            stringResource(R.string.onboarding_subtitle),
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(24.dp))

        LangDropdown(
            label = stringResource(R.string.onboarding_native),
            selected = state.appLang,
            onSelect = viewModel::setAppLang,
            testTag = TestTags.ONBOARDING_NATIVE,
        )
        Spacer(Modifier.height(12.dp))
        LangDropdown(
            label = stringResource(R.string.onboarding_learning),
            selected = state.learningLang,
            onSelect = viewModel::setLearningLang,
            testTag = TestTags.ONBOARDING_LEARNING,
        )

        Spacer(Modifier.height(20.dp))
        Text(stringResource(R.string.onboarding_cefr), style = MaterialTheme.typography.titleMedium)
        CEFR_LEVELS.forEach { level ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.testTag(TestTags.ONBOARDING_CEFR_PREFIX + level),
            ) {
                RadioButton(
                    selected = state.cefrLevel == level,
                    onClick = { viewModel.setCefr(level) },
                )
                Text(level)
            }
        }

        if (LanguagePacks.showsTensePicker(state.learningLang)) {
            Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.onboarding_tenses), style = MaterialTheme.typography.titleMedium)
            verbTensesFor(state.learningLang).forEach { (key, label) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked = key in state.selectedTenses,
                        onCheckedChange = { viewModel.toggleTense(key) },
                    )
                    Text(label)
                }
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
                modifier = Modifier.fillMaxWidth().testTag(TestTags.ONBOARDING_START),
            ) { Text(stringResource(R.string.onboarding_start)) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LangDropdown(
    label: String,
    selected: String,
    onSelect: (String) -> Unit,
    testTag: String? = null,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedLabel = SUPPORTED_LEARNING_LANGS.firstOrNull { it.first == selected }?.second ?: selected
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = Modifier.then(if (testTag != null) Modifier.testTag(testTag) else Modifier),
    ) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable),
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
