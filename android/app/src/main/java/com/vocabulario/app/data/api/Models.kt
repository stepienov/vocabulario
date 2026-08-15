package com.vocabulario.app.data.api

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName
import kotlinx.serialization.json.JsonNames
import kotlinx.serialization.json.JsonObject

@Serializable
data class TokenResponse(
    val access_token: String,
    val refresh_token: String,
    val token_type: String = "bearer",
)

@Serializable
data class RegisterRequest(val email: String, val password: String)

@Serializable
data class LoginRequest(val email: String, val password: String)

@Serializable
data class GoogleAuthRequest(val id_token: String)

@Serializable
data class RefreshRequest(val refresh_token: String)

@Serializable
data class UserResponse(
    val id: String,
    val email: String,
    val role: String,
)

@Serializable
data class UserSettingsResponse(
    val practice_input_pref: String,
    val practice_direction: String,
    val typing_tolerance: String,
    val typo_modal_enabled: Boolean,
    val new_cards_per_day: Int,
    val theme: String,
    val show_usages: Boolean = true,
    val show_synonyms_antonyms: Boolean = true,
    val show_synonyms: Boolean = true,
    val show_antonyms: Boolean = true,
    val show_word_family: Boolean = true,
    val show_periphrases: Boolean = true,
    val show_conjugation: Boolean = true,
    val conjugation_expanded_default: Boolean = false,
    val show_example_sentences: Boolean = true,
    val related_words_expanded_default: Boolean = false,
    val study_reminder_enabled: Boolean = true,
    val cards_ready_push_enabled: Boolean = true,
    val reminder_hour: Int = 19,
)

@Serializable
data class UserSettingsUpdate(
    val practice_input_pref: String? = null,
    val practice_direction: String? = null,
    val typing_tolerance: String? = null,
    val typo_modal_enabled: Boolean? = null,
    val new_cards_per_day: Int? = null,
    val theme: String? = null,
    val show_usages: Boolean? = null,
    val show_synonyms_antonyms: Boolean? = null,
    val show_synonyms: Boolean? = null,
    val show_antonyms: Boolean? = null,
    val show_word_family: Boolean? = null,
    val show_periphrases: Boolean? = null,
    val show_conjugation: Boolean? = null,
    val conjugation_expanded_default: Boolean? = null,
    val show_example_sentences: Boolean? = null,
    val related_words_expanded_default: Boolean? = null,
    val study_reminder_enabled: Boolean? = null,
    val cards_ready_push_enabled: Boolean? = null,
    val reminder_hour: Int? = null,
)

@Serializable
data class LanguageProfileCreate(
    @JsonNames("native_lang")
    val app_lang: String,
    val learning_lang: String,
    val cefr_level: String = "A2",
    val selected_tenses: List<String> = emptyList(),
    val tense_label_lang: String = "app_lang",
)

@Serializable
data class LanguageProfileResponse(
    val id: String,
    @JsonNames("native_lang")
    val app_lang: String,
    val native_lang: String? = null,
    val learning_lang: String,
    val cefr_level: String,
    val selected_tenses: List<String>,
    val tense_label_lang: String = "app_lang",
    val is_active: Boolean,
    val last_used_at: String? = null,
)

@Serializable
data class LanguageProfileUpdate(
    val cefr_level: String? = null,
    val selected_tenses: List<String>? = null,
    val app_lang: String? = null,
    val tense_label_lang: String? = null,
)

@Serializable
data class LookupRequest(val text: String, val profile_id: String)

@Serializable
data class LookupCandidate(
    val lemma: String,
    val pos: String? = null,
    val gloss: String,
    val lexical_entry_id: String? = null,
    val in_learning: Boolean = false,
    val learning_card_id: String? = null,
    val list_id: String? = null,
    val list_name: String? = null,
    val enrichment_status: String? = null,
) {
    val onList: Boolean get() = !list_name.isNullOrBlank()
    val isCreating: Boolean get() = enrichment_status == "pending"
}

@Serializable
data class LookupResponse(
    val candidates: List<LookupCandidate>,
    val source: String,
    val confident: Boolean = false,
)

@Serializable
data class ImportValidateRequest(
    val words: List<String>,
    val profile_id: String,
)

@Serializable
data class ImportValidWord(
    val input: String,
    val lemma: String,
    val pos: String? = null,
    val gloss: String = "",
    val lexical_entry_id: String? = null,
    val entry_kind: String = "lemma",
    val base_lemma: String? = null,
    val pattern: String? = null,
)

@Serializable
data class ImportValidateResponse(
    val valid: List<ImportValidWord> = emptyList(),
    val invalid: List<String> = emptyList(),
    val mode: String = "vocabulario",
)

@Serializable
data class ImportIngestRequest(
    val text: String,
    val profile_id: String,
    val mode: String = "vocabulario",
)

@Serializable
data class ImportTts(
    val enabled: Boolean = false,
    val lang: String? = null,
)

@Serializable
data class ImportDisplayBlock(
    val type: String,
    val text: String? = null,
    val emphasis: String? = null,
    val heading: String? = null,
    val collapsed: Boolean? = null,
    val items: List<String>? = null,
    val headers: List<String>? = null,
    val rows: List<List<String>>? = null,
    val children: List<ImportDisplayBlock>? = null,
    val align: String? = null,
    val size: String? = null,
    val semantic: String? = null,
    val tts: ImportTts? = null,
)

@Serializable
data class ImportDisplaySide(
    val blocks: List<ImportDisplayBlock> = emptyList(),
)

@Serializable
data class ImportDisplayPayload(
    val prompt: ImportDisplaySide = ImportDisplaySide(),
    val answer: ImportDisplaySide = ImportDisplaySide(),
    val prompt_style: String = "word",
    val bidirectional: Boolean = false,
)

@Serializable
data class ImportDisplayCard(
    val key: String,
    val lemma_l2: String,
    val gloss_primary: String? = null,
    val display: ImportDisplayPayload,
)

@Serializable
data class ImportDisplayResponse(
    val mode: String = "preserve",
    val cards: List<ImportDisplayCard> = emptyList(),
    val field_roles: List<JsonObject> = emptyList(),
    val rationale: String = "",
    val total_notes: Int = 0,
)

@Serializable
data class ImportDisplayCommitRequest(
    val profile_id: String,
    val list_id: String,
    val cards: List<ImportDisplayCard>,
)

@Serializable
data class ImportDisplayCommitResponse(
    val created: Int = 0,
    val skipped: Int = 0,
    val list_id: String,
)

@Serializable
data class WordListCreate(
    val name: String,
    val profile_id: String,
)

@Serializable
data class WordListUpdate(
    val name: String,
)

@Serializable
data class WordListResponse(
    val id: String,
    val name: String,
    val is_system: Boolean,
    val is_pending_inbox: Boolean = false,
    val word_count: Int = 0,
    val created_at: String? = null,
)

@Serializable
data class WordListAddWordRequest(
    val lemma: String,
    val pos: String? = null,
    val gloss: String? = null,
    val lexical_entry_id: String? = null,
    val profile_id: String,
    val entry_kind: String = "lemma",
    val base_lemma: String? = null,
    val pattern: String? = null,
)

@Serializable
data class WordMoveRequest(
    val target_list_id: String,
    val profile_id: String,
)

@Serializable
data class DashboardForecastDay(
    val day_offset: Int,
    val label: String,
    val due_count: Int,
)

@Serializable
data class DashboardStatsResponse(
    val due_count: Int = 0,
    val new_remaining: Int = 0,
    val new_done_today: Int = 0,
    val new_limit: Int = 0,
    val reviews_done_today: Int = 0,
    val done_today: Int = 0,
    val srs_new: Int = 0,
    val srs_due: Int = 0,
    val srs_learning: Int = 0,
    val srs_mastered: Int = 0,
    val new_reserve: Int = 0,
    val cards_total: Int = 0,
    val forecast: List<DashboardForecastDay> = emptyList(),
    val last_added_at: String? = null,
    val last_reviewed_at: String? = null,
    val new_today: Int = 0,
    val reviews_in_period: Int = 0,
    val avg_words_per_day: Double = 0.0,
    val period_days: Int = 1,
)

@Serializable
data class CardCreateRequest(
    val lemma: String,
    val pos: String? = null,
    val gloss: String? = null,
    val profile_id: String,
    val lexical_entry_id: String? = null,
)

@Serializable
data class CardResponse(
    val id: String,
    val lemma_l2: String,
    val pos: String? = null,
    val gloss_primary: String? = null,
    val content: kotlinx.serialization.json.JsonObject,
    val lexical_entry_id: String? = null,
    val created_at: String,
    val persisted: Boolean = true,
    val enrichment_status: String = "ready",
    val enrichment_error: String? = null,
    val srs_status: String? = null,
    val srs_interval_days: Double? = null,
    val content_review_status: String? = null,
    val card_activity_status: String? = null,
    val has_content_changes: Boolean = false,
)

@Serializable
data class SrsQueueItem(
    val card_id: String,
    val lemma_l2: String,
    val gloss_primary: String? = null,
    val content: kotlinx.serialization.json.JsonObject,
    val status: String,
    val direction: String? = null,
    val card_activity_status: String? = null,
    val has_content_changes: Boolean = false,
)

@Serializable
data class SrsQueueResponse(
    val due: List<SrsQueueItem>,
    @SerialName("new") val newCards: List<SrsQueueItem>,
    val practice_direction: String,
)

@Serializable
data class ReviewRequest(
    val card_id: String,
    val grade: String,
    val mode: String,
    val direction: String,
    val correct: Boolean,
    val answer: String? = null,
)

@Serializable
data class SrsUndoRequest(
    val client_id: String,
    val previous_srs: SyncSrsState,
)

@Serializable
data class SrsUndoResponse(
    val srs: SyncSrsState,
)

@Serializable
data class SyncSrsState(
    val card_id: String,
    val status: String,
    val ease: Double = 2.5,
    val interval_days: Double = 0.0,
    val repetitions: Int = 0,
    val lapses: Int = 0,
    val next_review_at: String? = null,
    val last_reviewed_at: String? = null,
    val last_grade: String? = null,
    val stability: Double? = null,
    val difficulty: Double? = null,
    val fsrs_step: Int? = null,
)

@Serializable
data class SyncCardItem(
    val id: String,
    val profile_id: String,
    val deck_id: String? = null,
    val lemma_l2: String,
    val pos: String? = null,
    val gloss_primary: String? = null,
    val content: kotlinx.serialization.json.JsonObject,
    val enrichment_status: String = "ready",
    val content_review_status: String? = null,
    val card_activity_status: String? = null,
    val has_content_changes: Boolean = false,
    val updated_at: String? = null,
    val srs: SyncSrsState? = null,
)

@Serializable
data class SyncListItem(
    val id: String,
    val name: String,
    val is_system: Boolean = false,
    val is_pending_inbox: Boolean = false,
    val word_count: Int = 0,
    val created_at: String? = null,
)

@Serializable
data class SyncPullResponse(
    val server_time: String,
    val settings: UserSettingsResponse,
    val cards: List<SyncCardItem> = emptyList(),
    val lists: List<SyncListItem> = emptyList(),
    val deleted_card_ids: List<String> = emptyList(),
    val deleted_list_ids: List<String> = emptyList(),
)

@Serializable
data class SyncReviewItem(
    val client_id: String,
    val card_id: String,
    val grade: String,
    val mode: String,
    val direction: String,
    val correct: Boolean,
    val answer: String? = null,
    val reviewed_at: String,
)

@Serializable
data class SyncMoveItem(
    val client_id: String,
    val card_id: String,
    val target_list_id: String? = null,
    val moved_at: String,
)

@Serializable
data class SyncPushRequest(
    val reviews: List<SyncReviewItem> = emptyList(),
    val moves: List<SyncMoveItem> = emptyList(),
)

@Serializable
data class SyncMoveResult(
    val client_id: String,
    val card_id: String,
    val deck_id: String? = null,
)

@Serializable
data class SyncPushResponse(
    val applied: Int = 0,
    val skipped: Int = 0,
    val srs: List<SyncSrsState> = emptyList(),
    val moves_applied: Int = 0,
    val moves_skipped: Int = 0,
    val moves: List<SyncMoveResult> = emptyList(),
)

@Serializable
data class ReviewResponse(
    val next_review_at: String? = null,
    val status: String,
    val interval_days: Float,
)

@Serializable
data class CheckAnswerRequest(
    val card_id: String,
    val answer: String,
    val direction: String,
)

@Serializable
data class CheckAnswerResponse(
    val correct: Boolean,
    val expected: String? = null,
    val accepted_as_typo: Boolean = false,
)

@Serializable
data class ChoiceOption(
    val text: String,
    val lemma_l2: String? = null,
    val gloss: String? = null,
    val pos: String? = null,
    val card_id: String? = null,
    val in_learning: Boolean = false,
    val is_correct: Boolean = false,
)

@Serializable
data class DistractorsRequest(
    val card_id: String,
    val profile_id: String,
    val direction: String,
)

@Serializable
data class DistractorsResponse(
    val options: List<ChoiceOption>,
    val direction: String,
)

@Serializable
data class CardCorrectionCreate(
    val sections: List<String> = emptyList(),
    val note: String? = null,
)

@Serializable
data class CardCorrectionCreateResponse(
    val correction_id: String,
    val status: String = "reported",
)

@Serializable
data class CardCorrectionResponse(
    val id: String,
    val card_id: String,
    val sections: List<String>,
    val note: String? = null,
    val status: String,
    val result_code: String? = null,
    val reason: String? = null,
    val created_at: String,
    val resolved_at: String? = null,
)

@Serializable
data class CardHistoryEventResponse(
    val id: String,
    val card_id: String,
    val event_type: String,
    val actor: String,
    val result_code: String? = null,
    val summary: String? = null,
    val payload: kotlinx.serialization.json.JsonObject? = null,
    val created_at: String,
    val can_restore: Boolean = false,
)

@Serializable
data class CardHistoryResponse(
    val events: List<CardHistoryEventResponse> = emptyList(),
)

@Serializable
data class CardRestoreRequest(
    val history_event_id: String,
)

@Serializable
data class CorrectionQuotaResponse(
    val used: Int,
    val limit: Int,
    val remaining: Int,
)

@Serializable
data class CardSelfEditRequest(
    val content: kotlinx.serialization.json.JsonObject,
)

@Serializable
data class SelfEditValidateIssue(
    val field: String,
    val label: String,
    val message: String,
)

@Serializable
data class SelfEditValidateResponse(
    val ok: Boolean,
    val issues: List<SelfEditValidateIssue> = emptyList(),
)

@Serializable
data class DeviceRegisterRequest(
    val token: String,
    val platform: String = "android",
)
