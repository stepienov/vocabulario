package com.vocabulario.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import android.net.Uri
import com.vocabulario.app.R
import com.vocabulario.app.data.BlockingBusy
import com.vocabulario.app.data.PairSession
import com.vocabulario.app.data.imports.ImportController
import com.vocabulario.app.ui.auth.AuthScreen
import com.vocabulario.app.ui.auth.AuthViewModel
import com.vocabulario.app.ui.auth.LegalGateScreen
import com.vocabulario.app.ui.auth.LogoutUnsentDialog
import com.vocabulario.app.ui.auth.UpdateRequiredScreen
import com.vocabulario.app.ui.auth.VerifyEmailScreen
import com.vocabulario.app.ui.deletion.DeletionPendingScreen
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.BusyOverlayHost
import com.vocabulario.app.ui.components.ButtonLabel
import com.vocabulario.app.ui.home.HomeScreen
import com.vocabulario.app.ui.learning.LearningScreen
import com.vocabulario.app.ui.onboarding.OnboardingScreen
import com.vocabulario.app.ui.packs.PacksScreen
import com.vocabulario.app.ui.practice.ListFlashcardSummary
import com.vocabulario.app.ui.practice.ListFlashcardsScreen
import com.vocabulario.app.ui.practice.PracticeScreen
import com.vocabulario.app.ui.profile.ProfileScreen
import com.vocabulario.app.ui.settings.SettingsScreen
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.components.SingletonComponent

object Routes {
    const val AUTH = "auth"
    const val VERIFY_EMAIL = "verify_email"
    const val LEGAL = "legal"
    const val DELETION_PENDING = "deletion_pending"
    const val ONBOARDING = "onboarding"
    const val HOME = "home"
    const val PRACTICE = "practice"
    const val LIST_FLASHCARDS = "list_flashcards/{listId}"
    const val SETTINGS = "settings"
    const val PROFILE = "profile"
    const val LEARNING = "learning"
    const val PACKS = "packs"
}

@EntryPoint
@InstallIn(SingletonComponent::class)
interface PairSessionEntryPoint {
    fun pairSession(): PairSession
}

@EntryPoint
@InstallIn(SingletonComponent::class)
interface BlockingBusyEntryPoint {
    fun blockingBusy(): BlockingBusy
}

@EntryPoint
@InstallIn(SingletonComponent::class)
interface ImportControllerEntryPoint {
    fun importController(): ImportController
}

@Composable
fun VocabularioAppRoot(
    appViewModel: AppViewModel = hiltViewModel(),
    authViewModel: AuthViewModel = hiltViewModel(),
) {
    val startRoute by appViewModel.startRoute.collectAsState()
    val updateRequired by appViewModel.updateRequired.collectAsState()
    val pairSession = rememberPairSession()
    val blockingBusy = rememberBlockingBusy()
    rememberImportController()
    val pairBusy by pairSession.busy.collectAsState()
    val requestBusy by blockingBusy.busy.collectAsState()
    val requestMessage by blockingBusy.message.collectAsState()

    LaunchedEffect(Unit) { appViewModel.bootstrap() }

    if (startRoute == AppStartRoute.LOADING) {
        if (updateRequired) {
            UpdateRequiredScreen(onCheckAgain = appViewModel::recheckUpdate)
            return
        }
        val loadingSlow by appViewModel.loadingSlow.collectAsState()
        Box(
            Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background),
            contentAlignment = Alignment.Center,
        ) {
            if (loadingSlow) {
                SlowStartPanel(onRetry = { appViewModel.retryBootstrap() })
            } else {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }
        }
        return
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
    ) {
        BusyOverlayHost(
            busy = pairBusy || requestBusy,
            message = requestMessage,
        ) {
            // Przebuduj graf przy zmianie trasy startowej (HOME ↔ AUTH ↔ ONBOARDING).
            key(startRoute) {
                val navController = rememberNavController()
                val restoreSettings by appViewModel.restoreSettings.collectAsState()
                LaunchedEffect(startRoute, restoreSettings) {
                    if (startRoute == AppStartRoute.HOME && restoreSettings) {
                        navController.navigate(Routes.SETTINGS)
                        appViewModel.onSettingsRestored()
                    }
                }
                val graphStart = when (startRoute) {
                    AppStartRoute.AUTH -> Routes.AUTH
                    AppStartRoute.VERIFY_EMAIL -> Routes.VERIFY_EMAIL
                    AppStartRoute.LEGAL -> Routes.LEGAL
                    AppStartRoute.DELETION_PENDING -> Routes.DELETION_PENDING
                    AppStartRoute.ONBOARDING -> Routes.ONBOARDING
                    AppStartRoute.HOME -> Routes.HOME
                    AppStartRoute.LOADING -> Routes.AUTH
                }

                NavHost(navController = navController, startDestination = graphStart) {
                    composable(Routes.AUTH) {
                        AuthScreen(
                            onAuthenticated = { needsOnboarding ->
                                appViewModel.completeAuthenticated(needsOnboarding)
                            },
                            onRegisterComplete = {
                                appViewModel.completeAuthenticated(needsOnboarding = true)
                            },
                        )
                    }
                    composable(Routes.VERIFY_EMAIL) {
                        val onLoggedOut: suspend () -> Unit = { appViewModel.onLogout() }
                        LogoutPromptHost(authViewModel, onLoggedOut)
                        VerifyEmailScreen(onLogout = { authViewModel.requestLogout(onLoggedOut) })
                    }
                    composable(Routes.LEGAL) {
                        val onLoggedOut: suspend () -> Unit = { appViewModel.onLogout() }
                        LogoutPromptHost(authViewModel, onLoggedOut)
                        LegalGateScreen(onLogout = { authViewModel.requestLogout(onLoggedOut) })
                    }
                    composable(Routes.DELETION_PENDING) {
                        DeletionPendingScreen()
                    }
                    composable(Routes.ONBOARDING) {
                        OnboardingScreen(
                            onComplete = { appViewModel.onOnboardingComplete() },
                        )
                    }
                    composable(Routes.HOME) { homeEntry ->
                        val flashReviewed by homeEntry.savedStateHandle
                            .getStateFlow("list_flash_reviewed", 0)
                            .collectAsState()
                        val flashAdded by homeEntry.savedStateHandle
                            .getStateFlow("list_flash_added", 0)
                            .collectAsState()
                        HomeScreen(
                            onPractice = { navController.navigate(Routes.PRACTICE) },
                            onSettings = { navController.navigate(Routes.SETTINGS) },
                            onOpenCard = { navController.navigate(Routes.LEARNING) },
                            onListFlashcards = { listId ->
                                navController.navigate(
                                    "list_flashcards/${Uri.encode(listId)}",
                                )
                            },
                            listFlashcardSummary = if (flashReviewed > 0) {
                                ListFlashcardSummary(flashReviewed, flashAdded)
                            } else {
                                null
                            },
                            onDismissListFlashcardSummary = {
                                homeEntry.savedStateHandle["list_flash_reviewed"] = 0
                                homeEntry.savedStateHandle["list_flash_added"] = 0
                            },
                        )
                    }
                    composable(Routes.PRACTICE) {
                        PracticeScreen(onBack = { navController.popBackStack() })
                    }
                    composable(
                        route = Routes.LIST_FLASHCARDS,
                        arguments = listOf(navArgument("listId") { type = NavType.StringType }),
                    ) {
                        ListFlashcardsScreen(
                            onFinished = { summary ->
                                if (summary.reviewed > 0) {
                                    navController.previousBackStackEntry?.savedStateHandle?.apply {
                                        set("list_flash_reviewed", summary.reviewed)
                                        set("list_flash_added", summary.added)
                                    }
                                }
                                navController.popBackStack()
                            },
                        )
                    }
                    composable(Routes.SETTINGS) {
                        val onLoggedOut: suspend () -> Unit = { appViewModel.onLogout() }
                        LogoutPromptHost(authViewModel, onLoggedOut)
                        SettingsScreen(
                            onBack = { navController.popBackStack() },
                            onLogout = { authViewModel.requestLogout(onLoggedOut) },
                        )
                    }
                    composable(Routes.PROFILE) {
                        ProfileScreen(
                            onBack = { navController.popBackStack() },
                            onAddProfile = { navController.navigate(Routes.ONBOARDING) },
                        )
                    }
                    composable(Routes.LEARNING) {
                        LearningScreen(onBack = { navController.popBackStack() })
                    }
                    composable(Routes.PACKS) {
                        PacksScreen(onBack = { navController.popBackStack() })
                    }
                }
            }
        }
        // Nad nawigacją, żeby stan ekranów i kolejki przetrwały blokadę.
        if (updateRequired) {
            UpdateRequiredScreen(onCheckAgain = appViewModel::recheckUpdate)
        }
    }
}

@Composable
private fun LogoutPromptHost(authViewModel: AuthViewModel, onLoggedOut: suspend () -> Unit) {
    val logoutPrompt by authViewModel.logoutPrompt.collectAsState()
    logoutPrompt?.let { prompt ->
        LogoutUnsentDialog(
            prompt = prompt,
            onSyncAndLogout = { authViewModel.syncAndLogout(onLoggedOut) },
            onAskDiscard = authViewModel::askDiscardConfirmation,
            onDiscard = { authViewModel.discardAndLogout(onLoggedOut) },
            onCancel = authViewModel::cancelLogout,
        )
    }
}

@Composable
private fun rememberPairSession(): PairSession {
    val context = LocalContext.current.applicationContext
    return remember {
        EntryPointAccessors.fromApplication(context, PairSessionEntryPoint::class.java).pairSession()
    }
}

@Composable
private fun rememberBlockingBusy(): BlockingBusy {
    val context = LocalContext.current.applicationContext
    return remember {
        EntryPointAccessors.fromApplication(context, BlockingBusyEntryPoint::class.java).blockingBusy()
    }
}

@Composable
private fun rememberImportController(): ImportController {
    val context = LocalContext.current.applicationContext
    return remember {
        EntryPointAccessors.fromApplication(context, ImportControllerEntryPoint::class.java)
            .importController()
    }
}

@Composable
private fun SlowStartPanel(onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            stringResource(R.string.loading_slow_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            stringResource(R.string.loading_slow_message),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(20.dp))
        Button(onClick = onRetry, shape = AppButtonShape) {
            ButtonLabel(stringResource(R.string.action_retry))
        }
    }
}
