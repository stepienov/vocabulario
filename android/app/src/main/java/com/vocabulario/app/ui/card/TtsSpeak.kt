package com.vocabulario.app.ui.card

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/** Speaks L2 text once the engine is ready (queues the first tap if needed). */
class L2TtsSpeaker {
    private val engine = AtomicReference<TextToSpeech?>(null)
    private val ready = AtomicBoolean(false)
    private val pending = AtomicReference<Pair<String, String>?>(null)

    fun attach(tts: TextToSpeech?) {
        engine.set(tts)
    }

    fun markReady(ok: Boolean) {
        ready.set(ok)
        if (!ok) return
        val next = pending.getAndSet(null) ?: return
        speakNow(next.first, next.second)
    }

    fun speak(text: String, utteranceId: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        if (!ready.get() || engine.get() == null) {
            pending.set(trimmed to utteranceId)
            return
        }
        speakNow(trimmed, utteranceId)
    }

    private fun speakNow(text: String, utteranceId: String) {
        val tts = engine.get() ?: return
        // Flush previous utterance so repeated taps always restart cleanly.
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
    }

    fun shutdown() {
        ready.set(false)
        pending.set(null)
        engine.getAndSet(null)?.run {
            stop()
            shutdown()
        }
    }
}

@Composable
fun rememberL2Tts(languageTag: String): L2TtsSpeaker {
    val context = LocalContext.current
    val speaker = remember { L2TtsSpeaker() }
    DisposableEffect(context, languageTag) {
        var engine: TextToSpeech? = null
        engine = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val locale = Locale.forLanguageTag(languageTag)
                val result = engine?.setLanguage(locale)
                val ok = result != TextToSpeech.LANG_MISSING_DATA &&
                    result != TextToSpeech.LANG_NOT_SUPPORTED
                if (!ok) {
                    // Fallback: try primary language only (e.g. pl from pl-PL).
                    engine?.language = Locale(locale.language)
                }
                speaker.attach(engine)
                speaker.markReady(true)
            } else {
                speaker.markReady(false)
            }
        }
        speaker.attach(engine)
        // Progress listener keeps engine warm; errors are ignored.
        engine?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit
            override fun onDone(utteranceId: String?) = Unit
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) = Unit
        })
        onDispose { speaker.shutdown() }
    }
    return speaker
}

fun TextToSpeech?.speakL2(text: String, utteranceId: String) {
    val trimmed = text.trim()
    if (trimmed.isEmpty()) return
    this?.speak(trimmed, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
}
