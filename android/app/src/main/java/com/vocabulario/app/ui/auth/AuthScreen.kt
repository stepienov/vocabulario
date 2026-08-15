package com.vocabulario.app.ui.auth

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppGrayField
import com.vocabulario.app.ui.components.BrandLogo
import com.vocabulario.app.ui.components.ButtonLabel
import com.vocabulario.app.ui.theme.BrandBlueLight
import com.vocabulario.app.ui.theme.BrandTeal

private val GoogleButtonShape = RoundedCornerShape(8.dp)
private val GoogleBlue = Color(0xFF1A73E8)
private val GoogleButtonBorderLight = Color(0xFFDADCE0)
private val GoogleButtonFillDark = Color(0xFF131314)
private val GoogleButtonBorderDark = Color(0xFF8E918F)
private val AuthFieldBorderLight = Color(0xFFD0D7DE)
private val DividerLineLight = Color(0xFFD0D7DE)
private val DividerTextLight = Color(0xFF57606A)

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
    val keyboard = LocalSoftwareKeyboardController.current
    val focusManager = LocalFocusManager.current
    fun hideKeyboard() {
        keyboard?.hide()
        focusManager.clearFocus()
    }
    val submit = {
        hideKeyboard()
        if (isRegister) viewModel.register(email, password, onRegisterComplete)
        else viewModel.login(email, password, onAuthenticated)
    }
    val errorMessage by viewModel.errorMessage.collectAsState()
    val scheme = MaterialTheme.colorScheme
    val dark = scheme.background.luminance() < 0.5f
    val fieldFill = if (dark) scheme.surfaceVariant else Color.White
    val fieldBorder = if (dark) Color.Transparent else AuthFieldBorderLight

    var entered by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { entered = true }
    val heroAlpha by animateFloatAsState(
        targetValue = if (entered) 1f else 0f,
        animationSpec = tween(700, easing = FastOutSlowInEasing),
        label = "authHero",
    )
    val formAlpha by animateFloatAsState(
        targetValue = if (entered) 1f else 0f,
        animationSpec = tween(700, delayMillis = 160, easing = FastOutSlowInEasing),
        label = "authForm",
    )

    val gradient = if (dark) {
        Brush.verticalGradient(
            colorStops = arrayOf(
                0.0f to Color(0xFF0A1E33),
                0.45f to scheme.background,
                1.0f to scheme.background,
            ),
        )
    } else {
        Brush.verticalGradient(
            colorStops = arrayOf(
                0.0f to BrandBlueLight.copy(alpha = 0.22f),
                0.35f to BrandTeal.copy(alpha = 0.10f),
                0.7f to scheme.background,
                1.0f to scheme.background,
            ),
        )
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(scheme.background)
            .background(gradient),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .padding(top = 36.dp, bottom = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .alpha(heroAlpha),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                BrandLogo(height = 52.dp, maxWidth = 320.dp)
            }

            Spacer(Modifier.height(36.dp))

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .alpha(formAlpha),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    if (isRegister) {
                        stringResource(R.string.auth_register_title)
                    } else {
                        stringResource(R.string.auth_login_title)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 40.dp),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                    color = scheme.onBackground,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(24.dp))

                GoogleSignInButton(
                    onClick = {
                        hideKeyboard()
                        viewModel.googleSignIn(context, onAuthenticated)
                    },
                    dark = dark,
                )

                Spacer(Modifier.height(20.dp))
                OrContinueDivider(dark = dark)
                Spacer(Modifier.height(20.dp))

                AppGrayField(
                    value = email,
                    onValueChange = { email = it; viewModel.clearError() },
                    placeholder = stringResource(R.string.auth_email),
                    modifier = Modifier.testTag(TestTags.AUTH_EMAIL),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Email,
                        imeAction = ImeAction.Next,
                    ),
                    containerColor = fieldFill,
                    unfocusedBorderColor = fieldBorder,
                )
                Spacer(Modifier.height(12.dp))
                AppGrayField(
                    value = password,
                    onValueChange = { password = it; viewModel.clearError() },
                    placeholder = stringResource(R.string.auth_password),
                    modifier = Modifier.testTag(TestTags.AUTH_PASSWORD),
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                    containerColor = fieldFill,
                    unfocusedBorderColor = fieldBorder,
                )

                Spacer(Modifier.height(22.dp))

                Button(
                    onClick = submit,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp)
                        .testTag(TestTags.AUTH_SUBMIT),
                    shape = AppButtonShape,
                ) {
                    ButtonLabel(
                        if (isRegister) {
                            stringResource(R.string.auth_register)
                        } else {
                            stringResource(R.string.auth_login)
                        },
                        style = MaterialTheme.typography.titleMedium,
                    )
                }

                Spacer(Modifier.height(10.dp))
                OutlinedButton(
                    onClick = {
                        hideKeyboard()
                        isRegister = !isRegister
                        viewModel.clearError()
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp)
                        .testTag(TestTags.AUTH_TOGGLE_MODE),
                    shape = AppButtonShape,
                ) {
                    ButtonLabel(
                        if (isRegister) {
                            stringResource(R.string.auth_have_account)
                        } else {
                            stringResource(R.string.auth_register_title)
                        },
                        style = MaterialTheme.typography.titleMedium,
                    )
                }

                errorMessage?.let {
                    Spacer(Modifier.height(12.dp))
                    Text(it, color = scheme.error, textAlign = TextAlign.Center)
                }
            }
        }
    }
}

@Composable
private fun GoogleSignInButton(onClick: () -> Unit, dark: Boolean) {
    Button(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp)
            .testTag(TestTags.AUTH_GOOGLE),
        shape = GoogleButtonShape,
        colors = ButtonDefaults.buttonColors(
            containerColor = if (dark) GoogleButtonFillDark else Color.White,
            contentColor = if (dark) Color(0xFFE3E3E3) else GoogleBlue,
        ),
        border = BorderStroke(1.dp, if (dark) GoogleButtonBorderDark else GoogleButtonBorderLight),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 1.dp, pressedElevation = 0.dp),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Image(
                painter = painterResource(R.drawable.ic_google_g),
                contentDescription = null,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(12.dp))
            Text(
                stringResource(R.string.auth_google),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun OrContinueDivider(dark: Boolean) {
    val line = if (dark) MaterialTheme.colorScheme.outline else DividerLineLight
    val text = if (dark) MaterialTheme.colorScheme.onSurfaceVariant else DividerTextLight
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        HorizontalDivider(modifier = Modifier.weight(1f), color = line)
        Text(
            stringResource(R.string.auth_or_continue),
            modifier = Modifier
                .padding(horizontal = 10.dp)
                .weight(1f, fill = false),
            style = MaterialTheme.typography.bodySmall,
            color = text,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        HorizontalDivider(modifier = Modifier.weight(1f), color = line)
    }
}
