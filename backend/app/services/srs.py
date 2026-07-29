from datetime import UTC, datetime, timedelta

from app.models import SrsState

GRADE_HARD = "hard"
GRADE_EASY = "easy"
GRADE_KNOW_WELL = "know_well"

LEARNING_STEPS_MINUTES = [1, 10, 1440]


def apply_review(state: SrsState, grade: str, correct: bool) -> SrsState:
    now = datetime.now(UTC)

    if not correct:
        grade = GRADE_HARD
        state.lapses += 1
        state.status = "learning"
        state.repetitions = 0
        state.interval_days = 0
        state.ease = max(1.3, state.ease - 0.2)
        state.next_review_at = now + timedelta(minutes=LEARNING_STEPS_MINUTES[0])
        state.last_reviewed_at = now
        state.last_grade = grade
        return state

    if state.status == "new":
        state.status = "learning"
        state.repetitions = 0
        state.interval_days = 0
        state.next_review_at = now + timedelta(minutes=LEARNING_STEPS_MINUTES[0])
    elif state.status == "learning":
        step_idx = min(state.repetitions, len(LEARNING_STEPS_MINUTES) - 1)
        state.repetitions += 1
        if state.repetitions >= len(LEARNING_STEPS_MINUTES):
            state.status = "review"
            state.interval_days = 1
            state.next_review_at = now + timedelta(days=1)
        else:
            minutes = LEARNING_STEPS_MINUTES[step_idx]
            state.next_review_at = now + timedelta(minutes=minutes)
    else:
        if grade == GRADE_HARD:
            state.ease = max(1.3, state.ease - 0.15)
            state.interval_days = max(1, state.interval_days * 1.2)
        elif grade == GRADE_KNOW_WELL:
            state.ease = min(3.0, state.ease + 0.05)
            state.interval_days = state.interval_days * state.ease * 1.3
        else:
            state.interval_days = state.interval_days * state.ease

        state.interval_days = max(1, state.interval_days)
        state.repetitions += 1
        state.status = "review"
        state.next_review_at = now + timedelta(days=state.interval_days)

    state.last_reviewed_at = now
    state.last_grade = grade
    return state
