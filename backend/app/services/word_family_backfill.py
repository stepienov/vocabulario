"""Jednorazowy backfill rodzin z istniejącego JSON — bez LLM.

Hasła z cache’u trafiają do jednej rodziny tylko przy krawędzi dwukierunkowej.
Krewni bez własnego LexicalEntry wiszą na rodzinie tego, kto ich wymienił.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import LanguageProfile, LearningCard, LexicalEntry, WordFamily, WordFamilyMember
from app.services.pos_normalize import normalize_pos_bucket
from app.services.word_families import _project_family, project_family_items
from app.services.word_family_quality import (
    MAX_FAMILY_MEMBERS,
    filter_word_family,
    member_key,
    merge_related_lists,
)

logger = logging.getLogger(__name__)

MemberKey = tuple[str, str]


def parse_lang_pair(pair: str) -> tuple[str, str]:
    native, sep, learning = (pair or "").partition(">")
    if not sep or not learning:
        return "", (pair or "").strip().lower()
    return native.strip().lower(), learning.strip().lower()


def learning_lang_of(pair: str) -> str:
    return parse_lang_pair(pair)[1]


def _is_lemma_entry(content: dict | None, pos: str | None) -> bool:
    data = content or {}
    kind = str(data.get("entry_kind") or "lemma").strip().lower()
    if kind != "lemma":
        return False
    bucket = normalize_pos_bucket(data.get("pos") or pos)
    return bucket not in {"phrase", "construction", "unknown"}


def _normalize_item(raw: dict) -> dict | None:
    lemma = str(raw.get("lemma") or "").strip()
    pos = normalize_pos_bucket(raw.get("pos"))
    if not lemma or pos == "unknown":
        return None
    article = raw.get("article")
    return {
        "lemma": lemma,
        "pos": pos,
        "article": article if isinstance(article, str) and article.strip() else None,
        "gloss_l1": str(raw.get("gloss_l1") or raw.get("gloss") or "").strip() or "?",
    }


@dataclass
class PreparedEntry:
    entry_id: UUID
    lang_pair: str
    head: dict
    head_key: MemberKey
    relatives: list[dict]
    relative_keys: set[MemberKey]
    extra_antonyms: list[dict]


@dataclass
class FamilyPlan:
    lang_pair: str
    members: list[dict]
    entry_ids: list[UUID]
    antonyms_by_entry: dict[UUID, list[dict]] = field(default_factory=dict)


@dataclass
class BackfillReport:
    lang_pair: str
    entries_seen: int = 0
    skipped_non_lemma: int = 0
    families: int = 0
    members: int = 0
    singleton_skipped: int = 0
    cards_patched: int = 0
    orphan_cards_patched: int = 0
    examples: list[str] = field(default_factory=list)


def prepare_entry(
    entry_id: UUID,
    lang_pair: str,
    content: dict,
    pos: str | None = None,
) -> PreparedEntry | None:
    if not _is_lemma_entry(content, pos):
        return None
    lemma = str(content.get("lemma") or "").strip()
    head_pos = normalize_pos_bucket(content.get("pos") or pos)
    key = member_key(lemma, head_pos)
    if key is None:
        return None
    meanings = content.get("meanings") or []
    gloss = ""
    if meanings and isinstance(meanings[0], dict):
        gloss = str(meanings[0].get("gloss_l1") or "").strip()
    head = {
        "lemma": lemma,
        "pos": head_pos,
        "article": None,
        "gloss_l1": gloss or "?",
    }
    raw_family: list[dict] = []
    for item in content.get("word_family_l2") or []:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_item(item)
        if normalized:
            raw_family.append(normalized)
    learning = learning_lang_of(lang_pair)
    existing_ant = [
        x for x in (content.get("antonyms_l2") or []) if isinstance(x, dict)
    ]
    relatives, antonyms = filter_word_family(
        lemma, head_pos, raw_family, existing_ant, learning
    )
    extra = [
        item
        for item in antonyms
        if (item.get("lemma") or "").casefold()
        not in {(a.get("lemma") or "").casefold() for a in existing_ant}
    ]
    rel_keys: set[MemberKey] = set()
    kept: list[dict] = []
    for item in relatives:
        rk = member_key(item.get("lemma"), item.get("pos"))
        if rk is None or rk == key:
            continue
        rel_keys.add(rk)
        kept.append(item)
    return PreparedEntry(
        entry_id=entry_id,
        lang_pair=lang_pair,
        head=head,
        head_key=key,
        relatives=kept,
        relative_keys=rel_keys,
        extra_antonyms=extra,
    )


class _UnionFind:
    def __init__(self, keys: list[MemberKey]) -> None:
        self.parent = {k: k for k in keys}

    def find(self, key: MemberKey) -> MemberKey:
        parent = self.parent[key]
        if parent != key:
            self.parent[key] = self.find(parent)
        return self.parent[key]

    def union(self, a: MemberKey, b: MemberKey) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _merge_member(into: dict[MemberKey, dict], item: dict, rank: int) -> None:
    key = member_key(item.get("lemma"), item.get("pos"))
    if key is None:
        return
    existing = into.get(key)
    if existing is None:
        row = dict(item)
        row["rank"] = rank
        into[key] = row
        return
    existing["rank"] = min(int(existing.get("rank") or rank), rank)
    gloss = item.get("gloss_l1") or ""
    if gloss and gloss != "?" and (existing.get("gloss_l1") in {"", "?"}):
        existing["gloss_l1"] = gloss
    if item.get("article") and not existing.get("article"):
        existing["article"] = item["article"]


def build_family_plans(prepared: list[PreparedEntry]) -> list[FamilyPlan]:
    if not prepared:
        return []
    lang_pair = prepared[0].lang_pair
    by_key: dict[MemberKey, PreparedEntry] = {}
    for item in prepared:
        by_key.setdefault(item.head_key, item)

    uf = _UnionFind(list(by_key.keys()))
    for item in by_key.values():
        for rel_key in item.relative_keys:
            other = by_key.get(rel_key)
            if other is None:
                continue
            if item.head_key in other.relative_keys:
                uf.union(item.head_key, rel_key)

    groups: dict[MemberKey, list[PreparedEntry]] = defaultdict(list)
    for item in by_key.values():
        groups[uf.find(item.head_key)].append(item)

    claimed_dangling: set[MemberKey] = set()
    plans: list[FamilyPlan] = []
    for cluster in sorted(groups.values(), key=len, reverse=True):
        members: dict[MemberKey, dict] = {}
        antonyms_by_entry: dict[UUID, list[dict]] = {}
        rank = 0
        for item in cluster:
            _merge_member(members, item.head, rank)
            rank += 1
            if item.extra_antonyms:
                antonyms_by_entry[item.entry_id] = item.extra_antonyms
            for rel in item.relatives:
                rel_key = member_key(rel.get("lemma"), rel.get("pos"))
                if rel_key is None:
                    continue
                if rel_key in by_key and uf.find(rel_key) != uf.find(item.head_key):
                    continue
                if rel_key not in by_key:
                    if rel_key in claimed_dangling:
                        continue
                    claimed_dangling.add(rel_key)
                _merge_member(members, rel, rank)
                rank += 1
        ordered = sorted(
            members.values(),
            key=lambda m: (int(m.get("rank") or 0), (m.get("lemma") or "").casefold()),
        )[:MAX_FAMILY_MEMBERS]
        if len(ordered) < 2:
            continue
        plans.append(
            FamilyPlan(
                lang_pair=lang_pair,
                members=ordered,
                entry_ids=[item.entry_id for item in cluster],
                antonyms_by_entry=antonyms_by_entry,
            )
        )
    return plans


def family_example(plan: FamilyPlan) -> str:
    lemmas = [str(m.get("lemma") or "") for m in plan.members[:6]]
    return f"{plan.lang_pair}: {', '.join(lemmas)}" + (
        "…" if len(plan.members) > 6 else ""
    )


def apply_extra_antonyms(content: dict, extra: list[dict]) -> dict:
    if not extra:
        return content
    current = [x for x in (content.get("antonyms_l2") or []) if isinstance(x, dict)]
    merged = merge_related_lists(current, extra)
    if merged == current:
        return content
    out = dict(content)
    out["antonyms_l2"] = merged
    return out


async def _wipe_lang_pair_families(db: AsyncSession, lang_pair: str) -> int:
    result = await db.execute(select(WordFamily).where(WordFamily.lang_pair == lang_pair))
    families = list(result.scalars().all())
    count = len(families)
    entries = await db.execute(
        select(LexicalEntry).where(
            LexicalEntry.lang_pair == lang_pair,
            LexicalEntry.word_family_id.is_not(None),
        )
    )
    for entry in entries.scalars().all():
        entry.word_family_id = None
    for family in families:
        await db.delete(family)
    await db.flush()
    return count


async def persist_family_plans(
    db: AsyncSession,
    plans: list[FamilyPlan],
    *,
    entries_by_id: dict[UUID, LexicalEntry],
) -> tuple[int, int]:
    cards_patched = 0
    now = datetime.now(UTC)
    for plan in plans:
        family = WordFamily(id=uuid4(), lang_pair=plan.lang_pair)
        db.add(family)
        await db.flush()
        for index, item in enumerate(plan.members):
            key = member_key(item.get("lemma"), item.get("pos"))
            if key is None:
                continue
            db.add(
                WordFamilyMember(
                    id=uuid4(),
                    family_id=family.id,
                    lang_pair=plan.lang_pair,
                    lemma_key=key[0],
                    lemma=str(item["lemma"]),
                    pos=key[1],
                    article=item.get("article"),
                    gloss_l1=item.get("gloss_l1") or "?",
                    rank=int(item.get("rank") or index),
                )
            )
        await db.flush()
        for entry_id in plan.entry_ids:
            entry = entries_by_id.get(entry_id)
            if entry is None:
                continue
            entry.word_family_id = family.id
            extra = plan.antonyms_by_entry.get(entry_id) or []
            if extra:
                content = apply_extra_antonyms(dict(entry.content or {}), extra)
                entry.content = content
                flag_modified(entry, "content")
        await db.flush()
        await _project_family(db, family)
        await db.flush()
        cards_result = await db.execute(
            select(LearningCard).where(
                LearningCard.lexical_entry_id.in_(plan.entry_ids),
                LearningCard.deleted_at.is_(None),
            )
        )
        for card in cards_result.scalars().all():
            card.updated_at = now
            cards_patched += 1
    return len(plans), cards_patched


async def patch_orphan_cards(
    db: AsyncSession,
    lang_pair: str,
    member_family: dict[MemberKey, UUID],
    family_members: dict[UUID, list[WordFamilyMember]],
) -> int:
    native, learning = parse_lang_pair(lang_pair)
    if not native or not learning:
        return 0
    result = await db.execute(
        select(LearningCard, LanguageProfile)
        .join(LanguageProfile, LanguageProfile.id == LearningCard.profile_id)
        .where(
            LearningCard.deleted_at.is_(None),
            LearningCard.lexical_entry_id.is_(None),
            LanguageProfile.app_lang == native,
            LanguageProfile.learning_lang == learning,
        )
    )
    patched = 0
    now = datetime.now(UTC)
    for card, _profile in result.all():
        key = member_key(card.lemma_l2, card.pos or (card.content or {}).get("pos"))
        if key is None:
            continue
        family_id = member_family.get(key)
        if family_id is None:
            continue
        members = family_members.get(family_id) or []
        content = dict(card.content or {})
        lemma = content.get("lemma") or card.lemma_l2
        pos = content.get("pos") or card.pos
        content["word_family_l2"] = project_family_items(members, lemma, pos)
        card.content = content
        flag_modified(card, "content")
        card.updated_at = now
        patched += 1
    return patched


async def load_prepared_entries(
    db: AsyncSession,
    lang_pair: str,
    *,
    limit: int | None = None,
) -> tuple[list[PreparedEntry], dict[UUID, LexicalEntry], int, int]:
    stmt = select(LexicalEntry).where(LexicalEntry.lang_pair == lang_pair)
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = list((await db.execute(stmt)).scalars().all())
    prepared: list[PreparedEntry] = []
    by_id: dict[UUID, LexicalEntry] = {}
    skipped = 0
    for entry in rows:
        by_id[entry.id] = entry
        item = prepare_entry(
            entry.id, entry.lang_pair, dict(entry.content or {}), entry.pos
        )
        if item is None:
            skipped += 1
            continue
        prepared.append(item)
    return prepared, by_id, len(rows), skipped


async def backfill_lang_pair(
    db: AsyncSession,
    lang_pair: str,
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> BackfillReport:
    prepared, by_id, seen, skipped = await load_prepared_entries(
        db, lang_pair, limit=limit
    )
    plans = build_family_plans(prepared)
    in_plans = {eid for plan in plans for eid in plan.entry_ids}
    report = BackfillReport(
        lang_pair=lang_pair,
        entries_seen=seen,
        skipped_non_lemma=skipped,
        families=len(plans),
        members=sum(len(p.members) for p in plans),
        singleton_skipped=sum(1 for item in prepared if item.entry_id not in in_plans),
        examples=[family_example(p) for p in plans[:8]],
    )
    if dry_run:
        entry_ids = [eid for p in plans for eid in p.entry_ids]
        if entry_ids:
            count = await db.execute(
                select(LearningCard.id).where(
                    LearningCard.lexical_entry_id.in_(entry_ids),
                    LearningCard.deleted_at.is_(None),
                )
            )
            report.cards_patched = len(list(count.scalars().all()))
        return report

    await _wipe_lang_pair_families(db, lang_pair)
    _families, cards_patched = await persist_family_plans(
        db, plans, entries_by_id=by_id
    )
    report.cards_patched = cards_patched

    member_rows = list(
        (
            await db.execute(
                select(WordFamilyMember).where(WordFamilyMember.lang_pair == lang_pair)
            )
        ).scalars().all()
    )
    member_family = {
        (m.lemma_key, normalize_pos_bucket(m.pos)): m.family_id for m in member_rows
    }
    family_members: dict[UUID, list[WordFamilyMember]] = defaultdict(list)
    for member in member_rows:
        family_members[member.family_id].append(member)
    report.orphan_cards_patched = await patch_orphan_cards(
        db, lang_pair, member_family, family_members
    )
    await db.commit()
    return report


async def list_lang_pairs(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(select(LexicalEntry.lang_pair).distinct().order_by(LexicalEntry.lang_pair))
    ).scalars().all()
    return [p for p in rows if p]
