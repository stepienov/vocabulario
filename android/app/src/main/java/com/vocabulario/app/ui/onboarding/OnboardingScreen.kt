package com.vocabulario.app.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.CEFR_LEVELS
import com.vocabulario.app.data.SUPPORTED_LEARNING_LANGS
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppPillDropdown
import com.vocabulario.app.ui.components.ButtonLabel

@Composable
fun OnboardingScreen(
    onComplete: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val localeTag = LocalConfiguration.current.locales.toLanguageTags()
    key(localeTag) {
        if (state.step == 1) {
            OnboardingAppLangStep(
                appLang = state.appLang,
                onSelectLang = viewModel::setAppLang,
                onContinue = viewModel::goToLearningStep,
            )
        } else {
            OnboardingLearningStep(
                state = state,
                onBack = viewModel::backToAppLang,
                onSelectLearning = viewModel::setLearningLang,
                onSelectLevel = viewModel::setCefr,
                onStart = { viewModel.complete(onComplete) },
            )
        }
    }
}

@Composable
private fun OnboardingAppLangStep(
    appLang: String,
    onSelectLang: (String) -> Unit,
    onContinue: () -> Unit,
) {
    OnboardingChrome(
        footer = {
            OnboardingPrimaryButton(
                label = stringResource(R.string.onboarding_continue),
                onClick = onContinue,
                testTag = TestTags.ONBOARDING_CONTINUE,
            )
        },
    ) {
        AppPillDropdown(
            options = SUPPORTED_LEARNING_LANGS,
            selectedCode = appLang,
            onSelect = onSelectLang,
            label = stringResource(R.string.onboarding_choose_language),
            testTag = TestTags.ONBOARDING_NATIVE,
            labelTextAlign = TextAlign.Center,
            labelBottomPadding = 20.dp,
        )
    }
}

@Composable
private fun OnboardingLearningStep(
    state: OnboardingUiState,
    onBack: () -> Unit,
    onSelectLearning: (String) -> Unit,
    onSelectLevel: (String) -> Unit,
    onStart: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val learningOptions = SUPPORTED_LEARNING_LANGS.filterNot {
        it.first.equals(state.appLang, ignoreCase = true)
    }
    val levelOptions = CEFR_LEVELS.map { it to it } +
        (LEVEL_UNSURE to stringResource(R.string.onboarding_level_unknown))
    val canStart = state.learningLang.isNotBlank() && state.cefrLevel.isNotBlank() && !state.loading

    OnboardingChrome(
        onBack = onBack,
        footer = {
            if (state.loading) {
                CircularProgressIndicator(
                    color = scheme.primary,
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )
            } else {
                OnboardingPrimaryButton(
                    label = stringResource(R.string.onboarding_start),
                    onClick = onStart,
                    enabled = canStart,
                    testTag = TestTags.ONBOARDING_START,
                )
            }
        },
    ) {
        AppPillDropdown(
            options = learningOptions,
            selectedCode = state.learningLang,
            onSelect = onSelectLearning,
            label = stringResource(R.string.onboarding_want_to_learn),
            testTag = TestTags.ONBOARDING_LEARNING,
            labelTextAlign = TextAlign.Center,
            labelBottomPadding = 20.dp,
        )
        if (state.learningLang.isNotBlank()) {
            Spacer(Modifier.height(24.dp))
            AppPillDropdown(
                options = levelOptions,
                selectedCode = state.cefrLevel,
                onSelect = onSelectLevel,
                label = stringResource(R.string.onboarding_level),
                testTag = TestTags.ONBOARDING_LEVEL,
                labelTextAlign = TextAlign.Center,
                labelBottomPadding = 20.dp,
            )
        }
        state.error?.let {
            Spacer(Modifier.height(12.dp))
            Text(
                it,
                color = scheme.error,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun OnboardingChrome(
    onBack: (() -> Unit)? = null,
    footer: @Composable ColumnScope.() -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(scheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(horizontal = 24.dp)
            .padding(bottom = 20.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
        ) {
            if (onBack != null) {
                IconButton(
                    onClick = onBack,
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .testTag(TestTags.BTN_BACK),
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = stringResource(R.string.cd_back),
                        tint = scheme.onBackground,
                    )
                }
            }
            Text(
                stringResource(R.string.onboarding_app_setup),
                modifier = Modifier
                    .align(Alignment.Center)
                    .padding(horizontal = 48.dp),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                color = scheme.onBackground,
                textAlign = TextAlign.Center,
                maxLines = 1,
            )
        }
        BoxWithConstraints(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
        ) {
            val topPad = (maxHeight * 0.25f).coerceAtLeast(16.dp)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(top = topPad),
                content = content,
            )
        }
        Spacer(Modifier.height(16.dp))
        footer()
    }
}

@Composable
private fun OnboardingPrimaryButton(
    label: String,
    onClick: () -> Unit,
    testTag: String,
    enabled: Boolean = true,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp)
            .testTag(testTag),
        shape = AppButtonShape,
    ) {
        ButtonLabel(label, style = MaterialTheme.typography.titleMedium)
    }
}
