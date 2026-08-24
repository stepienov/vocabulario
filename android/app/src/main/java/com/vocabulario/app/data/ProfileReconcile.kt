package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang

/** Wybiera profil, który naprawdę jest na serwerze — nie ghost ID z TokenStore/Room. */
internal fun resolveActiveProfile(
    storedId: String?,
    remote: List<LanguageProfileResponse>,
): LanguageProfileResponse? {
    if (remote.isEmpty()) return null
    storedId?.takeIf { it.isNotBlank() }?.let { id ->
        remote.firstOrNull { it.id == id }?.let { return it }
    }
    return remote.firstOrNull { it.is_active } ?: remote.first()
}

/**
 * GET /profiles nie może cofać lokalnie wybranej pary.
 * CEFR / czasy aktywnego id zostają; [is_active] idzie za TokenStore/Room.
 */
internal fun mergeRemoteProfiles(
    remote: List<LanguageProfileResponse>,
    localActive: LanguageProfileResponse?,
    chosenId: String?,
): List<LanguageProfileResponse> {
    if (remote.isEmpty()) return emptyList()
    val resolved = resolveActiveProfile(chosenId ?: localActive?.id, remote) ?: return remote
    return remote.map { remoteProfile ->
        val withLocalPrefs = if (localActive != null && remoteProfile.id == localActive.id) {
            remoteProfile.copy(
                selected_tenses = localActive.selected_tenses,
                cefr_level = localActive.cefr_level,
                tense_label_lang = localActive.tense_label_lang,
            )
        } else {
            remoteProfile
        }
        withLocalPrefs.copy(is_active = withLocalPrefs.id == resolved.id)
    }
}

internal fun overlayAppLang(
    profile: LanguageProfileResponse,
    storedLang: String,
): LanguageProfileResponse {
    val lang = storedLang.trim().lowercase()
    if (lang.isBlank() || profile.appLang.equals(lang, ignoreCase = true)) return profile
    return profile.copy(app_lang = lang, native_lang = lang)
}

internal fun findLangPair(
    profiles: List<LanguageProfileResponse>,
    appLang: String,
    learningLang: String,
): LanguageProfileResponse? {
    val app = appLang.trim().lowercase()
    val learning = learningLang.trim().lowercase()
    return profiles.firstOrNull {
        it.appLang.equals(app, ignoreCase = true) &&
            it.learning_lang.equals(learning, ignoreCase = true)
    }
}

/** Para (język aplikacji, język nauki) ma własny profil — nigdy nie nadpisujemy app_lang istniejącej pary. */
internal sealed class LangPairSwitch {
    data object Keep : LangPairSwitch()
    data class Activate(val profileId: String) : LangPairSwitch()
    data object Create : LangPairSwitch()
}

internal fun langPairSwitch(
    existing: LanguageProfileResponse?,
    activeProfileId: String?,
): LangPairSwitch {
    if (existing == null) return LangPairSwitch.Create
    if (existing.id == activeProfileId) return LangPairSwitch.Keep
    return LangPairSwitch.Activate(existing.id)
}
