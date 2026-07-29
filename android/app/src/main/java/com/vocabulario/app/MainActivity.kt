package com.vocabulario.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.ui.VocabularioAppRoot
import com.vocabulario.app.ui.theme.VocabularioTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    @Inject lateinit var tokenStore: TokenStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val theme by tokenStore.theme.collectAsState(initial = "system")
            VocabularioTheme(themeMode = theme) {
                VocabularioAppRoot()
            }
        }
    }
}
