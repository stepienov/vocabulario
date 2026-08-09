import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
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
    show_periphrases: Mapped[bool] = mapped_column(Boolean, default=True)
    show_conjugation: Mapped[bool] = mapped_column(Boolean, default=True)
    conjugation_expanded_default: Mapped[bool] = mapped_column(Boolean, default=False)
    show_example_sentences: Mapped[bool] = mapped_column(Boolean, default=True)
    related_words_expanded_default: Mapped[bool] = mapped_column(Boolean, default=False)
    study_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cards_ready_push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_hour: Mapped[int] = mapped_column(Integer, default=19)

    user: Mapped["User"] = relationship(back_populates="settings")


class LexicalEntry(Base):
    __tablename__ = "lexical_entries"
    __table_args__ = (UniqueConstraint("lang_pair", "lemma_l2", "pos"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lang_pair: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    lemma_l2: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lemma_l1_primary: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    pos: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cefr: Mapped[str | None] = mapped_column(String(8), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="ai")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningCard(Base):
    __tablename__ = "learning_cards"
    # Uniqueness only among live cards — soft-deleted rows are tombstones for sync.
    __table_args__ = (
        Index(
            "uq_learning_cards_active",
            "user_id",
            "profile_id",
            "lemma_l2",
            "pos",
            "deck_id",
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
    # pending → karta widoczna od razu, treść dociąga się w tle; ready → gotowa do nauki.
    enrichment_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    enrichment_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_review_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_activity_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    has_content_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Soft-delete tombstone: NULL = live, non-NULL = deleted (propagated via /sync/pull).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
