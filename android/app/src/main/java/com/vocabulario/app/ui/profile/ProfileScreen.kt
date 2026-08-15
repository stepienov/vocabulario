package com.vocabulario.app.ui.profile

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.LanguagePacks
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.verbTensesFor

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    onBack: () -> Unit,
    onAddProfile: () -> Unit,
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.profile_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.cd_back),
                        )
                    }
                },
                actions = {
                    TextButton(onClick = onAddProfile) {
                        Text(stringResource(R.string.profile_new_pair))
                    }
                },
            )
        },
    ) { padding ->
        if (state.loading) {
            CircularProgressIndicator(modifier = Modifier.padding(padding).padding(24.dp))
            return@Scaffold
        }
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            state.activeProfile?.let { profile ->
                Text(
                    stringResource(
                        R.string.profile_active_pair,
                        profile.appLang.uppercase(),
                        profile.learning_lang.uppercase(),
                    ),
                    style = MaterialTheme.typography.titleLarge,
                )
                Text(
                    stringResource(R.string.profile_level, profile.cefr_level),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            Spacer(Modifier.height(16.dp))
            Text(stringResource(R.string.profile_pairs), style = MaterialTheme.typography.titleMedium)
            state.profiles.forEach { profile ->
                Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                stringResource(
                                    R.string.profile_active_pair,
                                    profile.appLang.uppercase(),
                                    profile.learning_lang.uppercase(),
                                ),
                            )
                            Text(
                                stringResource(R.string.profile_level, profile.cefr_level),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            if (profile.is_active) {
                                Text(
                                    stringResource(R.string.profile_active),
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                        if (!profile.is_active) {
                            TextButton(onClick = { viewModel.activateProfile(profile.id) }) {
                                Text(stringResource(R.string.profile_activate))
                            }
                        }
                    }
                }
            }

            Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.profile_cefr_active), style = MaterialTheme.typography.titleMedium)
            CEFR_LEVELS.forEach { level ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(
                        selected = state.cefrLevel == level,
                        onClick = { viewModel.setCefr(level) },
                    )
                    Text(level)
                }
            }

            val learningLang = state.activeProfile?.learning_lang
            if (LanguagePacks.showsTensePicker(learningLang)) {
                Spacer(Modifier.height(20.dp))
                Text(stringResource(R.string.profile_tenses), style = MaterialTheme.typography.titleMedium)
                verbTensesFor(learningLang).forEach { (key, label) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = key in state.selectedTenses,
                            onCheckedChange = { viewModel.toggleTense(key) },
                        )
                        Text(label)
                    }
                }
            }

            state.message?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.primary)
            }
            state.error?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}
