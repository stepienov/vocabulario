package com.vocabulario.app

import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.viewModels
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.vocabulario.app.data.AccountLink
import com.vocabulario.app.data.AccountLinkKind
import com.vocabulario.app.data.parseAccountLink
import com.vocabulario.app.ui.theme.VocabularioTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

class AccountLinkState(
    private val submitLink: suspend (AccountLink, String) -> Int? = { link, password ->
        linkService.submit(link, password)
    },
) : ViewModel() {
    var link by mutableStateOf<AccountLink?>(null)
        private set
    var busy by mutableStateOf(false)
        private set
    var done by mutableStateOf(false)
        private set
    var error by mutableStateOf<Int?>(null)
        private set

    fun receive(link: AccountLink?) {
        this.link = link
        busy = false
        done = false
        error = if (link == null) R.string.account_link_missing_token else null
    }

    fun submit(password: String, repeat: String) {
        val currentLink = link ?: return
        if (busy || done) return
        val length = password.codePointCount(0, password.length)
        error = when {
            currentLink.kind == AccountLinkKind.RESET && length < 15 -> R.string.err_new_password_short
            currentLink.kind == AccountLinkKind.RESET && length > 128 -> R.string.err_password_too_long
            currentLink.kind == AccountLinkKind.RESET && password != repeat -> R.string.err_passwords_mismatch
            else -> null
        }
        if (error != null) return
        busy = true
        viewModelScope.launch {
            val result = submitLink(currentLink, password)
            if (link !== currentLink) return@launch
            busy = false
            error = result
            done = result == null
        }
    }
}

class AccountLinkActivity : AppCompatActivity() {
    private val linkState: AccountLinkState by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        enableEdgeToEdge()
        if (savedInstanceState == null || intent?.data != null) receiveLink(intent)
        setContent {
            VocabularioTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    key(linkState.link) {
                        AccountLinkScreen(state = linkState, onClose = ::finish)
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        receiveLink(intent)
        setIntent(intent)
    }

    private fun receiveLink(intent: Intent?) {
        linkState.receive(if (intent?.action == Intent.ACTION_VIEW) parseAccountLink(intent.dataString) else null)
        intent?.data = null
    }
}

private val linkClient = OkHttpClient.Builder()
    .followRedirects(false)
    .followSslRedirects(false)
    .retryOnConnectionFailure(false)
    .callTimeout(20, TimeUnit.SECONDS)
    .build()

internal fun accountLinkResult(status: Int, code: String?): Int? = when {
    status == 200 -> null
    code == "password_too_short" -> R.string.err_new_password_short
    code == "password_too_long" -> R.string.err_password_too_long
    code == "password_invalid_unicode" -> R.string.err_password_invalid_chars
    status == 400 || status == 422 -> R.string.account_link_invalid
    status == 409 -> R.string.account_link_used
    status == 410 -> R.string.account_link_expired
    status == 429 -> R.string.account_link_rate_limited
    else -> R.string.account_link_error
}

internal class AccountLinkService(
    private val baseUrl: HttpUrl,
    private val client: OkHttpClient,
) {
    suspend fun submit(link: AccountLink, password: String): Int? = withContext(Dispatchers.IO) {
        val endpoint = when (link.kind) {
            AccountLinkKind.VERIFY -> "email-verification/confirm"
            AccountLinkKind.RESET -> "password-reset/confirm"
        }
        val payload = buildJsonObject {
            put("token", link.token)
            if (link.kind == AccountLinkKind.RESET) put("new_password", password)
        }.toString()
        val request = Request.Builder()
            .url(baseUrl.newBuilder().addPathSegments(endpoint).build())
            .post(payload.toRequestBody("application/json".toMediaType()))
            .build()
        try {
            client.newCall(request).execute().use { response ->
                val code = if (response.isSuccessful) null else {
                    try {
                        val body = response.peekBody(8192).string()
                        val root = Json.parseToJsonElement(body) as? JsonObject
                        val detail = root?.get("detail") as? JsonObject
                        (detail?.get("code") as? JsonPrimitive)?.content
                    } catch (_: IllegalArgumentException) {
                        null
                    }
                }
                accountLinkResult(response.code, code)
            }
        } catch (_: IOException) {
            R.string.account_link_network
        }
    }
}

private val linkService = AccountLinkService(
    "https://vocabulario.io/api/v1/auth/".toHttpUrl(),
    linkClient,
)

@Composable
private fun AccountLinkScreen(state: AccountLinkState, onClose: () -> Unit) {
    val link = state.link
    val busy = state.busy
    val done = state.done
    val error = state.error
    var password by remember { mutableStateOf("") }
    var repeat by remember { mutableStateOf("") }
    LaunchedEffect(done) {
        if (done) {
            password = ""
            repeat = ""
        }
    }
    val title = when (link?.kind) {
        AccountLinkKind.VERIFY -> R.string.account_link_verify_title
        AccountLinkKind.RESET -> R.string.account_link_reset_title
        null -> R.string.account_link_invalid
    }
    val intro = when (link?.kind) {
        AccountLinkKind.VERIFY -> R.string.account_link_verify_intro
        AccountLinkKind.RESET -> R.string.account_link_reset_intro
        null -> null
    }
    val button = when (link?.kind) {
        AccountLinkKind.VERIFY -> R.string.account_link_verify_button
        AccountLinkKind.RESET -> R.string.account_link_reset_button
        null -> null
    }
    val success = when (link?.kind) {
        AccountLinkKind.VERIFY -> R.string.account_link_verify_done
        AccountLinkKind.RESET -> R.string.account_link_reset_done
        null -> null
    }
    Column(
        modifier = Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()
            .verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(stringResource(title), style = MaterialTheme.typography.headlineSmall)
        if (done && success != null) {
            Text(stringResource(success))
        } else {
            if (intro != null) Text(stringResource(intro))
            if (link?.kind == AccountLinkKind.RESET) {
                OutlinedTextField(
                    value = password, onValueChange = { password = it }, enabled = !busy,
                    label = { Text(stringResource(R.string.account_new_password)) },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
                OutlinedTextField(
                    value = repeat, onValueChange = { repeat = it }, enabled = !busy,
                    label = { Text(stringResource(R.string.account_repeat_password)) },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(), singleLine = true,
                )
            }
            error?.let { Text(stringResource(it), color = MaterialTheme.colorScheme.error) }
            if (link != null && button != null) {
                Button(
                    enabled = !busy,
                    onClick = { state.submit(password, repeat) },
                ) { Text(stringResource(button)) }
            }
        }
        TextButton(onClick = onClose, enabled = !busy) {
            Text(stringResource(R.string.action_close))
        }
    }
}
