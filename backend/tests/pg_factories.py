"""Wiersze do testów na lokalnym Postgresie."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import LanguageProfile, LearningCard, SrsState, User, WordList


async def create_user(session: AsyncSession, *, email: str | None = None) -> User:
    user = User(email=email or f"pg-{uuid4()}@test.com", role="user")
    session.add(user)
    await session.flush()
    return user


async def create_profile(
    session: AsyncSession,
    user: User,
    app_lang: str,
    learning_lang: str,
) -> LanguageProfile:
    profile = LanguageProfile(
        user_id=user.id,
        app_lang=app_lang,
        learning_lang=learning_lang,
    )
    session.add(profile)
    await session.flush()
    return profile


async def create_list(session: AsyncSession, profile: LanguageProfile, name: str) -> WordList:
    word_list = WordList(user_id=profile.user_id, profile_id=profile.id, name=name)
    session.add(word_list)
    await session.flush()
    return word_list


async def create_card(
    session: AsyncSession,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    status: str = "pending",
    content: dict | None = None,
    deck_id=None,
) -> LearningCard:
    card = LearningCard(
        user_id=profile.user_id,
        profile_id=profile.id,
        deck_id=deck_id,
        lemma_l2=lemma,
        pos=pos,
        content={} if content is None else content,
        enrichment_status=status,
    )
    session.add(card)
    await session.flush()
    if deck_id is None:
        session.add(SrsState(card_id=card.id, scope="main", status="new"))
        await session.flush()
    return card


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}
