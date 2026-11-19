from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    UUID4,
    BaseModel,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID
    session_id: UUID
    expires_in: int


class RegisterRequest(BaseModel):
    email: EmailStr
    # Password policy codes (422) come from the service; the schema only caps the body size.
    password: str = Field(max_length=4096)
    # UI language for the verification mail; the account has no profile yet.
    locale: str | None = Field(default=None, max_length=16)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=4096)


class GoogleAuthRequest(BaseModel):
    challenge_id: UUID4
    id_token: str = Field(min_length=1, max_length=8192)
    # Verification mail language when a new account's Google address is not proven.
    locale: str | None = Field(default=None, max_length=16)


class GoogleLinkChallengeRequest(BaseModel):
    recent_auth_token: str = Field(min_length=1, max_length=128)


class RecentAuthGoogleChallengeRequest(BaseModel):
    action: Literal["change_email", "add_password"]


class GoogleChallengeResponse(BaseModel):
    challenge_id: UUID
    nonce: str
    expires_at: datetime


class GoogleLinkRequest(BaseModel):
    challenge_id: UUID4
    id_token: str = Field(min_length=1, max_length=8192)
    recent_auth_token: str = Field(min_length=1, max_length=128)


class RecentAuthGoogleRequest(BaseModel):
    challenge_id: UUID4
    id_token: str = Field(min_length=1, max_length=8192)
    action: Literal["change_email", "add_password"]


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)
    request_id: UUID4


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


# Password values get their own policy codes (422) in the service, so the schema only
# caps the body size instead of using min/max_length.
class PasswordResetRequest(BaseModel):
    email: EmailStr
    locale: str | None = Field(default=None, max_length=16)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(max_length=4096)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(max_length=4096)
    new_password: str = Field(max_length=4096)


class MailAcceptedResponse(BaseModel):
    status: str = "accepted"
    retry_after_seconds: int


class PasswordResetResponse(BaseModel):
    status: str = "password_reset"
    requires_login: bool = True


class EmailVerificationConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class StatusResponse(BaseModel):
    status: str


class RecentAuthPasswordRequest(BaseModel):
    password: str = Field(max_length=4096)
    action: str = Field(max_length=32)


class RecentAuthResponse(BaseModel):
    recent_auth_token: str
    action: str
    expires_at: datetime


class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    recent_auth_token: str = Field(min_length=1, max_length=128)
    request_id: UUID4

    @field_validator("new_email", mode="before")
    @classmethod
    def _strip_edges(cls, value):
        return value.strip() if isinstance(value, str) else value


class EmailChangeResponse(BaseModel):
    change_id: UUID
    mode: str
    status: str
    new_email: str
    expires_at: datetime
    resend_available_at: datetime | None
    delivery_status: str
    delivery_delayed: bool


class EmailChangeCurrentResponse(BaseModel):
    change: EmailChangeResponse | None


class EmailChangeConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class EmailChangeConfirmed(BaseModel):
    status: str = "email_changed"
    requires_login: bool = True


class AddPasswordRequest(BaseModel):
    new_password: str = Field(max_length=4096)
    recent_auth_token: str = Field(min_length=1, max_length=128)


class EmailVerificationStatusResponse(BaseModel):
    email_verified: bool
    delivery_status: str
    delivery_delayed: bool
    resend_available_at: datetime | None


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    email_verified: bool
    # True when the server gate blocks study/sync until this address is confirmed.
    email_verification_required: bool = False
    login_methods: list[str]
    # Legacy password hash: only a reset can set a new password.
    password_upgrade_required: bool = False
    # Revision of the current address: a cached confirmation never carries over to another address.
    email_revision: int = 1
    account_status: str = "active"
    lifecycle_revision: int = 1
    # Last address Google reported for the linked identity; absent without a Google method.
    google_email: str | None = None
    google_email_observed_at: datetime | None = None


class UserSettingsResponse(BaseModel):
    practice_input_pref: str
    practice_direction: str
    typing_tolerance: str
    typo_modal_enabled: bool
    new_cards_per_day: int
    theme: str
    show_usages: bool = True
    show_synonyms_antonyms: bool = True
    show_synonyms: bool = True
    show_antonyms: bool = True
    show_word_family: bool = True
    show_associations: bool = True
    show_periphrases: bool = True
    show_conjugation: bool = True
    conjugation_expanded_default: bool = False
    show_example_sentences: bool = True
    related_words_expanded_default: bool = False
    study_reminder_enabled: bool = True
    cards_ready_push_enabled: bool = True
    reminder_hour: int = 19

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    practice_input_pref: str | None = None
    practice_direction: str | None = None
    typing_tolerance: str | None = None
    typo_modal_enabled: bool | None = None
    new_cards_per_day: int | None = None
    theme: str | None = None
    show_usages: bool | None = None
    show_synonyms_antonyms: bool | None = None
    show_synonyms: bool | None = None
    show_antonyms: bool | None = None
    show_word_family: bool | None = None
    show_associations: bool | None = None
    show_periphrases: bool | None = None
    show_conjugation: bool | None = None
    conjugation_expanded_default: bool | None = None
    show_example_sentences: bool | None = None
    related_words_expanded_default: bool | None = None
    study_reminder_enabled: bool | None = None
    cards_ready_push_enabled: bool | None = None
    reminder_hour: int | None = None


class LanguageProfileCreate(BaseModel):
    app_lang: str | None = Field(default=None, min_length=2, max_length=8)
    native_lang: str | None = Field(default=None, min_length=2, max_length=8)
    learning_lang: str = Field(min_length=2, max_length=8)
    cefr_level: str = "A2"
    selected_tenses: list[str] = Field(default_factory=list)
    tense_label_lang: str = "app_lang"

    @model_validator(mode="before")
    @classmethod
    def _coerce_app_lang(cls, data: object) -> object:
        if isinstance(data, dict):
            if not data.get("app_lang") and data.get("native_lang"):
                data = {**data, "app_lang": data["native_lang"]}
        return data

    @model_validator(mode="after")
    def _require_app_lang(self) -> "LanguageProfileCreate":
        if not self.app_lang:
            raise ValueError("app_lang is required")
        object.__setattr__(self, "app_lang", self.app_lang.strip().lower())
        object.__setattr__(self, "learning_lang", self.learning_lang.strip().lower())
        if self.tense_label_lang not in {"app_lang", "learning_lang"}:
            raise ValueError("tense_label_lang must be app_lang or learning_lang")
        from app.services.tenses import normalize_tense_keys

        object.__setattr__(
            self,
            "selected_tenses",
            normalize_tense_keys(self.selected_tenses, learning_lang=self.learning_lang),
        )
        return self


class LanguageProfileResponse(BaseModel):
    id: UUID
    app_lang: str
    learning_lang: str
    cefr_level: str
    selected_tenses: list[str]
    tense_label_lang: str = "app_lang"
    is_active: bool
    last_used_at: datetime | None
    revision: int = 1

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def native_lang(self) -> str:
        return self.app_lang

    @field_validator("selected_tenses")
    @classmethod
    def _normalize_response_tenses(cls, value: list[str]) -> list[str]:
        from app.services.tenses import normalize_tense_keys

        return normalize_tense_keys(value)

    @model_validator(mode="after")
    def _normalize_tenses_for_lang(self) -> "LanguageProfileResponse":
        from app.services.tenses import normalize_tense_keys

        object.__setattr__(
            self,
            "selected_tenses",
            normalize_tense_keys(self.selected_tenses, learning_lang=self.learning_lang),
        )
        return self


class LanguageProfileUpdate(BaseModel):
    cefr_level: str | None = None
    selected_tenses: list[str] | None = None
    app_lang: str | None = Field(default=None, min_length=2, max_length=8)
    tense_label_lang: str | None = None
    # Kontrakt T-004: rewizja bazowa i stabilny ID mutacji; legacy klient je pomija.
    expected_revision: int | None = Field(default=None, ge=1)
    client_op_id: UUID | None = None

    @field_validator("selected_tenses")
    @classmethod
    def _normalize_update_tenses(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        from app.services.tenses import normalize_tense_keys

        return normalize_tense_keys(value)

    @model_validator(mode="after")
    def _validate_tense_label_lang(self) -> "LanguageProfileUpdate":
        if self.tense_label_lang is not None and self.tense_label_lang not in {
            "app_lang",
            "learning_lang",
        }:
            raise ValueError("tense_label_lang must be app_lang or learning_lang")
        if self.app_lang is not None:
            object.__setattr__(self, "app_lang", self.app_lang.strip().lower())
        return self


class LookupRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    profile_id: UUID
    local_membership: bool = False
    more: bool = False
    operation_id: UUID | None = None
    round: int | None = Field(default=None, ge=1)


class LookupCandidate(BaseModel):
    lemma: str
    pos: str | None
    gloss: str
    lexical_entry_id: UUID | None = None
    in_learning: bool = False
    learning_card_id: UUID | None = None
    list_id: UUID | None = None
    list_name: str | None = None
    enrichment_status: str | None = None
    reading: str | None = None
    typed_as: str | None = None


class LookupResponse(BaseModel):
    candidates: list[LookupCandidate]
    source: str
    # True gdy któryś kandydat to pewne odczytanie zapytania (dokładne lemma/gloss).
    # Klient używa tego, by słowa-śmieci z trybu offline oznaczyć jako „wymaga sprawdzenia"
    # zamiast tworzyć kartę i palić tokeny na enrichment.
    confident: bool = False
    # True gdy ostatnie uzupełnienie OpenAI nie dodało nowych par lemat+POS.
    ai_complete: bool = False
    added: int | None = None
    suggestions_exhausted: bool = False
    headword_meaning: str = ""


class ImportValidateRequest(BaseModel):
    words: list[str] = Field(min_length=1, max_length=50)
    profile_id: UUID


class ImportValidWord(BaseModel):
    input: str
    lemma: str
    pos: str | None = None
    gloss: str = ""
    lexical_entry_id: UUID | None = None
    entry_kind: str = "lemma"
    base_lemma: str | None = None
    pattern: str | None = None


class ImportValidateResponse(BaseModel):
    valid: list[ImportValidWord]
    invalid: list[str]
    mode: str = "vocabulario"


class ImportIngestRequest(BaseModel):
    """Wklejka: surowy tekst albo pojedynczy URL Quizlet/AnkiWeb."""

    text: str = Field(min_length=1, max_length=500_000)
    profile_id: UUID
    mode: str = Field(default="vocabulario", description="Ignored; import always creates Vocabulario cards.")


class ImportJobCreateRequest(BaseModel):
    profile_id: UUID
    list_id: UUID
    mode: str = Field(default="vocabulario")
    text: str = Field(min_length=1, max_length=500_000)


class ImportJobCommitRequest(BaseModel):
    item_ids: list[UUID] | None = None


class ImportJobItemResponse(BaseModel):
    id: UUID
    ordinal: int
    input_label: str
    verdict: str
    reason_code: str | None = None
    reason_detail: str | None = None
    lemma: str | None = None
    gloss: str | None = None
    pos: str | None = None
    entry_kind: str | None = None
    display: dict | None = None
    existing_card_id: UUID | None = None
    created_card_id: UUID | None = None
    attempt: int = 0
    list_name: str | None = None


class ImportJobProgressResponse(BaseModel):
    job_id: UUID | None = None
    status: str = "idle"
    phase: str = "idle"
    stage: str = "idle"
    source_name: str = ""
    mode: str = "vocabulario"
    list_id: UUID | None = None
    list_name: str | None = None
    processed: int = 0
    total: int = 0
    current_ordinal: int | None = None
    current_label: str | None = None
    current_attempt: int = 0
    ready_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    created_count: int = 0
    cancel_requested: bool = False
    error_code: str | None = None
    error_message: str | None = None
    heartbeat_at: datetime | None = None
    daily_used: int = 0
    daily_limit: int = 25


class ImportJobDetailResponse(ImportJobProgressResponse):
    items: list[ImportJobItemResponse] = Field(default_factory=list)


class ImportJobAdminResponse(ImportJobProgressResponse):
    user_id: UUID
    profile_id: UUID
    created_at: datetime | None = None
    finished_at: datetime | None = None


class ImportJobEventResponse(BaseModel):
    id: UUID
    job_id: UUID
    item_id: UUID | None = None
    at: datetime
    level: str
    event: str
    payload: dict | None = None

    model_config = {"from_attributes": True}


class AppLogResponse(BaseModel):
    id: UUID
    created_at: datetime
    level: str
    category: str
    event: str
    status: str
    request_id: UUID | None = None
    user_id: UUID | None = None
    profile_id: UUID | None = None
    http_method: str | None = None
    http_path: str | None = None
    http_status: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    duration_ms: int | None = None
    message: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    traceback: str | None = None
    payload: dict | None = None

    model_config = {"from_attributes": True}


class LlmUsageResponse(BaseModel):
    id: UUID
    created_at: datetime
    provider: str
    model: str
    purpose: str
    operation_id: UUID | None = None
    operation_kind: str | None = None
    query: str | None = None
    lemma: str | None = None
    pos: str | None = None
    lang_pair: str | None = None
    card_id: UUID | None = None
    user_id: UUID | None = None
    profile_id: UUID | None = None
    request_id: UUID | None = None
    openai_response_id: str | None = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    estimated_cost_usd: float | None = None
    pricing_version: str | None = None
    duration_ms: int | None = None
    status: str
    lookup_event_id: UUID | None = None

    model_config = {"from_attributes": True}


class LlmUsageListResponse(BaseModel):
    items: list[LlmUsageResponse]
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cached_tokens: int
    total_estimated_cost_usd: float | None = None


class WordListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile_id: UUID
    # Stabilny klucz z lokalnego intentu: ponowienie po utraconej odpowiedzi nie tworzy drugiej listy.
    client_op_id: UUID | None = None


class WordListUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WordListResponse(BaseModel):
    id: UUID
    name: str
    is_system: bool
    is_pending_inbox: bool = False
    word_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class WordListAddWordRequest(BaseModel):
    lemma: str
    pos: str | None = None
    gloss: str | None = None
    lexical_entry_id: UUID | None = None
    profile_id: UUID
    entry_kind: str = "lemma"
    base_lemma: str | None = None
    pattern: str | None = None
    source_card_id: UUID | None = None


class WordMoveRequest(BaseModel):
    target_list_id: UUID
    profile_id: UUID


class DashboardForecastDay(BaseModel):
    day_offset: int
    label: str
    due_count: int


class DashboardStatsResponse(BaseModel):
    due_count: int
    new_remaining: int
    new_done_today: int
    new_limit: int
    reviews_done_today: int
    done_today: int
    srs_new: int
    srs_due: int
    srs_learning: int
    srs_mastered: int
    new_reserve: int
    cards_total: int
    forecast: list[DashboardForecastDay] = []
    last_added_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    # legacy aliases for older clients
    new_today: int = 0
    reviews_in_period: int = 0
    avg_words_per_day: float = 0.0
    period_days: int = 1


class CardCreateRequest(BaseModel):
    lemma: str
    pos: str | None = None
    gloss: str | None = None
    profile_id: UUID
    lexical_entry_id: UUID | None = None
    entry_kind: str = "lemma"
    base_lemma: str | None = None
    pattern: str | None = None
    source_card_id: UUID | None = None


class CardContent(BaseModel):
    schema_version: str = "vocabulario.card.v1"
    lemma: str
    language: str
    pos: str | None = None
    ipa: str | None = None
    headword_note: str | None = None
    meanings: list[dict] = Field(default_factory=list)
    synonyms_l2: list[dict | str] = Field(default_factory=list)
    antonyms_l2: list[dict | str] = Field(default_factory=list)
    word_family_l2: list[dict | str] = Field(default_factory=list)
    associations_l2: list[dict | str] = Field(default_factory=list)
    similar_words: list[dict] = Field(default_factory=list)
    conjugation: dict | None = None
    notes: str | None = None
    confidence: float | None = None


class CardResponse(BaseModel):
    id: UUID
    lemma_l2: str
    pos: str | None
    gloss_primary: str | None
    content: dict
    lexical_entry_id: UUID | None
    created_at: datetime
    persisted: bool = True
    enrichment_status: str = "ready"
    enrichment_error: str | None = None
    enrichment_active: bool = False
    srs_status: str | None = None
    srs_interval_days: float | None = None
    srs_next_review_at: datetime | None = None
    srs_last_reviewed_at: datetime | None = None
    content_review_status: str | None = None
    card_activity_status: str | None = None
    has_content_changes: bool = False

    model_config = {"from_attributes": True}


class CardCorrectionCreate(BaseModel):
    sections: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("sections")
    @classmethod
    def _strip_sections(cls, value: list[str]) -> list[str]:
        return [s.strip().lower() for s in value if s and s.strip()]

    @model_validator(mode="after")
    def _sections_or_note(self) -> "CardCorrectionCreate":
        return self


class CardCorrectionCreateResponse(BaseModel):
    correction_id: UUID
    status: str = "reported"


class CorrectionQuotaResponse(BaseModel):
    used: int
    limit: int
    remaining: int


class CardCorrectionResponse(BaseModel):
    id: UUID
    card_id: UUID
    sections: list[str]
    note: str | None
    status: str
    result_code: str | None = None
    reason: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class CorrectionEscalateResponse(BaseModel):
    id: UUID
    status: str = "pending"


class CardHistoryEventResponse(BaseModel):
    id: UUID
    card_id: UUID
    event_type: str
    actor: str
    result_code: str | None = None
    summary: str | None = None
    payload: dict | None = None
    created_at: datetime
    can_restore: bool = False


class CardHistoryResponse(BaseModel):
    events: list[CardHistoryEventResponse]


class DeviceRegisterRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    platform: str = Field(default="android", max_length=16)


class SrsQueueItem(BaseModel):
    card_id: UUID
    lemma_l2: str
    gloss_primary: str | None
    content: dict
    status: str
    direction: str | None = None
    enrichment_status: str | None = None
    card_activity_status: str | None = None
    has_content_changes: bool = False


class SrsQueueResponse(BaseModel):
    due: list[SrsQueueItem]
    new: list[SrsQueueItem]
    practice_direction: str


class ReviewRequest(BaseModel):
    card_id: UUID
    grade: str = Field(description="again|hard|good|easy")
    mode: str
    direction: str
    correct: bool
    answer: str | None = None

    @field_validator("grade")
    @classmethod
    def _normalize_grade(cls, value: str) -> str:
        from app.services.srs import normalize_grade

        g = normalize_grade(value.strip().lower())
        if g not in {"again", "hard", "good", "easy"}:
            raise ValueError("grade must be again|hard|good|easy")
        return g


class ReviewResponse(BaseModel):
    next_review_at: datetime | None
    status: str
    interval_days: float


class SyncSrsState(BaseModel):
    card_id: UUID
    status: str
    ease: float = 2.5
    interval_days: float = 0
    repetitions: int = 0
    lapses: int = 0
    next_review_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    last_grade: str | None = None
    stability: float | None = None
    difficulty: float | None = None
    fsrs_step: int | None = None


class SrsUndoRequest(BaseModel):
    client_id: UUID
    previous_srs: SyncSrsState


class SrsUndoResponse(BaseModel):
    srs: SyncSrsState


class SyncCardItem(BaseModel):
    id: UUID
    profile_id: UUID
    deck_id: UUID | None = None
    lemma_l2: str
    pos: str | None = None
    gloss_primary: str | None = None
    content: dict
    enrichment_status: str = "ready"
    content_review_status: str | None = None
    card_activity_status: str | None = None
    has_content_changes: bool = False
    updated_at: datetime | None = None
    srs: SyncSrsState | None = None


class SyncListItem(BaseModel):
    id: UUID
    name: str
    is_system: bool = False
    is_pending_inbox: bool = False
    word_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SyncPullResponse(BaseModel):
    server_time: datetime
    settings: UserSettingsResponse
    cards: list[SyncCardItem]
    lists: list[SyncListItem] = []
    deleted_card_ids: list[UUID] = []
    deleted_list_ids: list[UUID] = []
    cursor: str | None = None


class SyncPullRequest(BaseModel):
    profile_id: UUID
    cursor: str | None = None

class SyncReviewItem(BaseModel):
    client_id: UUID
    card_id: UUID
    grade: str
    mode: str
    direction: str
    correct: bool
    answer: str | None = None
    reviewed_at: datetime

    @field_validator("grade")
    @classmethod
    def _normalize_grade(cls, value: str) -> str:
        from app.services.srs import normalize_grade

        g = normalize_grade(value.strip().lower())
        if g not in {"again", "hard", "good", "easy"}:
            raise ValueError("grade must be again|hard|good|easy")
        return g


class SyncMoveItem(BaseModel):
    client_id: UUID
    card_id: UUID
    # None or system list id → Learning deck (deck_id NULL)
    target_list_id: UUID | None = None
    moved_at: datetime


class SyncPushRequest(BaseModel):
    reviews: list[SyncReviewItem] = Field(default_factory=list)
    moves: list[SyncMoveItem] = Field(default_factory=list)


class SyncMoveResult(BaseModel):
    client_id: UUID
    card_id: UUID
    deck_id: UUID | None = None


class SyncOperationResult(BaseModel):
    """Potwierdzenie jednej wysłanej operacji (review albo move)."""

    client_id: UUID
    card_id: UUID
    outcome: Literal["applied", "duplicate", "superseded", "not_found", "conflict"]
    reason: Literal[
        "card_unavailable", "target_unavailable", "undo_already_applied", "operation_id_conflict"
    ] | None = None


class SyncPushResponse(BaseModel):
    applied: int
    skipped: int
    srs: list[SyncSrsState] = []
    moves_applied: int = 0
    moves_skipped: int = 0
    moves: list[SyncMoveResult] = []
    review_results: list[SyncOperationResult] = []
    move_results: list[SyncOperationResult] = []
