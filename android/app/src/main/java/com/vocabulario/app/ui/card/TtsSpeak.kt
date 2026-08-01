package com.vocabulario.app.ui.card

import android.speech.tts.TextToSpeech

fun TextToSpeech?.speakL2(text: String, utteranceId: String) {
    val trimmed = text.trim()
    if (trimmed.isEmpty()) return
    this?.speak(trimmed, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
}
