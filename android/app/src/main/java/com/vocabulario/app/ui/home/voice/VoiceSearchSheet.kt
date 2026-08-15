package com.vocabulario.app.ui.home.voice

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import com.vocabulario.app.R
import com.vocabulario.app.data.api.LookupCandidate
import com.vocabulario.app.ui.TestTags
import com.vocabulario.app.ui.components.AppDialogShape
import com.vocabulario.app.ui.components.AppDialogWindowChrome
import com.vocabulario.app.ui.components.LemmaActionRow
import com.vocabulario.app.ui.components.LemmaAddButton
import java.util.Locale

@Composable
fun VoiceSearchSheet(
    visible: Boolean,
    nativeLang: String,
    learningLang: String,
    candidates: List<LookupCandidate>,
    loading: Boolean,
    searchError: String?,
    onDismiss: () -> Unit,
    onResult: (String) -> Unit,
    onAdd: (LookupCandidate) -> Unit,
) {
    if (!visible) return

    val context = LocalContext.current
    val scheme = MaterialTheme.colorScheme
    var partial by remember { mutableStateOf("") }
    var heardText by remember { mutableStateOf<String?>(null) }
    var listening by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var startAfterPermission by remember { mutableStateOf(false) }
    var pendingListenNative by remember { mutableStateOf(false) }
    var nativeFallbackPending by remember { mutableStateOf(false) }
    val speechAvailable = remember { SpeechRecognizer.isRecognitionAvailable(context) }

    val recognizer = remember {
        if (speechAvailable) SpeechRecognizer.createSpeechRecognizer(context) else null
    }

    fun stopListening() {
        runCatching { recognizer?.stopListening() }
        listening = false
    }

    fun dismiss() {
        stopListening()
        onDismiss()
    }

    fun buildIntent(useNativeLang: Boolean): Intent {
        val learningTag = Locale.forLanguageTag(learningLang).toLanguageTag()
        val nativeTag = Locale.forLanguageTag(nativeLang).toLanguageTag()
        val primaryTag = if (useNativeLang) nativeTag else learningTag
        return Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, primaryTag)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            if (!useNativeLang && Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE && learningTag != nativeTag) {
                putExtra("android.speech.extra.ADDITIONAL_LANGUAGES", arrayListOf(nativeTag))
            }
        }
    }

    fun beginListening(useNativeLang: Boolean) {
        partial = ""
        error = null
        nativeFallbackPending = useNativeLang
        recognizer?.startListening(buildIntent(useNativeLang))
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted && startAfterPermission) {
            startAfterPermission = false
            beginListening(pendingListenNative)
        } else if (!granted) {
            startAfterPermission = false
            error = context.getString(R.string.voice_permission_denied)
            listening = false
        }
    }

    fun startListening(useNativeLang: Boolean = false) {
        if (!speechAvailable || recognizer == null) {
            error = context.getString(R.string.voice_unavailable)
            return
        }
        val granted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            startAfterPermission = true
            pendingListenNative = useNativeLang
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        beginListening(useNativeLang)
    }

    fun maybeRetryWithNativeLang() {
        if (nativeFallbackPending || learningLang == nativeLang || Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            return
        }
        nativeFallbackPending = true
        startListening(useNativeLang = true)
    }

    DisposableEffect(recognizer) {
        recognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) {
                listening = true
                error = null
            }

            override fun onBeginningOfSpeech() = Unit
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit

            override fun onEndOfSpeech() {
                listening = false
            }

            override fun onError(code: Int) {
                listening = false
                when (code) {
                    SpeechRecognizer.ERROR_NO_MATCH,
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT,
                    -> {
                        if (!nativeFallbackPending) {
                            maybeRetryWithNativeLang()
                            if (!nativeFallbackPending) {
                                error = context.getString(R.string.voice_no_match)
                            }
                        } else {
                            error = context.getString(R.string.voice_no_match)
                        }
                    }
                    SpeechRecognizer.ERROR_NETWORK,
                    SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
                    -> error = context.getString(R.string.voice_network_required)
                    else -> error = context.getString(R.string.voice_unavailable)
                }
            }

            override fun onResults(results: Bundle?) {
                listening = false
                val text = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                    ?.trim()
                if (text.isNullOrBlank()) {
                    if (!nativeFallbackPending) {
                        maybeRetryWithNativeLang()
                    } else {
                        error = context.getString(R.string.voice_no_match)
                    }
                    return
                }
                heardText = text
                partial = text
                onResult(text)
            }

            override fun onPartialResults(partialResults: Bundle?) {
                partial = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                    .orEmpty()
            }

            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })
        onDispose {
            recognizer?.destroy()
        }
    }

    LaunchedEffect(visible) {
        if (!visible) return@LaunchedEffect
        heardText = null
        partial = ""
        error = null
        nativeFallbackPending = false
        kotlinx.coroutines.delay(120)
        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.RECORD_AUDIO,
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            startListening(false)
        } else {
            startAfterPermission = true
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    val pulseTransition = rememberInfiniteTransition(label = "voice_mic_pulse")
    val micScale by pulseTransition.animateFloat(
        initialValue = 1f,
        targetValue = if (listening) 1.12f else 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(700),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "mic_scale",
    )

    Dialog(
        onDismissRequest = { dismiss() },
        properties = DialogProperties(
            dismissOnBackPress = true,
            dismissOnClickOutside = true,
            usePlatformDefaultWidth = false,
        ),
    ) {
        AppDialogWindowChrome(dimAlpha = 0.52f)
        Box(
            modifier = Modifier
                .fillMaxSize()
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = { dismiss() },
                )
                .testTag(TestTags.SHEET_VOICE_SEARCH),
            contentAlignment = Alignment.Center,
        ) {
            Surface(
                modifier = Modifier
                    .padding(horizontal = 24.dp)
                    .fillMaxWidth()
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                        onClick = {},
                    ),
                shape = AppDialogShape,
                color = scheme.surface,
                tonalElevation = 6.dp,
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            stringResource(R.string.voice_listening),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.weight(1f),
                        )
                        IconButton(
                            onClick = { dismiss() },
                            modifier = Modifier
                                .size(36.dp)
                                .testTag(TestTags.BTN_VOICE_SEARCH),
                        ) {
                            Icon(
                                Icons.Default.Close,
                                contentDescription = stringResource(R.string.action_close),
                            )
                        }
                    }

                    Spacer(Modifier.height(8.dp))

                    Box(
                        modifier = Modifier
                            .size(72.dp)
                            .scale(if (listening) micScale else 1f),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            Icons.Default.Mic,
                            contentDescription = null,
                            modifier = Modifier.size(40.dp),
                            tint = if (listening) scheme.primary else scheme.onSurfaceVariant,
                        )
                    }

                    Spacer(Modifier.height(12.dp))

                    Text(
                        when {
                            partial.isNotBlank() -> partial
                            listening -> stringResource(R.string.voice_listening_hint)
                            heardText != null -> heardText.orEmpty()
                            else -> stringResource(R.string.voice_either_lang_hint)
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = scheme.onSurface,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth(),
                    )

                    error?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = scheme.error, textAlign = TextAlign.Center)
                    }

                    searchError?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = scheme.error, textAlign = TextAlign.Center)
                    }

                    if (loading || heardText != null) {
                        Spacer(Modifier.height(16.dp))
                    }

                    if (loading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(28.dp),
                            strokeWidth = 3.dp,
                            color = scheme.primary,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            stringResource(R.string.voice_searching),
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurfaceVariant,
                        )
                    }

                    if (candidates.isNotEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 280.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            items(candidates, key = { it.lemma + it.gloss }) { candidate ->
                                VoiceCandidateRow(
                                    candidate = candidate,
                                    onAdd = {
                                        onAdd(candidate)
                                        dismiss()
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun VoiceCandidateRow(
    candidate: LookupCandidate,
    onAdd: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    LemmaActionRow(
        lemma = candidate.lemma,
        gloss = candidate.gloss,
        trailing = {
            when {
                candidate.isCreating -> {
                    CircularProgressIndicator(
                        modifier = Modifier.size(28.dp),
                        strokeWidth = 3.dp,
                        color = scheme.primary,
                    )
                }
                candidate.onList -> {
                    Icon(
                        Icons.Default.CheckCircle,
                        contentDescription = null,
                        tint = scheme.primary,
                        modifier = Modifier.size(26.dp),
                    )
                }
                else -> {
                    LemmaAddButton(
                        onClick = onAdd,
                        contentDescription = stringResource(R.string.action_add),
                    )
                }
            }
        },
    )
}
