package com.vocabulario.app.data.sync

import com.vocabulario.app.data.api.LanguageProfileResponse
import kotlinx.serialization.Serializable

/** Edytowalne pola profilu; w intencie tylko zmienione, w snapshotcie wszystkie cztery. */
@Serializable
data class ProfileFields(
    val cefr_level: String? = null,
    val selected_tenses: List<String>? = null,
    val app_lang: String? = null,
    val tense_label_lang: String? = null,
) {
    val isEmpty: Boolean
        get() = cefr_level == null && selected_tenses == null && app_lang == null && tense_label_lang == null

    /** Pola z [newer] wygrywają; reszta zostaje. */
    fun overlaidBy(newer: ProfileFields) = ProfileFields(
        cefr_level = newer.cefr_level ?: cefr_level,
        selected_tenses = newer.selected_tenses ?: selected_tenses,
        app_lang = newer.app_lang ?: app_lang,
        tense_label_lang = newer.tense_label_lang ?: tense_label_lang,
    )

    /** Tylko te pola, które różnią się od [current]. */
    fun changedAgainst(current: ProfileFields) = ProfileFields(
        cefr_level = cefr_level?.takeIf { it != current.cefr_level },
        selected_tenses = selected_tenses?.takeIf { it != current.selected_tenses },
        app_lang = app_lang?.takeIf { it != current.app_lang },
        tense_label_lang = tense_label_lang?.takeIf { it != current.tense_label_lang },
    )

    /** Pola ustawione tutaj, ale z wartościami wziętymi z [source] (wartości sprzed edycji). */
    fun valuesFrom(source: ProfileFields) = ProfileFields(
        cefr_level = source.cefr_level.takeIf { cefr_level != null },
        selected_tenses = source.selected_tenses.takeIf { selected_tenses != null },
        app_lang = source.app_lang.takeIf { app_lang != null },
        tense_label_lang = source.tense_label_lang.takeIf { tense_label_lang != null },
    )

    /** Czy każde ustawione tutaj pole ma na serwerze już tę samą wartość. */
    fun matchedBy(server: ProfileFields): Boolean = !isEmpty && changedAgainst(server).isEmpty

    companion object {
        fun of(profile: LanguageProfileResponse) = ProfileFields(
            cefr_level = profile.cefr_level,
            selected_tenses = profile.selected_tenses,
            app_lang = profile.app_lang,
            tense_label_lang = profile.tense_label_lang,
        )

        val CEFR_LEVELS = setOf("A1", "A2", "B1", "B2", "C1", "C2")
        val TENSE_LABEL_LANGS = setOf("app_lang", "learning_lang")
    }
}

fun LanguageProfileResponse.withFields(fields: ProfileFields): LanguageProfileResponse = copy(
    cefr_level = fields.cefr_level ?: cefr_level,
    selected_tenses = fields.selected_tenses ?: selected_tenses,
    app_lang = fields.app_lang ?: app_lang,
    native_lang = fields.app_lang ?: native_lang,
    tense_label_lang = fields.tense_label_lang ?: tense_label_lang,
)

/** Walidacja przed zapisem lokalnym; serwer i tak sprawdza ponownie (422). */
fun validateProfileFields(fields: ProfileFields): Boolean =
    (fields.cefr_level == null || fields.cefr_level in ProfileFields.CEFR_LEVELS) &&
        (fields.app_lang == null || fields.app_lang.trim().length in 2..8) &&
        (fields.tense_label_lang == null || fields.tense_label_lang in ProfileFields.TENSE_LABEL_LANGS) &&
        (fields.selected_tenses == null || fields.selected_tenses.none { it.isBlank() })

/**
 * Wersjonowany payload outboxu `profile_update`. [baseRevision] == null oznacza draft czekający
 * na ustalenie bazy: nigdy nie jest wysyłany bez porównania z serwerem. [prev] to wartości zmienianych
 * pól sprzed pierwszej edycji, czyli ostatni znany snapshot do rozpoznania konfliktu.
 */
@Serializable
data class ProfileUpdatePayload(
    val v: Int = 1,
    val profileId: String,
    val baseRevision: Long? = null,
    val fields: ProfileFields,
    val prev: ProfileFields? = null,
)

/** Scala nowszą edycję z niewysłanym draftem tego samego profilu; nowszy wybór pola wygrywa. */
fun ProfileUpdatePayload.mergedWith(newFields: ProfileFields, newPrev: ProfileFields): ProfileUpdatePayload {
    val oldPrev = prev ?: ProfileFields()
    return copy(
        fields = fields.overlaidBy(newFields),
        // Wartości sprzed najstarszej edycji zostają; nowa jest dopisywana tylko dla nowych pól.
        prev = newPrev.overlaidBy(oldPrev),
    )
}

/** Wynik porównania draftu bez bazy z aktualnym profilem serwera. */
sealed interface BaseResolution {
    /** Serwer ma już te wartości: edycja jest potwierdzona bez PUT. */
    object AlreadyApplied : BaseResolution

    data class Use(val revision: Long) : BaseResolution

    /** Brak wiarygodnego snapshotu albo zmiana po obu stronach: decyduje użytkownik. */
    object Conflict : BaseResolution
}

fun resolveDraftBase(payload: ProfileUpdatePayload, server: LanguageProfileResponse): BaseResolution {
    val serverFields = ProfileFields.of(server)
    if (payload.fields.matchedBy(serverFields)) return BaseResolution.AlreadyApplied
    val revision = server.revision ?: return BaseResolution.Conflict
    val prev = payload.prev ?: return BaseResolution.Conflict
    val untouchedOnServer = payload.fields.valuesFrom(prev).matchedBy(serverFields)
    return if (untouchedOnServer) BaseResolution.Use(revision) else BaseResolution.Conflict
}

/** Przyczyny zablokowanej edycji/aktywacji profilu; używane też przez UI do doboru akcji. */
object ProfileBlock {
    const val CONFLICT = "profile_conflict"
    const val OPERATION_ID_CONFLICT = "operation_id_conflict"
    const val NOT_FOUND = "profile_not_found"
    const val INVALID = "profile_invalid"
    const val PAIR_EXISTS = "profile_pair_exists"

    /** Ponowne zastosowanie lokalnych zmian na świeżej bazie ma sens tylko po konflikcie rewizji. */
    fun canApplyMine(reason: String) = reason == CONFLICT || reason == OPERATION_ID_CONFLICT
}

/** Mapowanie odpowiedzi PUT /profiles/{id} na powód blokady; null = błąd przejściowy do ponowienia. */
fun profileUpdateBlockReason(status: Int, code: String?): String? = when {
    status == 409 && code == "profile_conflict" -> ProfileBlock.CONFLICT
    status == 409 && code == "operation_id_conflict" -> ProfileBlock.OPERATION_ID_CONFLICT
    status == 409 && code == "profile_pair_exists" -> ProfileBlock.PAIR_EXISTS
    status == 404 -> ProfileBlock.NOT_FOUND
    status == 422 -> ProfileBlock.INVALID
    else -> null
}

/** Widok wiersza outboxu `profile_update` potrzebny do decyzji o scaleniu (bez Room). */
data class ProfileOpView(
    val seq: Long,
    val status: String,
    val attempts: Int,
    val lastError: String?,
    val payload: ProfileUpdatePayload,
) {
    /** Nigdy nie wysłany: scalenie nie może rozjechać się z tym, co serwer mógł już zastosować. */
    val neverSent: Boolean get() = status == "pending" && attempts == 0 && lastError == null
}

/** Znacznik „próba wysyłki rozpoczęta" w lastError; po nim op nie jest już scalany. */
const val PROFILE_OP_SENT = "sent"

sealed interface ProfileEditPlan {
    /** [newPending] = true, gdy scalenie naprawia zablokowaną operację 422 i wraca ona do kolejki. */
    data class MergeInto(val seq: Long, val payload: ProfileUpdatePayload, val newPending: Boolean) : ProfileEditPlan

    data class Append(val payload: ProfileUpdatePayload) : ProfileEditPlan
}

/**
 * Reguły enqueue edycji profilu. [existing] to wszystkie operacje tego profilu w kolejności seq.
 * [confirmedRevision] to rewizja serwera znana z cache, [prev] wartości zmienianych pól sprzed edycji.
 */
fun planProfileEdit(
    profileId: String,
    changed: ProfileFields,
    prev: ProfileFields,
    confirmedRevision: Long?,
    existing: List<ProfileOpView>,
): ProfileEditPlan {
    val last = existing.lastOrNull()
    if (last != null) {
        if (last.status == "blocked") {
            return ProfileEditPlan.MergeInto(
                last.seq,
                last.payload.mergedWith(changed, prev),
                newPending = last.lastError == ProfileBlock.INVALID,
            )
        }
        if (last.neverSent) {
            return ProfileEditPlan.MergeInto(last.seq, last.payload.mergedWith(changed, prev), newPending = false)
        }
    }
    return ProfileEditPlan.Append(
        ProfileUpdatePayload(
            profileId = profileId,
            // Poprzednia niepotwierdzona mutacja uzupełni bazę przy ACK.
            baseRevision = if (existing.isEmpty()) confirmedRevision else null,
            fields = changed,
            prev = prev,
        ),
    )
}

/** Nakładka niepotwierdzonych edycji w kolejności seq; nowsza wygrywa. */
fun overlayDrafts(ops: List<ProfileOpView>): ProfileFields =
    ops.fold(ProfileFields()) { acc, op -> acc.overlaidBy(op.payload.fields) }
