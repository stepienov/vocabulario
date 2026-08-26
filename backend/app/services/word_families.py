"""Kanoniczna rodzina wyrazów — źródło prawdy w tabelach, JSON karty to projekcja."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import lang_pair_key
from app.models import LanguageProfile, LearningCard, LexicalEntry, WordFamily, WordFamilyMember
from app.services.pos_normalize import normalize_pos_bucket
from app.services.word_family_quality import (
    MAX_FAMILY_MEMBERS,
    POS_TIEBREAK,
    belongs_in_family,
    is_same_member,
    member_key,
    related_item_from_member,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _head_item(content: dict) -> dict | None:
    lemma = content.get("lemma")
    pos = normalize_pos_bucket(content.get("pos"))
    if not lemma or pos == "unknown":
        return None
    meanings = content.get("meanings") or []
    gloss = ""
    if meanings and isinstance(meanings[0], dict):
        gloss = str(meanings[0].get("gloss_l1") or "").strip()
    return {
        "lemma": lemma,
        "pos": pos,
        "article": None,
        "gloss_l1": gloss or "?",
    }


def _candidate_items(content: dict) -> list[dict]:
    head = _head_item(content)
    items: list[dict] = []
    if head:
        items.append(head)
    for raw in content.get("word_family_l2") or []:
        if not isinstance(raw, dict) or not raw.get("lemma"):
            continue
        pos = normalize_pos_bucket(raw.get("pos"))
        if pos == "unknown":
            continue
        items.append(
            {
                "lemma": raw["lemma"],
                "pos": pos,
                "article": raw.get("article"),
                "gloss_l1": raw.get("gloss_l1") or "?",
            }
        )
    return items


def _keys_of(items: list[dict]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in items:
        key = member_key(item.get("lemma"), item.get("pos"))
        if key:
            out.add(key)
    return out


def project_family_items(
    members: list[WordFamilyMember],
    exclude_lemma: str | None,
    exclude_pos: str | None,
) -> list[dict]:
    rows = [
        m
        for m in members
        if not is_same_member(m.lemma, m.pos, exclude_lemma, exclude_pos)
    ]
    rows.sort(
        key=lambda m: (
            m.rank,
            POS_TIEBREAK.get(normalize_pos_bucket(m.pos), 9),
            (m.lemma or "").casefold(),
        )
    )
    return [
        related_item_from_member(
            lemma=m.lemma,
            pos=m.pos,
            article=m.article,
            gloss_l1=m.gloss_l1,
        )
        for m in rows[:MAX_FAMILY_MEMBERS]
    ]


async def _load_members(db: AsyncSession, family_id: UUID) -> list[WordFamilyMember]:
    result = await db.execute(
        select(WordFamilyMember).where(WordFamilyMember.family_id == family_id)
    )
    return list(result.scalars().all())


async def _families_for_keys(
    db: AsyncSession,
    lang_pair: str,
    keys: set[tuple[str, str]],
    *,
    conversion_stems: set[str] | None = None,
) -> list[WordFamily]:
    conversion = conversion_stems or set()
    lemma_keys = {k[0] for k in keys} | conversion
    if not lemma_keys:
        return []
    result = await db.execute(
        select(WordFamilyMember).where(
            WordFamilyMember.lang_pair == lang_pair,
            WordFamilyMember.lemma_key.in_(lemma_keys),
        )
    )
    family_ids: set[UUID] = set()
    for member in result.scalars().all():
        key = (member.lemma_key, normalize_pos_bucket(member.pos))
        if key in keys or member.lemma_key in conversion:
            family_ids.add(member.family_id)
    if not family_ids:
        return []
    families = await db.execute(select(WordFamily).where(WordFamily.id.in_(family_ids)))
    return list(families.scalars().all())


async def _member_row(
    db: AsyncSession, lang_pair: str, lemma_key: str, pos: str
) -> WordFamilyMember | None:
    result = await db.execute(
        select(WordFamilyMember).where(
            WordFamilyMember.lang_pair == lang_pair,
            WordFamilyMember.lemma_key == lemma_key,
            WordFamilyMember.pos == pos,
        )
    )
    return result.scalars().first()


async def _delete_empty_family(db: AsyncSession, family: WordFamily) -> None:
    members = await _load_members(db, family.id)
    if members:
        return
    await db.delete(family)


async def _trim_members(db: AsyncSession, family_id: UUID, keep_key: tuple[str, str] | None) -> None:
    members = await _load_members(db, family_id)
    if len(members) <= MAX_FAMILY_MEMBERS:
        return
    members.sort(
        key=lambda m: (
            m.rank,
            POS_TIEBREAK.get(normalize_pos_bucket(m.pos), 9),
            (m.lemma or "").casefold(),
        )
    )
    keep: list[WordFamilyMember] = []
    overflow: list[WordFamilyMember] = []
    for member in members:
        key = (member.lemma_key, normalize_pos_bucket(member.pos))
        if keep_key and key == keep_key:
            keep.append(member)
            continue
        overflow.append(member)
    room = max(0, MAX_FAMILY_MEMBERS - len(keep))
    keep.extend(overflow[:room])
    keep_ids = {m.id for m in keep}
    for member in members:
        if member.id not in keep_ids:
            await db.delete(member)


async def _add_member(
    db: AsyncSession,
    family: WordFamily,
    item: dict,
    rank: int,
) -> WordFamilyMember | None:
    key = member_key(item.get("lemma"), item.get("pos"))
    if key is None:
        return None
    lemma_key, pos = key
    existing = await _member_row(db, family.lang_pair, lemma_key, pos)
    if existing is not None:
        if existing.family_id != family.id:
            return None
        if item.get("gloss_l1") and item["gloss_l1"] != "?":
            existing.gloss_l1 = item["gloss_l1"]
        if item.get("article"):
            existing.article = item["article"]
        if item.get("lemma"):
            existing.lemma = str(item["lemma"])
        return existing
    member = WordFamilyMember(
        id=uuid4(),
        family_id=family.id,
        lang_pair=family.lang_pair,
        lemma_key=lemma_key,
        lemma=str(item["lemma"]),
        pos=pos,
        article=item.get("article"),
        gloss_l1=item.get("gloss_l1") or "?",
        rank=rank,
    )
    db.add(member)
    await db.flush()
    return member


async def _project_family(db: AsyncSession, family: WordFamily) -> None:
    members = await _load_members(db, family.id)
    family.updated_at = _now()
    result = await db.execute(
        select(LexicalEntry).where(LexicalEntry.word_family_id == family.id)
    )
    entries = list(result.scalars().all())
    entry_by_key: dict[tuple[str, str], LexicalEntry] = {}
    for entry in entries:
        key = member_key(entry.lemma_l2 or (entry.content or {}).get("lemma"), entry.pos)
        if key:
            entry_by_key[key] = entry

    lemma_keys = {m.lemma_key for m in members}
    extra_entries: list[LexicalEntry] = []
    if lemma_keys:
        extra = await db.execute(
            select(LexicalEntry).where(
                LexicalEntry.lang_pair == family.lang_pair,
                LexicalEntry.lemma_key_l2.in_(lemma_keys),
            )
        )
        extra_entries = list(extra.scalars().all())
    for entry in extra_entries:
        key = member_key(entry.lemma_l2 or (entry.content or {}).get("lemma"), entry.pos)
        if key and any(
            m.lemma_key == key[0] and normalize_pos_bucket(m.pos) == key[1] for m in members
        ):
            entry.word_family_id = family.id
            entry_by_key[key] = entry

    for entry in entry_by_key.values():
        content = dict(entry.content or {})
        lemma = content.get("lemma") or entry.lemma_l2
        pos = content.get("pos") or entry.pos
        content["word_family_l2"] = project_family_items(members, lemma, pos)
        entry.content = content
        flag_modified(entry, "content")

    entry_ids = [e.id for e in entry_by_key.values()]
    if not entry_ids:
        return
    cards_result = await db.execute(
        select(LearningCard).where(
            LearningCard.lexical_entry_id.in_(entry_ids),
            LearningCard.deleted_at.is_(None),
        )
    )
    by_entry = {e.id: e for e in entry_by_key.values()}
    for card in cards_result.scalars().all():
        entry = by_entry.get(card.lexical_entry_id) if card.lexical_entry_id else None
        if entry is None:
            continue
        content = dict(card.content or {})
        lemma = content.get("lemma") or card.lemma_l2
        pos = content.get("pos") or card.pos
        content["word_family_l2"] = project_family_items(members, lemma, pos)
        card.content = content
        flag_modified(card, "content")
        card.updated_at = _now()


async def sync_word_family(
    db: AsyncSession,
    profile: LanguageProfile,
    content: dict,
    entry: LexicalEntry,
) -> dict:
    """Dołącza hasło do kanonicznej rodziny i zapisuje projekcję w JSON."""
    if (content.get("entry_kind") or "lemma") != "lemma":
        return content
    pos = normalize_pos_bucket(content.get("pos") or entry.pos)
    if pos in {"phrase", "construction", "unknown"}:
        return content

    pair = lang_pair_key(profile.app_lang, profile.learning_lang)
    learning = profile.learning_lang
    candidates = _candidate_items(content)
    head = _head_item(content)
    if head is None:
        return content
    head_key = member_key(head.get("lemma"), head.get("pos"))
    if head_key is None:
        return content

    cand_keys = _keys_of(candidates)
    llm_relatives = [
        item
        for item in candidates
        if member_key(item.get("lemma"), item.get("pos")) != head_key
    ]
    relative_keys = _keys_of(llm_relatives)

    overlapping = await _families_for_keys(
        db, pair, cand_keys, conversion_stems={head_key[0]}
    )
    head_row = await _member_row(db, pair, head_key[0], head_key[1])
    head_family: WordFamily | None = None
    if head_row is not None:
        head_family = await db.get(WordFamily, head_row.family_id)

    if head_family is not None:
        existing_members = await _load_members(db, head_family.id)
        existing_other = {
            (m.lemma_key, normalize_pos_bucket(m.pos))
            for m in existing_members
            if (m.lemma_key, normalize_pos_bucket(m.pos)) != head_key
        }
        if relative_keys and not (relative_keys & existing_other):
            logger.info(
                "word family detach lemma=%r pair=%s",
                head.get("lemma"),
                pair,
            )
            await db.delete(head_row)
            await db.flush()
            await _delete_empty_family(db, head_family)
            head_family = None
            overlapping = await _families_for_keys(
                db, pair, cand_keys, conversion_stems={head_key[0]}
            )

    target: WordFamily | None = head_family
    if target is None and overlapping:
        scored: list[tuple[int, WordFamily]] = []
        for family in overlapping:
            members = await _load_members(db, family.id)
            member_keys = {(m.lemma_key, normalize_pos_bucket(m.pos)) for m in members}
            scored.append((len(cand_keys & member_keys), family))
        scored.sort(key=lambda row: row[0], reverse=True)
        best_score, best = scored[0]
        if len(scored) == 1:
            target = best
        elif best_score >= 2:
            target = best
        elif head_key in {
            (m.lemma_key, normalize_pos_bucket(m.pos))
            for m in await _load_members(db, best.id)
        } or relative_keys & {
            (m.lemma_key, normalize_pos_bucket(m.pos))
            for m in await _load_members(db, best.id)
        }:
            # Jedna krawędź (hasło wymienia członka albo już tam jest) — dołącz,
            # ale nie spajaj pozostałych rodzin.
            target = best

    if target is None:
        if not llm_relatives:
            content["word_family_l2"] = []
            entry.content = content
            flag_modified(entry, "content")
            return content
        target = WordFamily(id=uuid4(), lang_pair=pair)
        db.add(target)
        await db.flush()

    members_now = await _load_members(db, target.id)
    member_pairs = [(m.lemma, m.pos) for m in members_now] or [
        (head.get("lemma"), head.get("pos"))
    ]
    next_rank = max((m.rank for m in members_now), default=-1) + 1

    await _add_member(db, target, head, rank=0 if not members_now else next_rank)
    next_rank = max((m.rank for m in await _load_members(db, target.id)), default=-1) + 1

    for item in llm_relatives:
        if not belongs_in_family(
            item.get("lemma"), item.get("pos"), member_pairs, learning
        ):
            continue
        added = await _add_member(db, target, item, rank=next_rank)
        if added is not None and added.rank == next_rank:
            next_rank += 1
            member_pairs.append((item.get("lemma"), item.get("pos")))

    await _trim_members(db, target.id, keep_key=head_key)
    entry.word_family_id = target.id
    await db.flush()
    await _project_family(db, target)
    await db.flush()
    return dict(entry.content or content)


async def backfill_card_word_family(
    db: AsyncSession,
    profile: LanguageProfile,
    card: LearningCard,
) -> None:
    """Jednorazowe spięcie gotowej karty do kanonicznej rodziny (stare listy)."""
    if card.lexical_entry_id is None:
        return
    entry = await db.get(LexicalEntry, card.lexical_entry_id)
    if entry is None or entry.word_family_id is not None:
        return
    synced = await sync_word_family(db, profile, dict(entry.content or {}), entry)
    entry.content = synced
