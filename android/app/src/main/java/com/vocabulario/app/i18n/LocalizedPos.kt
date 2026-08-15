package com.vocabulario.app.i18n

import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.vocabulario.app.R
import com.vocabulario.app.data.normalizePosKey

@StringRes
fun posStringRes(pos: String?): Int? = when (normalizePosKey(pos)) {
    "noun" -> R.string.pos_noun
    "verb" -> R.string.pos_verb
    "adj" -> R.string.pos_adj
    "adv" -> R.string.pos_adv
    "prep" -> R.string.pos_prep
    "conj" -> R.string.pos_conj
    "pron" -> R.string.pos_pron
    "det" -> R.string.pos_det
    "interj" -> R.string.pos_interj
    else -> null
}

/** Part-of-speech label in the active app UI language. */
@Composable
fun localizedPosLabel(pos: String?): String {
    val res = posStringRes(pos) ?: return ""
    return stringResource(res)
}
