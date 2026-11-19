package com.vocabulario.app.ui.auth

import com.vocabulario.app.BuildConfig
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.vocabulario.app.R
import com.vocabulario.app.data.ApiBaseUrl
import com.vocabulario.app.data.session.AuthNotice
import com.vocabulario.app.data.session.AuthNoticeKind
import com.vocabulario.app.data.session.RevocationSummary
import com.vocabulario.app.ui.report.SupportHelpDialog
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppAlertDialog
import com.vocabulario.app.ui.components.AppButtonShape
import com.vocabulario.app.ui.components.AppDialogAction
import com.vocabulario.app.ui.components.AppDialogButtonRow
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
    onAuthenticated: suspend (needsOnboarding: Boolean) -> Unit,
    onRegisterComplete: suspend () -> Unit,
    viewModel: AuthViewModel = hiltViewModel(),
) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
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
    val debugLoginError by viewModel.debugLoginError.collectAsState()
    val unclaimedData by viewModel.unclaimedData.collectAsState()
    val notice by viewModel.notice.collectAsState()
    val revocations by viewModel.revocations.collectAsState()
    val infoMessage by viewModel.infoMessage.collectAsState()
    var confirmSignOut by remember { mutableStateOf(false) }
    var supportOpen by remember { mutableStateOf(false) }
    if (supportOpen) SupportHelpDialog(onDismiss = { supportOpen = false })
    var confirmDiscard by remember { mutableStateOf(false) }
    val forgotPassword by viewModel.forgotPassword.collectAsState()
    val consent by viewModel.consent.collectAsState()
    val googleConsentNeeded by viewModel.googleConsentNeeded.collectAsState()
    LaunchedEffect(isRegister) { if (isRegister) viewModel.loadLegal() }
    if (googleConsentNeeded) {
        GoogleConsentDialog(
            consent = consent,
            onTermsChange = viewModel::setTermsAccepted,
            onAdultChange = viewModel::setAdultConfirmed,
            onRetry = viewModel::loadLegal,
            onDismiss = viewModel::dismissGoogleConsent,
            onConfirm = { viewModel.confirmGoogleConsent(context, onAuthenticated) },
        )
    }
    forgotPassword?.let { state ->
        ForgotPasswordDialog(
            state = state,
            onEmailChange = viewModel::updateForgotPasswordEmail,
            onSend = viewModel::sendForgotPassword,
            onDismiss = viewModel::closeForgotPassword,
        )
    }
    notice?.takeIf { confirmSignOut }?.let { current ->
        SignOutOnDeviceDialog(
            unsentCount = current.unsentCount,
            onDismiss = { confirmSignOut = false },
            onConfirm = {
                confirmSignOut = false
                viewModel.signOutOnDevice(current.unsentFingerprint)
            },
        )
    }
    unclaimedData?.let { unsent ->
        UnclaimedDataDialogs(
            unsentCount = unsent,
            confirmStep = confirmDiscard,
            onDismiss = {
                confirmDiscard = false
                viewModel.dismissUnclaimedData()
            },
            onDiscard = {
                if (unsent > 0 && !confirmDiscard) {
                    confirmDiscard = true
                } else {
                    confirmDiscard = false
                    viewModel.discardUnclaimedData()
                }
            },
        )
    }
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
                if (BuildConfig.DEBUG) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "DEBUG API: ${ApiBaseUrl.resolve()}",
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }
                Spacer(Modifier.height(24.dp))

                notice?.let { current ->
                    SessionNoticeCard(
                        notice = current,
                        onRetry = {
                            hideKeyboard()
                            viewModel.retrySessionRecovery(onAuthenticated)
                        },
                        onSignOut = {
                            hideKeyboard()
                            if (current.hasLocalData) {
                                confirmSignOut = true
                            } else {
                                viewModel.signOutOnDevice(current.unsentFingerprint)
                            }
                        },
                    )
                    Spacer(Modifier.height(20.dp))
                }

                if (revocations.pending > 0 || revocations.unconfirmed > 0) {
                    RevocationStatusCard(
                        summary = revocations,
                        onDismissUnconfirmed = viewModel::dismissUnconfirmedRevocations,
                    )
                    Spacer(Modifier.height(20.dp))
                }

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
                    visualTransformation = if (passwordVisible) {
                        VisualTransformation.None
                    } else {
                        PasswordVisualTransformation()
                    },
                    trailingIcon = {
                        IconButton(
                            onClick = { passwordVisible = !passwordVisible },
                            modifier = Modifier.testTag(TestTags.AUTH_PASSWORD_TOGGLE),
                        ) {
                            Icon(
                                imageVector = if (passwordVisible) {
                                    Icons.Filled.VisibilityOff
                                } else {
                                    Icons.Filled.Visibility
                                },
                                contentDescription = stringResource(
                                    if (passwordVisible) {
                                        R.string.cd_hide_password
                                    } else {
                                        R.string.cd_show_password
                                    },
                                ),
                                tint = scheme.onSurfaceVariant,
                            )
                        }
                    },
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                    containerColor = fieldFill,
                    unfocusedBorderColor = fieldBorder,
                )

                if (!isRegister) {
                    TextButton(
                        onClick = {
                            hideKeyboard()
                            viewModel.openForgotPassword(email)
                        },
                        modifier = Modifier
                            .align(Alignment.End)
                            .testTag(TestTags.AUTH_FORGOT_PASSWORD),
                    ) { Text(stringResource(R.string.auth_forgot_password)) }
                    Spacer(Modifier.height(8.dp))
                } else {
                    Spacer(Modifier.height(10.dp))
                    LegalConsentFields(
                        consent = consent,
                        onTermsChange = { viewModel.setTermsAccepted(it); viewModel.clearError() },
                        onAdultChange = { viewModel.setAdultConfirmed(it); viewModel.clearError() },
                        onRetry = viewModel::loadLegal,
                    )
                    Spacer(Modifier.height(14.dp))
                }

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
                TextButton(
                    onClick = { supportOpen = true },
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                ) { Text(stringResource(R.string.support_title)) }

                errorMessage?.let {
                    Spacer(Modifier.height(12.dp))
                    Text(it, color = scheme.error, textAlign = TextAlign.Center)
                }
                infoMessage?.let {
                    Spacer(Modifier.height(12.dp))
                    Text(it, color = scheme.onSurfaceVariant, textAlign = TextAlign.Center)
                }
                debugLoginError?.let {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}

/** Dane starej instalacji bez właściciela: informacja, potem (gdy są niewysłane zmiany) ponowne potwierdzenie. */
@Composable
private fun UnclaimedDataDialogs(
    unsentCount: Int,
    confirmStep: Boolean,
    onDismiss: () -> Unit,
    onDiscard: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(if (confirmStep) R.string.legacy_data_discard_confirm_title else R.string.legacy_data_title),
        text = {
            Text(
                if (confirmStep) {
                    stringResource(R.string.legacy_data_discard_confirm, unsentCount)
                } else {
                    stringResource(R.string.legacy_data_message, unsentCount)
                },
            )
        },
        warning = true,
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryKind = AppDialogAction.Neutral,
                primaryText = stringResource(R.string.legacy_data_discard),
                onPrimary = onDiscard,
                primaryKind = AppDialogAction.Destroy,
            )
        },
    )
}

/** Odwołanie sesji na serwerze: oczekuje na sieć albo zakończyło się bez potwierdzenia. */
@Composable
private fun RevocationStatusCard(
    summary: RevocationSummary,
    onDismissUnconfirmed: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = scheme.surfaceVariant,
        contentColor = scheme.onSurfaceVariant,
    ) {
        Column(Modifier.padding(16.dp)) {
            if (summary.pending > 0) {
                Text(stringResource(R.string.auth_revocation_pending), style = MaterialTheme.typography.bodyMedium)
            }
            if (summary.unconfirmed > 0) {
                if (summary.pending > 0) Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(R.string.auth_revocation_unconfirmed, summary.unconfirmed),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = onDismissUnconfirmed,
                    modifier = Modifier.fillMaxWidth(),
                    shape = AppButtonShape,
                ) {
                    ButtonLabel(stringResource(R.string.action_ok))
                }
            }
        }
    }
}

/** Sesja wymagająca ponownego loginu/odzyskania albo pozostawione dane konta: wyjaśnienie i jawne wyjścia. */
@Composable
private fun SessionNoticeCard(
    notice: AuthNotice,
    onRetry: () -> Unit,
    onSignOut: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val (titleRes, messageRes) = when (notice.kind) {
        AuthNoticeKind.REAUTH -> R.string.auth_notice_reauth_title to R.string.auth_notice_reauth
        AuthNoticeKind.RECOVERY -> R.string.auth_notice_recovery_title to R.string.auth_notice_recovery
        AuthNoticeKind.LOCAL_DATA -> R.string.auth_notice_local_data_title to R.string.auth_notice_local_data
    }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = scheme.surfaceVariant,
        contentColor = scheme.onSurfaceVariant,
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(
                stringResource(titleRes),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = scheme.onSurface,
            )
            Spacer(Modifier.height(6.dp))
            Text(stringResource(messageRes), style = MaterialTheme.typography.bodyMedium)
            if (notice.unsentCount > 0) {
                Spacer(Modifier.height(6.dp))
                Text(
                    stringResource(R.string.auth_notice_unsent, notice.unsentCount),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Spacer(Modifier.height(12.dp))
            if (notice.kind == AuthNoticeKind.RECOVERY) {
                Button(
                    onClick = onRetry,
                    modifier = Modifier.fillMaxWidth(),
                    shape = AppButtonShape,
                ) {
                    ButtonLabel(stringResource(R.string.action_retry))
                }
                Spacer(Modifier.height(8.dp))
            }
            OutlinedButton(
                onClick = onSignOut,
                modifier = Modifier.fillMaxWidth(),
                shape = AppButtonShape,
                colors = ButtonDefaults.outlinedButtonColors(contentColor = scheme.error),
            ) {
                ButtonLabel(stringResource(R.string.auth_sign_out_device))
            }
        }
    }
}

@Composable
private fun GoogleConsentDialog(
    consent: LegalConsentState,
    onTermsChange: (Boolean) -> Unit,
    onAdultChange: (Boolean) -> Unit,
    onRetry: () -> Unit,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.legal_google_title),
        text = {
            Column {
                Text(stringResource(R.string.legal_google_body))
                Spacer(Modifier.height(8.dp))
                LegalConsentFields(consent, onTermsChange, onAdultChange, onRetry)
            }
        },
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryKind = AppDialogAction.Neutral,
                primaryText = stringResource(R.string.legal_continue),
                onPrimary = onConfirm,
                primaryEnabled = consent.manifest != null && consent.termsAccepted && consent.adultConfirmed,
            )
        },
    )
}

@Composable
private fun ForgotPasswordDialog(
    state: ForgotPasswordState,
    onEmailChange: (String) -> Unit,
    onSend: () -> Unit,
    onDismiss: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.auth_forgot_password_title),
        text = {
            Column {
                if (state.sent) {
                    Text(stringResource(R.string.auth_forgot_password_sent, state.email.trim()))
                    Spacer(Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.auth_forgot_password_google_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    Text(stringResource(R.string.auth_forgot_password_body))
                    Spacer(Modifier.height(12.dp))
                    AppGrayField(
                        value = state.email,
                        onValueChange = onEmailChange,
                        placeholder = stringResource(R.string.auth_email),
                        singleLine = true,
                        isError = state.error != null,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Email,
                            imeAction = ImeAction.Send,
                        ),
                        keyboardActions = KeyboardActions(onSend = { onSend() }),
                    )
                    state.error?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        },
        buttons = {
            if (state.sent) {
                AppDialogButtonRow(primaryText = stringResource(R.string.action_ok), onPrimary = onDismiss)
            } else {
                AppDialogButtonRow(
                    secondaryText = stringResource(R.string.action_cancel),
                    onSecondary = onDismiss,
                    secondaryKind = AppDialogAction.Neutral,
                    primaryText = stringResource(R.string.auth_forgot_password_send),
                    onPrimary = onSend,
                    primaryEnabled = !state.sending,
                )
            }
        },
    )
}

@Composable
private fun SignOutOnDeviceDialog(
    unsentCount: Int,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AppAlertDialog(
        onDismissRequest = onDismiss,
        title = stringResource(R.string.auth_sign_out_device_confirm_title),
        text = {
            Column {
                Text(stringResource(R.string.auth_sign_out_device_confirm))
                if (unsentCount > 0) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.auth_notice_unsent, unsentCount),
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        },
        warning = true,
        buttons = {
            AppDialogButtonRow(
                secondaryText = stringResource(R.string.action_cancel),
                onSecondary = onDismiss,
                secondaryKind = AppDialogAction.Neutral,
                primaryText = stringResource(R.string.auth_sign_out_device),
                onPrimary = onConfirm,
                primaryKind = AppDialogAction.Destroy,
            )
        },
    )
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
