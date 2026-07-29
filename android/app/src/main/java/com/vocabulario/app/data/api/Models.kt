package com.vocabulario.app.data.api

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName

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
    val ui_lang: String,
    val role: String,
)

@Serializable
data class UserUpdate(val ui_lang: String? = null)

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
    val show_periphrases: Boolean = true,
    val conjugation_expanded_default: Boolean = false,
    val show_example_sentences: Boolean = true,
    val related_words_expanded_default: Boolean = false,
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
    val show_periphrases: Boolean? = null,
    val conjugation_expanded_default: Boolean? = null,
    val show_example_sentences: Boolean? = null,
    val related_words_expanded_default: Boolean? = null,
)

@Serializable
data class LanguageProfileCreate(
    val native_lang: String,
    val learning_lang: String,
    val cefr_level: String = "A2",
    val selected_tenses: List<String> = emptyList(),
)

@Serializable
data class LanguageProfileResponse(
    val id: String,
    val native_lang: String,
    val learning_lang: String,
    val cefr_level: String,
    val selected_tenses: List<String>,
    val is_active: Boolean,
    val last_used_at: String? = null,
)

@Serializable
data class LookupRequest(val text: String, val profile_id: String)

@Serializable
data class LanguageProfileUpdate(
    val cefr_level: String? = null,
    val selected_tenses: List<String>? = null,
)

@Serializable
data class LookupCandidate(
    val lemma: String,
    val pos: String? = null,
    val gloss: String,
    val lexical_entry_id: String? = null,
    val in_learning: Boolean = false,
    val is_favorite: Boolean = false,
    val learning_card_id: String? = null,
)

@Serializable
data class LookupResponse(
    val candidates: List<LookupCandidate>,
    val source: String,
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
)

@Serializable
data class FavoriteCreate(
    val lemma: String,
    val pos: String? = null,
    val gloss: String? = null,
    val profile_id: String,
)

@Serializable
data class FavoriteResponse(
    val id: String,
    val lemma: String,
    val pos: String? = null,
    val gloss: String? = null,
    val created_at: String,
    val enrichment_status: String = "ready",
)

@Serializable
data class SrsQueueItem(
    val card_id: String,
    val lemma_l2: String,
    val gloss_primary: String? = null,
    val content: kotlinx.serialization.json.JsonObject,
    val status: String,
    val direction: String? = null,
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
    val is_favorite: Boolean = false,
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
