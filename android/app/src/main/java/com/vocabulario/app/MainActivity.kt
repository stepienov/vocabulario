package com.vocabulario.app

import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.ui.VocabularioAppRoot
import com.vocabulario.app.ui.theme.VocabularioTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : AppCompatActivity() {
    @Inject lateinit var tokenStore: TokenStore

    @OptIn(ExperimentalComposeUiApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val theme by tokenStore.theme.collectAsState(initial = "system")
            VocabularioTheme(themeMode = theme) {
                Box(
                    modifier = Modifier.semantics { testTagsAsResourceId = true },
                ) {
                    VocabularioAppRoot()
                }
            }
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        // Locale switches without Activity recreate (android:configChanges) —
        // avoids the black flash; Compose picks up LocalConfiguration.
        super.onConfigurationChanged(newConfig)
    }
}
