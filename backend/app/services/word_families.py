"""Kanoniczna rodzina wyrazów — źródło prawdy w tabelach, JSON karty to projekcja."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import lang_pair_key
from app.lsp.lang_utils import articles_for
from app.models import LanguageProfile, LearningCard, LexicalEntry, WordFamily, WordFamilyMember
from app.services.pos_normalize import normalize_pos_bucket
from app.services.related_articles import (
    attach_article,
    drop_related_missing_articles,
    lift_article_from_lemma,
    related_needs_article,
)
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


def _learning_lang_from_pair(lang_pair: str | None) -> str | None:
    if not lang_pair or ">" not in lang_pair:
        return None
    return lang_pair.split(">", 1)[1].strip() or None


def _lemma_variants_for_members(
    members: list[WordFamilyMember],
    learning_lang: str | None,
) -> set[str]:
    """Formy lemma_l2 na karcie: naga i z rodzajnikiem."""
    out: set[str] = set()
    arts = articles_for(learning_lang)
    for member in members:
        for raw in (member.lemma, member.lemma_key):
            text = str(raw or "").strip()
            if text:
                out.add(text)
        stem = str(member.lemma_key or "").strip()
        if not stem:
            continue
        for art in arts:
            out.add(f"{art} {stem}")
    return out


def _lift_item_article(
    item: dict,
    learning_lang: str | None,
    extra_lemma: str | None = None,
) -> dict:
    """Copy/lift a citation article from lemma text. Never invent from gender."""
    lemma = str(item.get("lemma") or "").strip()
    pos = item.get("pos")
    attached = attach_article(
        {"lemma": lemma, "pos": pos, "gloss_l1": item.get("gloss_l1") or "?"},
        item.get("article"),
        learning_lang,
    )
    if not (attached.get("article") or "").strip() and extra_lemma:
        extra = attach_article(
            {"lemma": str(extra_lemma).strip(), "pos": pos},
            None,
            learning_lang,
        )
        if extra.get("article"):
            attached["article"] = extra["article"]
            if lift_article_from_lemma(lemma, learning_lang)[0]:
                attached["lemma"] = extra["lemma"]
            else:
                attached["lemma"] = lemma or extra["lemma"]
    out = dict(item)
    out["lemma"] = attached["lemma"]
    out["article"] = attached.get("article")
    return out


def _head_item(content: dict, learning_lang: str | None = None) -> dict | None:
    lemma = content.get("lemma")
    pos = normalize_pos_bucket(content.get("pos"))
    if not lemma or pos == "unknown":
        return None
    meanings = content.get("meanings") or []
    gloss = ""
    if meanings and isinstance(meanings[0], dict):
        gloss = str(meanings[0].get("gloss_l1") or "").strip()
    return _lift_item_article(
        {
            "lemma": lemma,
            "pos": pos,
            "article": content.get("article"),
            "gloss_l1": gloss or "?",
        },
        learning_lang,
    )


def _candidate_items(content: dict, learning_lang: str | None = None) -> list[dict]:
    head = _head_item(content, learning_lang)
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
            _lift_item_article(
                {
                    "lemma": raw["lemma"],
                    "pos": pos,
                    "article": raw.get("article"),
                    "gloss_l1": raw.get("gloss_l1") or "?",
                },
                learning_lang,
            )
        )
    return items


def _keys_of(items: list[dict]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in items:
        key = member_key(item.get("lemma"), item.get("pos"))
        if key:
            out.add(key)
    return out


def citation_articles_from_content(
    content: dict | None,
    learning_lang: str | None,
) -> dict[tuple[str, str], str]:
    """Rodzajniki już znane na karcie (hasło / synonimy / antonimy / rodzina)."""
    found: dict[tuple[str, str], str] = {}
    data = content or {}
    head = _head_item(data, learning_lang)
    bucket = [head] if head else []
    for key in ("synonyms_l2", "antonyms_l2", "word_family_l2"):
        for raw in data.get(key) or []:
            if not isinstance(raw, dict) or not raw.get("lemma"):
                continue
            pos = normalize_pos_bucket(raw.get("pos"))
            if pos == "unknown":
                continue
            bucket.append(
                _lift_item_article(
                    {
                        "lemma": raw["lemma"],
                        "pos": pos,
                        "article": raw.get("article"),
                        "gloss_l1": raw.get("gloss_l1") or "?",
                    },
                    learning_lang,
                )
            )
    for item in bucket:
        art = str(item.get("article") or "").strip()
        if not art:
            continue
        key = member_key(item.get("lemma"), item.get("pos"))
        if key:
            found[key] = art
    return found


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
    sample = rows[0] if rows else (members[0] if members else None)
    learning = _learning_lang_from_pair(getattr(sample, "lang_pair", None) if sample else None)
    items = [
        related_item_from_member(
            lemma=m.lemma,
            pos=m.pos,
            article=m.article,
            gloss_l1=m.gloss_l1,
        )
        for m in rows[:MAX_FAMILY_MEMBERS]
    ]
    return drop_related_missing_articles(items, learning)


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
    *,
    adopt: bool = False,
    require_article: bool = True,
) -> WordFamilyMember | None:
    key = member_key(item.get("lemma"), item.get("pos"))
    if key is None:
        return None
    item = _lift_item_article(item, _learning_lang_from_pair(family.lang_pair))
    lemma_key, pos = key
    lang = _learning_lang_from_pair(family.lang_pair)
    existing = await _member_row(db, family.lang_pair, lemma_key, pos)
    incoming_article = str(item.get("article") or "").strip()
    if existing is not None:
        if item.get("gloss_l1") and item["gloss_l1"] != "?":
            existing.gloss_l1 = item["gloss_l1"]
        if incoming_article:
            existing.article = incoming_article
        if item.get("lemma"):
            existing.lemma = str(item["lemma"])
        if existing.family_id != family.id:
            if adopt:
                old_family = await db.get(WordFamily, existing.family_id)
                existing.family_id = family.id
                await db.flush()
                if old_family is not None:
                    await _delete_empty_family(db, old_family)
                return existing
            return None
        return existing
    if require_article and related_needs_article(item, lang):
        return None
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


async def _apply_known_articles(
    db: AsyncSession,
    lang_pair: str,
    articles: dict[tuple[str, str], str],
) -> set[UUID]:
    """Dopisz rodzajnik do kanonicznego wiersza, gdy już gdzieś jest na karcie."""
    touched: set[UUID] = set()
    for (lemma_key, pos), article in articles.items():
        art = str(article or "").strip()
        if not art:
            continue
        existing = await _member_row(db, lang_pair, lemma_key, pos)
        if existing is None or str(existing.article or "").strip():
            continue
        existing.article = art
        touched.add(existing.family_id)
    return touched


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

    learning = _learning_lang_from_pair(family.lang_pair)
    for member in members:
        key = member_key(member.lemma, member.pos)
        entry = entry_by_key.get(key) if key else None
        extra = None
        if entry is not None:
            extra = entry.lemma_l2 or (entry.content or {}).get("lemma")
        lifted = _lift_item_article(
            {
                "lemma": member.lemma,
                "pos": member.pos,
                "article": member.article,
                "gloss_l1": member.gloss_l1,
            },
            learning,
            extra_lemma=extra,
        )
        member.lemma = lifted["lemma"]
        member.article = lifted.get("article")

    for entry in entry_by_key.values():
        content = dict(entry.content or {})
        lemma = content.get("lemma") or entry.lemma_l2
        pos = content.get("pos") or entry.pos
        content["word_family_l2"] = project_family_items(members, lemma, pos)
        entry.content = content
        flag_modified(entry, "content")

    member_keys = {(m.lemma_key, normalize_pos_bucket(m.pos)) for m in members}
    native, _, learning_code = family.lang_pair.partition(">")
    cards: list[LearningCard] = []
    lemma_variants = _lemma_variants_for_members(members, learning)
    entry_ids = [e.id for e in entry_by_key.values()]
    if native and learning_code and member_keys:
        profile_ids = list(
            (
                await db.execute(
                    select(LanguageProfile.id).where(
                        LanguageProfile.app_lang == native,
                        LanguageProfile.learning_lang == learning_code,
                    )
                )
            ).scalars().all()
        )
        if profile_ids:
            matchers = []
            if entry_ids:
                matchers.append(LearningCard.lexical_entry_id.in_(entry_ids))
            if lemma_variants:
                matchers.append(LearningCard.lemma_l2.in_(lemma_variants))
            if matchers:
                cards = list(
                    (
                        await db.execute(
                            select(LearningCard).where(
                                LearningCard.profile_id.in_(profile_ids),
                                LearningCard.deleted_at.is_(None),
                                or_(*matchers),
                            )
                        )
                    ).scalars().all()
                )
    for card in cards:
        key = member_key(card.lemma_l2 or (card.content or {}).get("lemma"), card.pos)
        if not key or key not in member_keys:
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
    entry: LexicalEntry | None = None,
) -> dict:
    """Dołącza hasło do kanonicznej rodziny i zapisuje projekcję w JSON."""
    if (content.get("entry_kind") or "lemma") != "lemma":
        return content
    pos = normalize_pos_bucket(content.get("pos") or (entry.pos if entry is not None else None))
    if pos in {"phrase", "construction", "unknown"}:
        return content

    pair = lang_pair_key(profile.app_lang, profile.learning_lang)
    learning = profile.learning_lang
    candidates = _candidate_items(content, learning)
    head = _head_item(content, learning)
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
            if entry is not None:
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

    await _add_member(
        db,
        target,
        head,
        rank=0 if not members_now else next_rank,
        require_article=False,
    )
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
    if entry is not None:
        entry.word_family_id = target.id
    await db.flush()
    known = citation_articles_from_content(content, learning)
    extra_families = await _apply_known_articles(db, pair, known)
    await db.flush()
    projected: set[UUID] = set()
    for fid in {target.id, *extra_families}:
        fam = target if fid == target.id else await db.get(WordFamily, fid)
        if fam is None or fid in projected:
            continue
        await _project_family(db, fam)
        projected.add(fid)
    await db.flush()
    members = await _load_members(db, target.id)
    out = dict(content)
    out["word_family_l2"] = project_family_items(
        members, out.get("lemma") or head.get("lemma"), out.get("pos") or head.get("pos")
    )
    if entry is not None:
        entry.content = out
        flag_modified(entry, "content")
    return out


def _card_content_for_family(card: LearningCard) -> dict:
    content = dict(card.content or {})
    if not content.get("lemma"):
        content["lemma"] = card.lemma_l2
    if not content.get("pos"):
        content["pos"] = card.pos
    return content


async def _entry_for_card(db: AsyncSession, card: LearningCard) -> LexicalEntry | None:
    if card.lexical_entry_id is None:
        return None
    return await db.get(LexicalEntry, card.lexical_entry_id)


async def _seed_family_from_citing_cards(
    db: AsyncSession,
    profile: LanguageProfile,
    card: LearningCard,
    head: dict,
    head_key: tuple[str, str],
) -> None:
    """Jeśli inna karta tego profilu już wymienia to hasło — zapisz jej rodzinę i dołącz hasło."""
    pair = lang_pair_key(profile.app_lang, profile.learning_lang)
    cards = list(
        (
            await db.execute(
                select(LearningCard).where(
                    LearningCard.profile_id == profile.id,
                    LearningCard.deleted_at.is_(None),
                )
            )
        ).scalars().all()
    )
    for other in cards:
        if other.id == card.id:
            continue
        content = other.content or {}
        if not content.get("word_family_l2"):
            continue
        items = _candidate_items(content, profile.learning_lang)
        if head_key not in _keys_of(items):
            continue
        entry = await _entry_for_card(db, other)
        synced = await sync_word_family(db, profile, dict(content), entry)
        other.content = synced
        flag_modified(other, "content")
        other.updated_at = _now()
        citing_head = _head_item(synced, profile.learning_lang)
        citing_key = (
            member_key(citing_head.get("lemma"), citing_head.get("pos"))
            if citing_head
            else member_key(other.lemma_l2, other.pos)
        )
        citing_row = (
            await _member_row(db, pair, citing_key[0], citing_key[1])
            if citing_key
            else None
        )
        if citing_row is None:
            return
        family = await db.get(WordFamily, citing_row.family_id)
        if family is None:
            return
        members_now = await _load_members(db, family.id)
        next_rank = max((m.rank for m in members_now), default=-1) + 1
        await _add_member(
            db,
            family,
            head,
            rank=next_rank,
            adopt=True,
            require_article=False,
        )
        await db.flush()
        return


async def attach_card_to_word_family(
    db: AsyncSession,
    profile: LanguageProfile,
    card: LearningCard,
    *,
    source_card: LearningCard | None = None,
) -> None:
    """Dołącza nową kartę do znanej rodziny: plus z pokrewnych albo zapis w tabeli."""
    content = _card_content_for_family(card)
    if (content.get("entry_kind") or "lemma") != "lemma":
        return
    head = _head_item(content, profile.learning_lang)
    if head is None:
        return
    head_key = member_key(head.get("lemma"), head.get("pos"))
    if head_key is None:
        return

    if source_card is not None:
        source_content = _card_content_for_family(source_card)
        source_entry = await _entry_for_card(db, source_card)
        synced_source = await sync_word_family(db, profile, source_content, source_entry)
        source_card.content = synced_source
        flag_modified(source_card, "content")
        source_card.updated_at = _now()
        source_head = _head_item(synced_source, profile.learning_lang)
        source_key = (
            member_key(source_head.get("lemma"), source_head.get("pos"))
            if source_head
            else member_key(source_card.lemma_l2, source_card.pos)
        )
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        source_row = (
            await _member_row(db, pair, source_key[0], source_key[1])
            if source_key
            else None
        )
        if source_row is not None:
            family = await db.get(WordFamily, source_row.family_id)
            if family is not None:
                members_now = await _load_members(db, family.id)
                next_rank = max((m.rank for m in members_now), default=-1) + 1
                await _add_member(
                    db,
                    family,
                    head,
                    rank=next_rank,
                    adopt=True,
                    require_article=False,
                )
                await db.flush()
                await _project_family(db, family)
                members = await _load_members(db, family.id)
                content["word_family_l2"] = project_family_items(
                    members, head.get("lemma"), head.get("pos")
                )
                card.content = content
                flag_modified(card, "content")
                card.updated_at = _now()
                return

    await _seed_family_from_citing_cards(db, profile, card, head, head_key)
    entry = await _entry_for_card(db, card)
    synced = await sync_word_family(db, profile, content, entry)
    card.content = synced
    flag_modified(card, "content")
    card.updated_at = _now()


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
    flag_modified(entry, "content")


@dataclass
class FillArticlesReport:
    lang_pair: str
    members_needing: int = 0
    members_filled: int = 0
    families_projected: int = 0
    examples: list[str] = field(default_factory=list)


async def _citation_catalog_for_pair(db: AsyncSession, lang_pair: str) -> dict[tuple[str, str], str]:
    learning = _learning_lang_from_pair(lang_pair)
    catalog: dict[tuple[str, str], str] = {}
    entries = (
        await db.execute(select(LexicalEntry).where(LexicalEntry.lang_pair == lang_pair))
    ).scalars().all()
    for entry in entries:
        catalog.update(citation_articles_from_content(entry.content or {}, learning))
        lifted = _lift_item_article(
            {
                "lemma": entry.lemma_l2,
                "pos": entry.pos,
                "article": (entry.content or {}).get("article"),
            },
            learning,
        )
        art = str(lifted.get("article") or "").strip()
        key = member_key(lifted.get("lemma") or entry.lemma_l2, lifted.get("pos") or entry.pos)
        if art and key:
            catalog[key] = art
    native, _, learning_code = lang_pair.partition(">")
    if native and learning_code:
        profile_ids = list(
            (
                await db.execute(
                    select(LanguageProfile.id).where(
                        LanguageProfile.app_lang == native,
                        LanguageProfile.learning_lang == learning_code,
                    )
                )
            ).scalars().all()
        )
        if profile_ids:
            cards = (
                await db.execute(
                    select(LearningCard).where(
                        LearningCard.profile_id.in_(profile_ids),
                        LearningCard.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            for card in cards:
                catalog.update(citation_articles_from_content(card.content or {}, learning))
                lifted = _lift_item_article(
                    {"lemma": card.lemma_l2, "pos": card.pos, "article": None},
                    learning,
                )
                art = str(lifted.get("article") or "").strip()
                key = member_key(lifted.get("lemma") or card.lemma_l2, lifted.get("pos") or card.pos)
                if art and key:
                    catalog[key] = art
    return catalog


async def fill_missing_family_articles(
    db: AsyncSession,
    lang_pair: str,
    *,
    dry_run: bool = True,
) -> FillArticlesReport:
    """Uzupełnij puste rodzajniki członków z cytacji już obecnych w JSON."""
    learning = _learning_lang_from_pair(lang_pair)
    members = list(
        (
            await db.execute(
                select(WordFamilyMember).where(WordFamilyMember.lang_pair == lang_pair)
            )
        ).scalars().all()
    )
    needing = [
        m
        for m in members
        if related_needs_article({"pos": m.pos, "article": m.article}, learning)
    ]
    report = FillArticlesReport(lang_pair=lang_pair, members_needing=len(needing))
    if not needing:
        return report
    catalog = await _citation_catalog_for_pair(db, lang_pair)
    family_ids: set[UUID] = set()
    for member in needing:
        key = (member.lemma_key, normalize_pos_bucket(member.pos))
        article = catalog.get(key)
        if not article:
            continue
        report.members_filled += 1
        family_ids.add(member.family_id)
        if len(report.examples) < 12:
            report.examples.append(f"{member.lemma} ({member.pos}) -> {article}")
        if not dry_run:
            member.article = article
    if dry_run:
        report.families_projected = len(family_ids)
        return report
    await db.flush()
    for fid in family_ids:
        family = await db.get(WordFamily, fid)
        if family is None:
            continue
        await _project_family(db, family)
        report.families_projected += 1
    await db.flush()
    return report
