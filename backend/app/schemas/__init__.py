from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str

    model_config = {"from_attributes": True}


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
        return self

    @field_validator("selected_tenses")
    @classmethod
    def _normalize_create_tenses(cls, value: list[str]) -> list[str]:
        from app.services.tenses import normalize_tense_keys

        return normalize_tense_keys(value)


class LanguageProfileResponse(BaseModel):
    id: UUID
    app_lang: str
    learning_lang: str
    cefr_level: str
    selected_tenses: list[str]
    tense_label_lang: str = "app_lang"
    is_active: bool
    last_used_at: datetime | None

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


class LanguageProfileUpdate(BaseModel):
    cefr_level: str | None = None
    selected_tenses: list[str] | None = None
    app_lang: str | None = Field(default=None, min_length=2, max_length=8)
    tense_label_lang: str | None = None

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


class LookupResponse(BaseModel):
    candidates: list[LookupCandidate]
    source: str
    # True gdy któryś kandydat to pewne odczytanie zapytania (dokładne lemma/gloss).
    # Klient używa tego, by słowa-śmieci z trybu offline oznaczyć jako „wymaga sprawdzenia"
    # zamiast tworzyć kartę i palić tokeny na enrichment.
    confident: bool = False


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


class ImportDisplayBlock(BaseModel):
    type: str
    text: str | None = None
    emphasis: str | None = None
    heading: str | None = None
    collapsed: bool | None = None
    items: list[str] | None = None
    headers: list[str] | None = None
    rows: list[list[str]] | None = None
    children: list["ImportDisplayBlock"] | None = None
    align: str | None = None
    size: str | None = None
    semantic: str | None = None
    tts: dict | None = None


class ImportDisplaySide(BaseModel):
    blocks: list[ImportDisplayBlock] = Field(default_factory=list)


class ImportDisplayPayload(BaseModel):
    prompt: ImportDisplaySide = Field(default_factory=ImportDisplaySide)
    answer: ImportDisplaySide = Field(default_factory=ImportDisplaySide)
    prompt_style: str = "word"
    bidirectional: bool = False


class ImportDisplayCard(BaseModel):
    key: str
    lemma_l2: str
    gloss_primary: str | None = None
    display: ImportDisplayPayload


class ImportDisplayResponse(BaseModel):
    mode: str = "preserve"
    cards: list[ImportDisplayCard]
    field_roles: list[dict] = Field(default_factory=list)
    rationale: str = ""
    total_notes: int = 0


class ImportDisplayCommitRequest(BaseModel):
    profile_id: UUID
    list_id: UUID
    cards: list[ImportDisplayCard] = Field(min_length=1, max_length=50)


class ImportDisplayCommitResponse(BaseModel):
    created: int
    skipped: int
    list_id: UUID


class ImportIngestRequest(BaseModel):
    """Wklejka: surowy tekst albo pojedynczy URL Quizlet/AnkiWeb."""

    text: str = Field(min_length=1, max_length=500_000)
    profile_id: UUID
    mode: str = Field(default="vocabulario", description="vocabulario | preserve")


class WordListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile_id: UUID


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


class CardContent(BaseModel):
    schema_version: str = "vocabulario.card.v1"
    lemma: str
    language: str
    pos: str | None = None
    ipa: str | None = None
    meanings: list[dict] = Field(default_factory=list)
    synonyms_l2: list[dict | str] = Field(default_factory=list)
    antonyms_l2: list[dict | str] = Field(default_factory=list)
    word_family_l2: list[dict | str] = Field(default_factory=list)
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
    srs_status: str | None = None
    srs_interval_days: float | None = None
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


class CardSelfEditRequest(BaseModel):
    content: dict

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: dict) -> dict:
        if not isinstance(value, dict):
            raise ValueError("content must be an object")
        lemma = str(value.get("lemma") or "").strip()
        if not lemma:
            raise ValueError("content.lemma is required")
        return value


class SelfEditValidateIssue(BaseModel):
    field: str
    label: str
    message: str


class SelfEditValidateResponse(BaseModel):
    ok: bool
    issues: list[SelfEditValidateIssue] = []


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


class CardRestoreRequest(BaseModel):
    history_event_id: UUID


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


class SyncPushResponse(BaseModel):
    applied: int
    skipped: int
    srs: list[SyncSrsState] = []
    moves_applied: int = 0
    moves_skipped: int = 0
    moves: list[SyncMoveResult] = []


ImportDisplayBlock.model_rebuild()
