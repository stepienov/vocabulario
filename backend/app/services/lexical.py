import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import lang_pair_key, normalize_text
from app.models import LanguageProfile, LearningCard, LexicalEntry, LookupQueryCache, User
from app.services.llm import LLMService
from app.services.enrichment import enrich_card_content
from app.services.lookup_candidates import (
    append_lookup_candidates,
    gloss_query_score,
    normalize_lookup_query,
    rank_lookup_candidates,
    sanitize_lookup_candidates,
    token_similarity,
)
from app.services.pos_normalize import normalize_pos_bucket
from app.services.similar_words import ensure_similar_words
from app.services.word_persistence import (
    EphemeralLexicalEntry,
    build_ephemeral_entry,
    words_persistence_enabled,
)


LexicalEntryLike = LexicalEntry | EphemeralLexicalEntry


@dataclass(frozen=True)
class LookupOutcome:
    candidates: list[dict]
    source: str
    ai_complete: bool


def lexical_entry_for_candidate(
    by_key: dict[tuple[str, str], LexicalEntry],
    lemma: str,
    pos: str | None,
) -> LexicalEntry | None:
    """Resolve a cached entry by lemma + POS only — never fall back to another POS."""
    bucket = normalize_pos_bucket(pos)
    if bucket == "unknown":
        return None
    return by_key.get((normalize_text(lemma), bucket))


def _card_matches_lookup(
    card: LearningCard,
    lemma_norm: str,
    pos: str | None,
    lexical_entry_id: str | None,
) -> bool:
    if normalize_text(card.lemma_l2) != lemma_norm:
        return False
    want = normalize_pos_bucket(pos)
    got = normalize_pos_bucket(card.pos)
    if want != "unknown" and got != "unknown" and want != got:
        return False
    if lexical_entry_id and card.lexical_entry_id:
        if str(card.lexical_entry_id) == str(lexical_entry_id):
            return want == "unknown" or got == "unknown" or want == got
    if want == "unknown" or got == "unknown":
        return False
    return want == got


def _normalize_import_headword(raw: str) -> str:
    """Quizlet często dokleja (e:i)/(o:ue) — walidacja exact tego nie lubi."""
    t = (raw or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s*\(([eo]):[ieu]+\)\s*", " ", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()




class LexicalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = LLMService()


    async def get_profile(self, user_id: UUID, profile_id: UUID) -> LanguageProfile:
        result = await self.db.execute(
            select(LanguageProfile).where(
                LanguageProfile.id == profile_id,
                LanguageProfile.user_id == user_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError("Profile not found")
        return profile


    async def search_db(
        self, text: str, profile: LanguageProfile
    ) -> list[LexicalEntry]:
        if not words_persistence_enabled():
            return []
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        norm = normalize_text(text)
        pattern = f"%{norm}%"
        result = await self.db.execute(
            select(LexicalEntry).where(
                LexicalEntry.lang_pair == pair,
                or_(
                    LexicalEntry.lemma_l2.ilike(pattern),
                    LexicalEntry.lemma_l1_primary.ilike(pattern),
                ),
            ).limit(10)
        )
        return list(result.scalars().all())


    async def _annotate_candidates(
        self, user_id: UUID, profile_id: UUID, candidates: list[dict]
    ) -> list[dict]:
        if not words_persistence_enabled():
            return [
                {
                    **c,
                    "in_learning": False,
                    "learning_card_id": None,
                    "list_id": None,
                    "list_name": None,
                }
                for c in candidates
            ]

        from app.models import WordList
        from app.services.word_lists import ensure_system_list

        await ensure_system_list(self.db, user_id, profile_id)

        cards_result = await self.db.execute(
            select(LearningCard).where(
                LearningCard.user_id == user_id,
                LearningCard.profile_id == profile_id,
                LearningCard.deleted_at.is_(None),
            )
        )
        cards = list(cards_result.scalars().all())
        lists_result = await self.db.execute(
            select(WordList).where(
                WordList.profile_id == profile_id,
                WordList.deleted_at.is_(None),
            )
        )
        lists_by_id = {wl.id: wl for wl in lists_result.scalars().all()}

        annotated = []
        for c in candidates:
            lemma_norm = normalize_text(c["lemma"])
            pos = c.get("pos")
            learning_card = next(
                (
                    card
                    for card in cards
                    if _card_matches_lookup(card, lemma_norm, pos, c.get("lexical_entry_id"))
                ),
                None,
            )
            list_id = None
            list_name = None
            if learning_card is not None:
                if learning_card.deck_id is None:
                    system = next((wl for wl in lists_by_id.values() if wl.is_system), None)
                    list_id = str(system.id) if system else None
                    list_name = system.name if system else "Uczę się"
                else:
                    wl = lists_by_id.get(learning_card.deck_id)
                    if wl is not None:
                        list_id = str(learning_card.deck_id)
                        list_name = wl.name
                    else:
                        # Lista usunięta / niedostępna — nie pokazuj starego chipa.
                        learning_card = None
            annotated.append(
                {
                    "lemma": c["lemma"],
                    "pos": c.get("pos"),
                    "gloss": c.get("gloss", ""),
                    "lexical_entry_id": c.get("lexical_entry_id"),
                    "in_learning": learning_card is not None and learning_card.deck_id is None,
                    "learning_card_id": str(learning_card.id) if learning_card else None,
                    "list_id": list_id,
                    "list_name": list_name,
                    "enrichment_status": (
                        learning_card.enrichment_status if learning_card is not None else None
                    ),
                }
            )
        return annotated

    async def _attach_lexical_ids(
        self, profile: LanguageProfile, candidates: list[dict]
    ) -> list[dict]:
        """Attach DB ids by exact lemma without returning entry content."""
        if not candidates or not words_persistence_enabled():
            return candidates
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        lemmas = [normalize_text(c["lemma"]) for c in candidates if c.get("lemma")]
        if not lemmas:
            return candidates
        from sqlalchemy import func

        result = await self.db.execute(
            select(LexicalEntry).where(
                LexicalEntry.lang_pair == pair,
                func.lower(LexicalEntry.lemma_l2).in_(lemmas),
            )
        )
        by_key: dict[tuple[str, str], LexicalEntry] = {}
        for entry in result.scalars().all():
            bucket = normalize_pos_bucket(entry.pos)
            if bucket == "unknown":
                continue
            by_key[(normalize_text(entry.lemma_l2), bucket)] = entry
        out = []
        for c in candidates:
            entry = lexical_entry_for_candidate(by_key, c.get("lemma") or "", c.get("pos"))
            out.append(
                {
                    **c,
                    "lexical_entry_id": str(entry.id) if entry else c.get("lexical_entry_id"),
                }
            )
        return out

    def _raw_to_candidates(self, raw: list[dict]) -> list[dict]:
        return [
            {
                "lemma": c.get("lemma", ""),
                "pos": c.get("pos"),
                "gloss": c.get("gloss", ""),
                "lexical_entry_id": None,
            }
            for c in raw
            if c.get("lemma")
        ]

    def _rank_lookup_candidates(
        self, candidates: list[dict], text: str, *, learning_lang: str
    ) -> list[dict]:
        # High recall: only drop malformed forms (sanitize), then RANK. We never
        # discard a plausible reading — a missing suggestion is worse than an extra one.
        candidates = sanitize_lookup_candidates(
            candidates, learning_lang=learning_lang
        )
        return rank_lookup_candidates(candidates, text, learning_lang=learning_lang)

    async def _fuzzy_l1_db_candidates(
        self, profile: LanguageProfile, text: str
    ) -> list[dict]:
        """Recover L1 typos against known glosses for this language pair."""
        q = normalize_text(text)
        if not q or len(q) < 3:
            return []
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        rows: list[tuple[str, str | None, str, str | None]] = []

        if words_persistence_enabled():
            result = await self.db.execute(
                select(LexicalEntry).where(LexicalEntry.lang_pair == pair).limit(800)
            )
            for entry in result.scalars().all():
                l1 = (entry.lemma_l1_primary or "").strip()
                if not l1:
                    continue
                rows.append((entry.lemma_l2, entry.pos, l1, str(entry.id)))

        card_result = await self.db.execute(
            select(LearningCard).where(
                LearningCard.profile_id == profile.id,
                LearningCard.user_id == profile.user_id,
            ).limit(400)
        )
        for card in card_result.scalars().all():
            gloss = (card.gloss_primary or "").strip()
            if not gloss:
                meanings = (card.content or {}).get("meanings") or []
                if meanings and isinstance(meanings[0], dict):
                    gloss = (meanings[0].get("gloss_l1") or "").strip()
            if not gloss:
                continue
            rows.append(
                (card.lemma_l2, card.pos, gloss, str(card.lexical_entry_id) if card.lexical_entry_id else None)
            )

        scored: list[tuple[float, dict]] = []
        for lemma, pos, gloss, lex_id in rows:
            primary = re.split(r"[,;/]", gloss)[0].strip()
            score = max(
                gloss_query_score(gloss, q),
                token_similarity(q, primary),
            )
            if score < 0.78:
                continue
            scored.append(
                (
                    score,
                    {
                        "lemma": lemma,
                        "pos": pos,
                        "gloss": primary or gloss,
                        "lexical_entry_id": lex_id,
                    },
                )
            )
        scored.sort(key=lambda t: -t[0])
        out: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for _, item in scored:
            key = (
                normalize_text(item["lemma"]),
                normalize_pos_bucket(item.get("pos")),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= 6:
                break
        return out

    async def _db_first_candidates(
        self, profile: LanguageProfile, text: str
    ) -> list[dict]:
        """Ranked candidates built purely from the shared PostgreSQL lexicon (no AI)."""
        entries = await self.search_db(text, profile)
        if not entries:
            return []
        cands = [
            {
                "lemma": e.lemma_l2,
                "pos": e.pos,
                "gloss": e.lemma_l1_primary or "",
                "lexical_entry_id": str(e.id),
            }
            for e in entries
        ]
        return self._rank_lookup_candidates(
            cands, text, learning_lang=profile.learning_lang
        )

    def _query_cache_key(self, text: str) -> str:
        return normalize_lookup_query(text) or (text.strip().casefold()[:200] or "_")

    async def _fetch_query_cache(
        self, lang_pair: str, input_norm: str, *, for_update: bool = False
    ) -> LookupQueryCache | None:
        stmt = select(LookupQueryCache).where(
            LookupQueryCache.lang_pair == lang_pair,
            LookupQueryCache.input_norm == input_norm,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _ensure_query_cache_row(
        self, lang_pair: str, input_norm: str
    ) -> LookupQueryCache:
        await self.db.execute(
            pg_insert(LookupQueryCache)
            .values(
                id=uuid4(),
                lang_pair=lang_pair,
                input_norm=input_norm,
                candidates=[],
                ai_complete=False,
                hit_count=0,
            )
            .on_conflict_do_nothing(index_elements=["lang_pair", "input_norm"])
        )
        row = await self._fetch_query_cache(lang_pair, input_norm, for_update=True)
        if row is None:
            raise RuntimeError("lookup_query_cache row missing after insert")
        return row

    async def _present_lookup(
        self,
        user: User,
        profile: LanguageProfile,
        text: str,
        stored: list[dict],
        source: str,
        ai_complete: bool,
    ) -> LookupOutcome:
        ranked = self._rank_lookup_candidates(
            stored, text, learning_lang=profile.learning_lang
        )
        attached = await self._attach_lexical_ids(profile, ranked)
        annotated = await self._annotate_candidates(user.id, profile.id, attached)
        return LookupOutcome(annotated, source, ai_complete)

    async def lookup_cached(
        self, user: User, profile_id: UUID, text: str
    ) -> LookupOutcome:
        """Read-only query cache. Does not call OpenAI or create a row on miss."""
        profile = await self.get_profile(user.id, profile_id)
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        key = self._query_cache_key(text)
        row = await self._fetch_query_cache(pair, key)
        if row is None:
            return LookupOutcome([], "db", False)
        row.hit_count = (row.hit_count or 0) + 1
        return await self._present_lookup(
            user,
            profile,
            text,
            list(row.candidates or []),
            "db",
            bool(row.ai_complete),
        )

    async def lookup_expand(
        self, user: User, profile_id: UUID, text: str
    ) -> LookupOutcome:
        """Ask OpenAI for new suggestions, append to cache, return the full ranked list."""
        profile = await self.get_profile(user.id, profile_id)
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        key = self._query_cache_key(text)

        existing = await self._fetch_query_cache(pair, key)
        if existing is not None and existing.ai_complete:
            existing.hit_count = (existing.hit_count or 0) + 1
            return await self._present_lookup(
                user,
                profile,
                text,
                list(existing.candidates or []),
                "db",
                True,
            )

        already = list(existing.candidates or []) if existing is not None else []
        raw = await self.llm.lookup_expand(
            text,
            profile.app_lang,
            profile.learning_lang,
            profile.cefr_level,
            already,
        )
        incoming = self._raw_to_candidates(raw)

        row = await self._ensure_query_cache_row(pair, key)
        if row.ai_complete:
            row.hit_count = (row.hit_count or 0) + 1
            return await self._present_lookup(
                user,
                profile,
                text,
                list(row.candidates or []),
                "db",
                True,
            )

        merged, added = append_lookup_candidates(
            list(row.candidates or []),
            incoming,
            learning_lang=profile.learning_lang,
        )
        row.candidates = merged
        flag_modified(row, "candidates")
        if added == 0:
            row.ai_complete = True
        row.hit_count = (row.hit_count or 0) + 1
        row.updated_at = datetime.now(UTC)
        await self.db.flush()
        return await self._present_lookup(
            user, profile, text, merged, "ai", bool(row.ai_complete)
        )

    async def lookup(self, user: User, profile_id: UUID, text: str) -> LookupOutcome:
        """Full path for offline flush / one-shot clients: cache if complete, else expand."""
        cached = await self.lookup_cached(user, profile_id, text)
        if cached.ai_complete:
            return cached
        return await self.lookup_expand(user, profile_id, text)

    async def best_lookup_candidate(
        self, user: User, profile_id: UUID, text: str
    ) -> dict | None:
        """Top-ranked lookup reading for offline-queued headwords (L1 or L2)."""
        outcome = await self.lookup(user, profile_id, text)
        return outcome.candidates[0] if outcome.candidates else None

    async def _exact_db_entry(
        self, profile: LanguageProfile, text: str
    ) -> LexicalEntry | None:
        if not words_persistence_enabled():
            return None
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        from app.services.card_jobs import find_ready_entry

        cached = await find_ready_entry(
            db=self.db,
            lang_pair=pair,
            lemma=text,
            pos=None,
            learning_lang=profile.learning_lang,
        )
        if cached is not None:
            return cached
        return None

    async def _validate_one(
        self, user: User, profile: LanguageProfile, raw: str
    ) -> dict | None:
        """Accept only exact L1/L2 headword — never typo autocorrect."""
        text = raw.strip()
        if not text or len(text) > 80:
            return None
        norm = normalize_text(text)
        db_entry = await self._exact_db_entry(profile, text)
        if db_entry is not None:
            return {
                "input": text,
                "lemma": db_entry.lemma_l2,
                "pos": db_entry.pos,
                "gloss": db_entry.lemma_l1_primary or "",
                "lexical_entry_id": str(db_entry.id),
            }
        raw_cands = await self.llm.lookup(
            text, profile.app_lang, profile.learning_lang, profile.cefr_level
        )
        candidates = sanitize_lookup_candidates(
            [
                {
                    "lemma": c.get("lemma", ""),
                    "pos": c.get("pos"),
                    "gloss": c.get("gloss", ""),
                    "lexical_entry_id": None,
                }
                for c in raw_cands
                if c.get("lemma")
            ],
            learning_lang=profile.learning_lang,
        )
        for c in candidates:
            lemma_n = normalize_text(c["lemma"])
            gloss_n = normalize_text(c.get("gloss") or "")
            # Exact L2 or exact L1 gloss — reject AI "corrections" of typos
            if lemma_n == norm or gloss_n == norm:
                attached = await self._attach_lexical_ids(profile, [c])
                hit = attached[0]
                return {
                    "input": text,
                    "lemma": hit["lemma"],
                    "pos": hit.get("pos"),
                    "gloss": hit.get("gloss") or "",
                    "lexical_entry_id": hit.get("lexical_entry_id"),
                }
        return None

    async def validate_import_words(
        self, user: User, profile_id: UUID, words: list[str]
    ) -> tuple[list[dict], list[str]]:
        profile = await self.get_profile(user.id, profile_id)
        # preserve order, dedupe by normalized form
        seen: set[str] = set()
        ordered: list[str] = []
        for w in words:
            t = _normalize_import_headword(w)
            if not t:
                continue
            key = normalize_text(t)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(t)

        sem = asyncio.Semaphore(4)

        async def run_one(word: str) -> tuple[str, dict | None]:
            async with sem:
                try:
                    return word, await self._validate_one(user, profile, word)
                except Exception:
                    return word, None

        results = await asyncio.gather(*(run_one(w) for w in ordered))
        valid: list[dict] = []
        invalid: list[str] = []
        for word, hit in results:
            if hit is None:
                invalid.append(word)
            else:
                valid.append(hit)
        return valid, invalid

    async def _enrich_ephemeral(
        self,
        profile: LanguageProfile,
        lemma: str,
        pos: str | None,
    ) -> EphemeralLexicalEntry:
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        content = await enrich_card_content(profile, lemma, pos)
        gloss = ""
        meanings = content.get("meanings", [])
        if meanings:
            gloss = meanings[0].get("gloss_l1", "")
        return build_ephemeral_entry(
            lang_pair=pair,
            lemma_l2=content.get("lemma", lemma),
            lemma_l1_primary=gloss,
            pos=content.get("pos", pos),
            content=content,
            cefr=profile.cefr_level,
        )

    async def get_or_create_entry(
        self,
        user: User,
        profile: LanguageProfile,
        lemma: str,
        pos: str | None,
        lexical_entry_id: UUID | None,
    ) -> LexicalEntryLike:
        if not words_persistence_enabled():
            return await self._enrich_ephemeral(profile, lemma, pos)

        pair = lang_pair_key(profile.app_lang, profile.learning_lang)

        if lexical_entry_id:
            result = await self.db.execute(
                select(LexicalEntry).where(
                    LexicalEntry.id == lexical_entry_id,
                    LexicalEntry.lang_pair == pair,
                )
            )
            entry = result.scalar_one_or_none()
            if entry:
                want = normalize_pos_bucket(pos)
                got = normalize_pos_bucket(entry.pos)
                if want == "unknown" or got == "unknown" or want == got:
                    entry.usage_count += 1
                    return entry

        from app.services.card_jobs import apply_lexical_keys, find_ready_entry

        existing = await find_ready_entry(
            db=self.db,
            lang_pair=pair,
            lemma=lemma,
            pos=pos,
            learning_lang=profile.learning_lang,
        )
        if existing:
            existing.usage_count += 1
            return existing

        content = await enrich_card_content(profile, lemma, pos)
        gloss = ""
        meanings = content.get("meanings", [])
        if meanings:
            gloss = meanings[0].get("gloss_l1", "")

        entry = LexicalEntry(
            lang_pair=pair,
            lemma_l2=content.get("lemma", lemma),
            lemma_l1_primary=gloss,
            pos=content.get("pos", pos),
            cefr=profile.cefr_level,
            content=content,
            source="ai",
            created_by_user_id=user.id,
            usage_count=1,
        )
        apply_lexical_keys(entry)
        self.db.add(entry)
        await self.db.flush()
        return entry

