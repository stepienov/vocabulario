package com.vocabulario.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import android.net.Uri
import com.vocabulario.app.data.PairSession
import com.vocabulario.app.data.imports.ImportController
import com.vocabulario.app.ui.auth.AuthScreen
import com.vocabulario.app.ui.auth.AuthViewModel
import com.vocabulario.app.ui.components.PairSwitchHost
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
interface ImportControllerEntryPoint {
    fun importController(): ImportController
}

@Composable
fun VocabularioAppRoot(
    appViewModel: AppViewModel = hiltViewModel(),
    authViewModel: AuthViewModel = hiltViewModel(),
) {
    val startRoute by appViewModel.startRoute.collectAsState()
    val pairSession = rememberPairSession()
    rememberImportController()
    val pairBusy by pairSession.busy.collectAsState()

    LaunchedEffect(Unit) { appViewModel.bootstrap() }

    if (startRoute == AppStartRoute.LOADING) {
        Box(
            Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background),
            contentAlignment = Alignment.Center,
        ) {
            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
        }
        return
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
    ) {
        PairSwitchHost(busy = pairBusy) {
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
                    AppStartRoute.ONBOARDING -> Routes.ONBOARDING
                    AppStartRoute.HOME -> Routes.HOME
                    AppStartRoute.LOADING -> Routes.AUTH
                }

                NavHost(navController = navController, startDestination = graphStart) {
                    composable(Routes.AUTH) {
                        AuthScreen(
                            onAuthenticated = { needsOnboarding ->
                                appViewModel.onAuthenticated(needsOnboarding)
                            },
                            onRegisterComplete = {
                                appViewModel.onAuthenticated(needsOnboarding = true)
                            },
                        )
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
                        SettingsScreen(
                            onBack = { navController.popBackStack() },
                            onLogout = {
                                authViewModel.logout {
                                    appViewModel.onLogout()
                                }
                            },
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
private fun rememberImportController(): ImportController {
    val context = LocalContext.current.applicationContext
    return remember {
        EntryPointAccessors.fromApplication(context, ImportControllerEntryPoint::class.java)
            .importController()
    }
}
