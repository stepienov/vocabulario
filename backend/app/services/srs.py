"""FSRS (Free Spaced Repetition Scheduler) — harmonogram powtórek."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fsrs import Card, Rating, Scheduler
from fsrs import State as FsrsState

from app.models import SrsState

GRADE_AGAIN = "again"
GRADE_HARD = "hard"
GRADE_GOOD = "good"
GRADE_EASY = "easy"

# Stare oceny z UI / logów → FSRS
_LEGACY_GRADES = {
    "know_well": GRADE_EASY,  # dawne „Umiem”
}

_RATING = {
    GRADE_AGAIN: Rating.Again,
    GRADE_HARD: Rating.Hard,
    GRADE_GOOD: Rating.Good,
    GRADE_EASY: Rating.Easy,
}

# Domyślne wagi FSRS-6 (py-fsrs) — te same ustawiamy w Android `LocalFsrs`.
_scheduler = Scheduler()


def normalize_grade(grade: str) -> str:
    return _LEGACY_GRADES.get(grade, grade)


def _to_rating(grade: str, correct: bool) -> Rating:
    if not correct:
        return Rating.Again
    return _RATING.get(normalize_grade(grade), Rating.Good)


def _status_from_fsrs(fsrs_state: FsrsState) -> str:
    if fsrs_state == FsrsState.Review:
        return "review"
    if fsrs_state == FsrsState.Relearning:
        return "relearning"
    return "learning"


def _fsrs_state_from_status(status: str) -> FsrsState:
    if status == "review":
        return FsrsState.Review
    if status == "relearning":
        return FsrsState.Relearning
    return FsrsState.Learning


def _card_from_db(state: SrsState, now: datetime) -> Card:
    """Odtwórz kartę FSRS ze stanu w DB (lub świeżą, gdy never reviewed)."""
    if state.status == "new" or state.stability is None:
        return Card(due=now)

    fsrs_state = _fsrs_state_from_status(state.status)
    step = None if fsrs_state == FsrsState.Review else (state.fsrs_step or 0)
    return Card(
        state=fsrs_state,
        step=step,
        stability=float(state.stability),
        difficulty=float(state.difficulty) if state.difficulty is not None else 5.0,
        due=state.next_review_at or now,
        last_review=state.last_reviewed_at,
    )


def _seed_from_legacy(state: SrsState, now: datetime) -> Card:
    """Przybliżona migracja starych kart SM-2 → FSRS przy pierwszej ocenie po upgrade."""
    if state.status == "new" or state.next_review_at is None:
        return Card(due=now)
    interval = max(float(state.interval_days or 0), 0.1)
    # ease 1.3..3.0 → difficulty ~7..1 (im łatwiej, tym niższa D)
    ease = float(state.ease or 2.5)
    difficulty = max(1.0, min(10.0, 11.0 - ease * 2.5))
    fsrs_state = (
        FsrsState.Review
        if state.status == "review"
        else FsrsState.Learning
    )
    return Card(
        state=fsrs_state,
        step=None if fsrs_state == FsrsState.Review else 0,
        stability=interval,
        difficulty=difficulty,
        due=state.next_review_at,
        last_review=state.last_reviewed_at
        or (state.next_review_at - timedelta(days=interval)),
    )


def apply_review(
    state: SrsState,
    grade: str,
    correct: bool,
    reviewed_at: datetime | None = None,
) -> SrsState:
    now = reviewed_at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    rating = _to_rating(grade, correct)
    stored_grade = GRADE_AGAIN if not correct else normalize_grade(grade)

    if state.stability is None and state.status in ("learning", "review") and state.interval_days:
        card = _seed_from_legacy(state, now)
    else:
        card = _card_from_db(state, now)

    card, _log = _scheduler.review_card(card, rating, review_datetime=now)

    state.stability = card.stability
    state.difficulty = card.difficulty
    state.fsrs_step = card.step
    state.status = _status_from_fsrs(card.state)
    state.next_review_at = card.due
    state.last_reviewed_at = card.last_review or now
    state.last_grade = stored_grade

    if card.last_review and card.due:
        state.interval_days = max(
            0.0,
            (card.due - card.last_review).total_seconds() / 86400.0,
        )
    if rating == Rating.Again:
        state.lapses = (state.lapses or 0) + 1
    state.repetitions = (state.repetitions or 0) + 1
    # ease zostawiamy jako przybliżenie dla starych ekranów / kompatybilności
    if card.difficulty is not None:
        state.ease = max(1.3, min(3.0, (11.0 - float(card.difficulty)) / 2.5))

    return state
