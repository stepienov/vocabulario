package com.vocabulario.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.vocabulario.app.ui.auth.AuthScreen
import com.vocabulario.app.ui.auth.AuthViewModel
import com.vocabulario.app.ui.favorites.FavoritesScreen
import com.vocabulario.app.ui.home.HomeScreen
import com.vocabulario.app.ui.learning.LearningScreen
import com.vocabulario.app.ui.onboarding.OnboardingScreen
import com.vocabulario.app.ui.packs.PacksScreen
import com.vocabulario.app.ui.practice.PracticeScreen
import com.vocabulario.app.ui.profile.ProfileScreen
import com.vocabulario.app.ui.settings.SettingsScreen

object Routes {
    const val AUTH = "auth"
    const val ONBOARDING = "onboarding"
    const val HOME = "home"
    const val PRACTICE = "practice"
    const val SETTINGS = "settings"
    const val PROFILE = "profile"
    const val FAVORITES = "favorites"
    const val LEARNING = "learning"
    const val PACKS = "packs"
}

@Composable
fun VocabularioAppRoot(
    appViewModel: AppViewModel = hiltViewModel(),
    authViewModel: AuthViewModel = hiltViewModel(),
) {
    val startRoute by appViewModel.startRoute.collectAsState()
    val navController = rememberNavController()

    LaunchedEffect(Unit) { appViewModel.bootstrap() }

    if (startRoute == AppStartRoute.LOADING) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                CircularProgressIndicator()
                Spacer(Modifier.height(16.dp))
                Text("Ładowanie…", style = MaterialTheme.typography.bodyLarge)
            }
        }
        return
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
                    val dest = if (needsOnboarding) Routes.ONBOARDING else Routes.HOME
                    navController.navigate(dest) {
                        popUpTo(Routes.AUTH) { inclusive = true }
                    }
                },
                onRegisterComplete = {
                    appViewModel.onAuthenticated(needsOnboarding = true)
                    navController.navigate(Routes.ONBOARDING) {
                        popUpTo(Routes.AUTH) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.ONBOARDING) {
            OnboardingScreen(
                onComplete = {
                    appViewModel.onOnboardingComplete()
                    navController.navigate(Routes.HOME) {
                        popUpTo(Routes.ONBOARDING) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.HOME) {
            HomeScreen(
                onPractice = { navController.navigate(Routes.PRACTICE) },
                onFavorites = { navController.navigate(Routes.FAVORITES) },
                onLearning = { navController.navigate(Routes.LEARNING) },
                onPacks = { navController.navigate(Routes.PACKS) },
                onSettings = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.PRACTICE) {
            PracticeScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onLogout = {
                    authViewModel.logout {
                        appViewModel.onLogout()
                        navController.navigate(Routes.AUTH) {
                            popUpTo(Routes.HOME) { inclusive = true }
                        }
                    }
                },
            )
        }
        composable(Routes.PROFILE) {
            ProfileScreen(
                onBack = { navController.popBackStack() },
                onAddProfile = {
                    navController.navigate(Routes.ONBOARDING)
                },
            )
        }
        composable(Routes.FAVORITES) {
            FavoritesScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.LEARNING) {
            LearningScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.PACKS) {
            PacksScreen(onBack = { navController.popBackStack() })
        }
    }
}
