from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


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
    ui_lang: str
    role: str

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    ui_lang: str | None = Field(default=None, min_length=2, max_length=8)


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
    show_periphrases: bool = True
    show_conjugation: bool = True
    conjugation_expanded_default: bool = False
    show_example_sentences: bool = True
    related_words_expanded_default: bool = False

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
    show_periphrases: bool | None = None
    show_conjugation: bool | None = None
    conjugation_expanded_default: bool | None = None
    show_example_sentences: bool | None = None
    related_words_expanded_default: bool | None = None


class LanguageProfileCreate(BaseModel):
    native_lang: str = Field(min_length=2, max_length=8)
    learning_lang: str = Field(min_length=2, max_length=8)
    cefr_level: str = "A2"
    selected_tenses: list[str] = Field(default_factory=list)

    @field_validator("selected_tenses")
    @classmethod
    def _normalize_create_tenses(cls, value: list[str]) -> list[str]:
        from app.services.tenses import normalize_tense_keys

        return normalize_tense_keys(value)


class LanguageProfileResponse(BaseModel):
    id: UUID
    native_lang: str
    learning_lang: str
    cefr_level: str
    selected_tenses: list[str]
    is_active: bool
    last_used_at: datetime | None

    model_config = {"from_attributes": True}

    @field_validator("selected_tenses")
    @classmethod
    def _normalize_response_tenses(cls, value: list[str]) -> list[str]:
        from app.services.tenses import normalize_tense_keys

        return normalize_tense_keys(value)


class LanguageProfileUpdate(BaseModel):
    cefr_level: str | None = None
    selected_tenses: list[str] | None = None

    @field_validator("selected_tenses")
    @classmethod
    def _normalize_update_tenses(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        from app.services.tenses import normalize_tense_keys

        return normalize_tense_keys(value)


class LookupRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    profile_id: UUID


class LookupCandidate(BaseModel):
    lemma: str
    pos: str | None
    gloss: str
    lexical_entry_id: UUID | None = None
    in_learning: bool = False
    is_favorite: bool = False
    learning_card_id: UUID | None = None
    list_id: UUID | None = None
    list_name: str | None = None
    enrichment_status: str | None = None


class LookupResponse(BaseModel):
    candidates: list[LookupCandidate]
    source: str


class WordListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile_id: UUID


class WordListUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WordListResponse(BaseModel):
    id: UUID
    name: str
    is_system: bool
    word_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class WordListAddWordRequest(BaseModel):
    lemma: str
    pos: str | None = None
    gloss: str | None = None
    lexical_entry_id: UUID | None = None
    profile_id: UUID


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


class CardContent(BaseModel):
    schema_version: str = "1.0"
    lemma: str
    language: str
    pos: str | None = None
    ipa: str | None = None
    meanings: list[dict] = Field(default_factory=list)
    synonyms_l2: list[dict | str] = Field(default_factory=list)
    antonyms_l2: list[dict | str] = Field(default_factory=list)
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

    model_config = {"from_attributes": True}


class FavoriteCreate(BaseModel):
    lemma: str
    pos: str | None = None
    gloss: str | None = None
    profile_id: UUID


class FavoriteResponse(BaseModel):
    id: UUID
    lemma: str
    pos: str | None
    gloss: str | None
    created_at: datetime
    enrichment_status: str = "ready"

    model_config = {"from_attributes": True}


class SrsQueueItem(BaseModel):
    card_id: UUID
    lemma_l2: str
    gloss_primary: str | None
    content: dict
    status: str
    direction: str | None = None


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


class SyncCardItem(BaseModel):
    id: UUID
    profile_id: UUID
    deck_id: UUID | None = None
    lemma_l2: str
    pos: str | None = None
    gloss_primary: str | None = None
    content: dict
    enrichment_status: str = "ready"
    updated_at: datetime | None = None
    srs: SyncSrsState | None = None


class SyncPullResponse(BaseModel):
    server_time: datetime
    settings: UserSettingsResponse
    cards: list[SyncCardItem]
    deleted_card_ids: list[UUID] = []


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


class SyncPushRequest(BaseModel):
    reviews: list[SyncReviewItem] = Field(default_factory=list)


class SyncPushResponse(BaseModel):
    applied: int
    skipped: int
    srs: list[SyncSrsState] = []
