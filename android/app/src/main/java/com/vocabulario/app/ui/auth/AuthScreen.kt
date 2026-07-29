package com.vocabulario.app.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppCard

@Composable
fun AuthScreen(
    onAuthenticated: (needsOnboarding: Boolean) -> Unit,
    onRegisterComplete: () -> Unit,
    viewModel: AuthViewModel = hiltViewModel(),
) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isRegister by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val errorMessage by viewModel.errorMessage.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            if (isRegister) "Załóż konto" else "Witaj z powrotem",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "Ucz się słówek w swoim tempie",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(32.dp))

        AppCard {
            Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it; viewModel.clearError() },
                    placeholder = { Text("Email") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    shape = AppButtonShape,
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it; viewModel.clearError() },
                    placeholder = { Text("Hasło") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    shape = AppButtonShape,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    colors = OutlinedTextFieldDefaults.colors(
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
                )
                if (isRegister) {
                    Text("Minimum 8 znaków", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        Spacer(Modifier.height(20.dp))

        Button(
            onClick = {
                if (isRegister) viewModel.register(email, password, onRegisterComplete)
                else viewModel.login(email, password, onAuthenticated)
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = AppButtonShape,
        ) { Text(if (isRegister) "Zarejestruj" else "Zaloguj", style = MaterialTheme.typography.titleMedium) }

        Spacer(Modifier.height(10.dp))
        OutlinedButton(
            onClick = { viewModel.googleSignIn(context, onAuthenticated) },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = AppButtonShape,
        ) { Text("Kontynuuj z Google") }

        Spacer(Modifier.height(10.dp))
        OutlinedButton(onClick = { isRegister = !isRegister }, shape = AppButtonShape) {
            Text(if (isRegister) "Mam już konto" else "Załóż konto")
        }

        errorMessage?.let {
            Spacer(Modifier.height(16.dp))
            Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
        }
    }
}
