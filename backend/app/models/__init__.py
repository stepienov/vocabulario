import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profiles: Mapped[list["LanguageProfile"]] = relationship(back_populates="user")
    settings: Mapped["UserSettings | None"] = relationship(back_populates="user", uselist=False)
    cards: Mapped[list["LearningCard"]] = relationship(back_populates="user")


class LanguageProfile(Base):
    __tablename__ = "language_profiles"
    __table_args__ = (UniqueConstraint("user_id", "app_lang", "learning_lang"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    app_lang: Mapped[str] = mapped_column(String(8), nullable=False)
    learning_lang: Mapped[str] = mapped_column(String(8), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(8), default="A2")
    selected_tenses: Mapped[list] = mapped_column(JSONB, default=list)
    tense_label_lang: Mapped[str] = mapped_column(String(16), default="app_lang")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="profiles")
    cards: Mapped[list["LearningCard"]] = relationship(back_populates="profile")

    @property
    def native_lang(self) -> str:
        """Deprecated alias — use app_lang."""
        return self.app_lang

    @native_lang.setter
    def native_lang(self, value: str) -> None:
        self.app_lang = value


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    practice_input_pref: Mapped[str] = mapped_column(String(16), default="flashcard")
    practice_direction: Mapped[str] = mapped_column(String(16), default="l2_to_l1")
    typing_tolerance: Mapped[str] = mapped_column(String(16), default="tolerate")
    typo_modal_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    new_cards_per_day: Mapped[int] = mapped_column(Integer, default=20)
    theme: Mapped[str] = mapped_column(String(16), default="system")
    show_usages: Mapped[bool] = mapped_column(Boolean, default=True)
    show_synonyms_antonyms: Mapped[bool] = mapped_column(Boolean, default=True)
    show_synonyms: Mapped[bool] = mapped_column(Boolean, default=True)
    show_antonyms: Mapped[bool] = mapped_column(Boolean, default=True)
    show_word_family: Mapped[bool] = mapped_column(Boolean, default=True)
    show_associations: Mapped[bool] = mapped_column(Boolean, default=True)
    show_periphrases: Mapped[bool] = mapped_column(Boolean, default=True)
    show_conjugation: Mapped[bool] = mapped_column(Boolean, default=True)
    conjugation_expanded_default: Mapped[bool] = mapped_column(Boolean, default=False)
    show_example_sentences: Mapped[bool] = mapped_column(Boolean, default=True)
    related_words_expanded_default: Mapped[bool] = mapped_column(Boolean, default=False)
    study_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cards_ready_push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_hour: Mapped[int] = mapped_column(Integer, default=19)

    user: Mapped["User"] = relationship(back_populates="settings")


class WordFamily(Base):
    __tablename__ = "word_families"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lang_pair: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list["WordFamilyMember"]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )


class WordFamilyMember(Base):
    __tablename__ = "word_family_members"
    __table_args__ = (
        UniqueConstraint("family_id", "lemma_key", "pos"),
        UniqueConstraint("lang_pair", "lemma_key", "pos"),
        Index("ix_word_family_members_lookup", "lang_pair", "lemma_key", "pos"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("word_families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lang_pair: Mapped[str] = mapped_column(String(16), nullable=False)
    lemma_key: Mapped[str] = mapped_column(String(255), nullable=False)
    lemma: Mapped[str] = mapped_column(String(255), nullable=False)
    pos: Mapped[str] = mapped_column(String(32), nullable=False)
    article: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gloss_l1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    family: Mapped["WordFamily"] = relationship(back_populates="members")


class LexicalEntry(Base):
    __tablename__ = "lexical_entries"
    __table_args__ = (UniqueConstraint("lang_pair", "lemma_l2", "pos"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lang_pair: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    lemma_l2: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lemma_l1_primary: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lemma_key_l2: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lemma_key_l1: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    pos: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cefr: Mapped[str | None] = mapped_column(String(8), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="ai")
    word_family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("word_families.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LookupQueryCache(Base):
    """Shared lookup suggestions keyed by language pair + normalized user query."""

    __tablename__ = "lookup_query_cache"
    __table_args__ = (UniqueConstraint("lang_pair", "input_norm"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lang_pair: Mapped[str] = mapped_column(String(16), nullable=False)
    input_norm: Mapped[str] = mapped_column(String(200), nullable=False)
    candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ai_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    more_exhausted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningCard(Base):
    __tablename__ = "learning_cards"
    # Uniqueness only among live cards — soft-deleted rows are tombstones for sync.
    __table_args__ = (
        Index(
            "uq_learning_cards_live_lemma_pos",
            "user_id",
            "profile_id",
            "lemma_l2",
            "pos",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("language_profiles.id", ondelete="CASCADE"))
    deck_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    lexical_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lexical_entries.id", ondelete="SET NULL"), nullable=True
    )
    lemma_l2: Mapped[str] = mapped_column(String(255), nullable=False)
    pos: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gloss_primary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # pending → enrichment w toku; preparing → czeka na zaplanowany retry;
    # ready → gotowa; failed → 3 nieudane próby.
    enrichment_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    enrichment_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enrichment_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrichment_side_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrichment_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enrichment_auto_retry_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enrichment_manual_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_review_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_activity_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    has_content_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Soft-delete tombstone: NULL = live, non-NULL = deleted (propagated via /sync/pull).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lookup_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lookup_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="cards")
    profile: Mapped["LanguageProfile"] = relationship(back_populates="cards")
    srs_states: Mapped[list["SrsState"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SrsState(Base):
    __tablename__ = "srs_state"
    __table_args__ = (UniqueConstraint("card_id", "scope"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(64), default="main")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="new")
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # FSRS memory state (None = jeszcze nie oceniane / legacy)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_step: Mapped[int | None] = mapped_column(Integer, nullable=True)

    card: Mapped["LearningCard"] = relationship(back_populates="srs_states")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    grade: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Idempotency for offline sync push (client-generated UUID)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True, nullable=True)


class WordList(Base):
    """User word lists. System list 'Uczę się' maps to LearningCard.deck_id IS NULL."""

    __tablename__ = "word_lists"
    # Uniqueness only among live lists — soft-deleted names can be reused.
    __table_args__ = (
        Index(
            "uq_word_lists_profile_name_active",
            "profile_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("language_profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # Offline search inbox ("Oczekujące" / Pending) — one per profile; UI name is localized.
    is_pending_inbox: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Soft-delete tombstone (propagated via /sync/pull deleted_list_ids).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CardCorrection(Base):
    __tablename__ = "card_corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    sections: Mapped[list] = mapped_column(JSONB, nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="reported")
    result_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    patch: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CardHistoryEvent(Base):
    __tablename__ = "card_history_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(16), nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminCardReview(Base):
    __tablename__ = "admin_card_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    learning_lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    before_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_verdict: Mapped[str] = mapped_column(String(32), default="pending")
    ai_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    admin_status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminEscalation(Base):
    __tablename__ = "admin_escalations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    correction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("card_corrections.id", ondelete="CASCADE"), unique=True
    )
    user_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    sections: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reject_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    card_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    token: Mapped[str] = mapped_column(String(512), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(16), default="android")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppliedSyncMove(Base):
    """Idempotency + LWW for offline card moves (sync push)."""

    __tablename__ = "applied_sync_moves"

    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_cards.id", ondelete="CASCADE"))
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


ACTIVE_IMPORT_STATUSES = (
    "queued",
    "analyzing",
    "review",
    "committing",
    "cancelling",
)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        Index(
            "uq_import_jobs_one_active",
            "user_id",
            "profile_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued','analyzing','review','committing','cancelling')"
            ),
        ),
        Index("ix_import_jobs_user_created", "user_id", "created_at"),
        Index("ix_import_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("language_profiles.id", ondelete="CASCADE")
    )
    list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("word_lists.id", ondelete="CASCADE"))
    phase: Mapped[str] = mapped_column(String(16), default="analyze")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(16), default="queued")
    source_kind: Mapped[str] = mapped_column(String(16), default="paste")
    source_name: Mapped[str] = mapped_column(String(255), default="")
    mode: Mapped[str] = mapped_column(String(16), default="vocabulario")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    current_ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_attempt: Mapped[int] = mapped_column(Integer, default=0)
    ready_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    items: Mapped[list["ImportJobItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    events: Mapped[list["ImportJobEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class ImportJobItem(Base):
    __tablename__ = "import_job_items"
    __table_args__ = (UniqueConstraint("job_id", "ordinal"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_note: Mapped[list] = mapped_column(JSONB, default=list)
    input_label: Mapped[str] = mapped_column(String(500), default="")
    verdict: Mapped[str] = mapped_column(String(16), default="pending")
    verdict_phase: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    lemma: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pos: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gloss: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lexical_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    display: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    existing_card_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_card_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    job: Mapped["ImportJob"] = relationship(back_populates="items")


class ImportJobEvent(Base):
    __tablename__ = "import_job_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    level: Mapped[str] = mapped_column(String(8), default="info")
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    job: Mapped["ImportJob"] = relationship(back_populates="events")


class AppLog(Base):
    """Trwały dziennik operacji i błędów — niezależny od stanu encji."""

    __tablename__ = "app_logs"
    __table_args__ = (
        Index("ix_app_logs_created_at", "created_at"),
        Index("ix_app_logs_level_created", "level", "created_at"),
        Index("ix_app_logs_category_created", "category", "created_at"),
        Index("ix_app_logs_event_created", "event", "created_at"),
        Index("ix_app_logs_user_created", "user_id", "created_at"),
        Index("ix_app_logs_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="http")
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    http_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    traceback: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class LlmUsage(Base):
    """Per-call LLM token/cost meter. No FK to cards — rows outlive deletions."""

    __tablename__ = "llm_usage"
    __table_args__ = (
        Index("ix_llm_usage_created_at", "created_at"),
        Index("ix_llm_usage_operation_id", "operation_id"),
        Index("ix_llm_usage_lemma_pair", "lemma", "lang_pair"),
        Index("ix_llm_usage_purpose", "purpose"),
        Index("ix_llm_usage_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    operation_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    query: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lemma: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pos: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lang_pair: Mapped[str | None] = mapped_column(String(16), nullable=True)
    card_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    openai_response_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    pricing_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    lookup_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lookup_events.id", ondelete="SET NULL"), nullable=True, index=True
    )


class LlmCallPayload(Base):
    """Surowy request/response LLM — 1:1 z llm_usage, TTL 30 dni."""

    __tablename__ = "llm_call_payloads"

    llm_usage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_usage.id", ondelete="CASCADE"), primary_key=True
    )
    request_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LookupEvent(Base):
    """Per-user lookup history. Cache hits are recorded too (source=cached)."""

    __tablename__ = "lookup_events"
    __table_args__ = (
        Index("ix_lookup_events_created_at", "created_at"),
        Index("ix_lookup_events_user_created", "user_id", "created_at"),
        Index("ix_lookup_events_query_norm", "query_norm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    query_norm: Mapped[str] = mapped_column(String(200), nullable=False)
    lang_pair: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="lookup")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ai_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
