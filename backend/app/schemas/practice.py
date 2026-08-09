from uuid import UUID

from pydantic import BaseModel, Field


class CheckAnswerRequest(BaseModel):
    card_id: str
    answer: str
    direction: str


class CheckAnswerResponse(BaseModel):
    correct: bool
    expected: str | None = None
    accepted_as_typo: bool = False


class ChoiceOption(BaseModel):
    text: str
    lemma_l2: str | None = None
    gloss: str | None = None
    pos: str | None = None
    card_id: UUID | None = None
    in_learning: bool = False
    is_correct: bool = False


class DistractorsRequest(BaseModel):
    card_id: UUID
    profile_id: UUID
    direction: str


class DistractorsResponse(BaseModel):
    options: list[ChoiceOption]
    direction: str
