package com.vocabulario.app.data

import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.api.appLang
import com.vocabulario.app.data.sync.ProfileFields
import com.vocabulario.app.data.sync.withFields

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
 * GET /profiles nie może cofać lokalnie wybranej pary ani niewysłanej edycji.
 * Wartości serwera są zatwierdzonym snapshotem ([LanguageProfileResponse.confirmed]); widoczne pola
 * to snapshot z nakładką [drafts]. [is_active] idzie za wyborem lokalnym, nie za serwerowym flagą.
 * Profil z lokalną pracą ([protectedIds]) nie znika, gdy serwer go nie zwrócił.
 */
internal fun mergeRemoteProfiles(
    remote: List<LanguageProfileResponse>,
    local: List<LanguageProfileResponse>,
    drafts: Map<String, ProfileFields>,
    protectedIds: Set<String>,
    chosenId: String?,
): List<LanguageProfileResponse> {
    val remoteIds = remote.map { it.id }.toSet()
    val localById = local.associateBy { it.id }
    // Spóźniona odpowiedź GET nie cofa rewizji już potwierdzonej przez ACK: zostaje lokalny snapshot.
    val fromRemote = remote.map { r ->
        val l = localById[r.id]
        val lr = l?.revision
        val rr = r.revision
        if (l != null && lr != null && rr != null && rr < lr) l else r.copy(confirmed = ProfileFields.of(r))
    }
    val kept = local.filter { it.id !in remoteIds && it.id in protectedIds }
    val combined = fromRemote + kept
    if (combined.isEmpty()) return emptyList()
    val resolved = resolveActiveProfile(chosenId ?: local.firstOrNull { it.is_active }?.id, combined)
        ?: return combined
    return combined.map { profile ->
        val withDraft = drafts[profile.id]?.let { profile.withFields(it) } ?: profile
        withDraft.copy(is_active = withDraft.id == resolved.id)
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
