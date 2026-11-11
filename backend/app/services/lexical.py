import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import lang_pair_key, normalize_text
from app.core.lemma_keys import canonical_lemma
from app.models import LanguageProfile, LearningCard, LexicalEntry, LookupQueryCache, User
from app.services.llm import LLMService
from app.services.llm_usage import bind_llm_usage_context
from app.services.enrichment import enrich_card_content
from app.services.lookup_candidates import (
    LOOKUP_CACHE_LIMIT,
    append_lookup_candidates,
    candidate_is_confident,
    count_new_lookup_rows,
    drop_implausible_lookup_rows,
    gloss_query_score,
    letters_of_query,
    normalize_lookup_query,
    rank_category_candidates,
    rank_lookup_candidates,
    row_translates_its_word,
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


logger = logging.getLogger(__name__)

CATEGORY_QUERY_PREFIX = "cat:"


class AssocRoundNotReady(Exception):
    """Runda 2 albo 3, zanim poprzednia ósemka jest zapisana."""


def _assoc_words_and_meaning(candidates: list) -> tuple[list[dict], str]:
    words: list[dict] = []
    meaning = ""
    for item in candidates or []:
        if not isinstance(item, dict):
            continue
        saved = item.get("_meaning")
        if isinstance(saved, str) and saved.strip():
            meaning = saved.strip()
            continue
        if (item.get("lemma") or "").strip():
            words.append(item)
    return words, meaning


@dataclass(frozen=True)
class LookupOutcome:
    candidates: list[dict]
    source: str
    ai_complete: bool
    added: int | None = None
    cache_row_id: UUID | None = None
    lang_pair: str | None = None
    persist: bool = False
    suggestions_exhausted: bool = False
    headword_meaning: str = ""


@dataclass(frozen=True, slots=True)
class _LookupCardChip:
    """Lookup chips need list membership — never the card JSON payload."""

    id: UUID
    lemma_l2: str
    pos: str | None
    deck_id: UUID | None
    lexical_entry_id: UUID | None
    enrichment_status: str | None


@dataclass(frozen=True, slots=True)
class _LookupEntryRef:
    id: UUID
    lemma_l2: str
    pos: str | None


@dataclass(frozen=True, slots=True)
class _LookupListChip:
    id: UUID
    name: str
    is_system: bool


def lexical_entry_for_candidate(
    by_key: dict[tuple[str, str], object],
    lemma: str,
    pos: str | None,
) -> object | None:
    """Resolve a cached entry by lemma + POS only — never fall back to another POS."""
    bucket = normalize_pos_bucket(pos)
    if bucket == "unknown":
        return None
    return by_key.get((normalize_text(lemma), bucket))


def _card_matches_lookup(
    card: LearningCard | _LookupCardChip,
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
            select(
                LearningCard.id,
                LearningCard.lemma_l2,
                LearningCard.pos,
                LearningCard.deck_id,
                LearningCard.lexical_entry_id,
                LearningCard.enrichment_status,
            ).where(
                LearningCard.user_id == user_id,
                LearningCard.profile_id == profile_id,
                LearningCard.deleted_at.is_(None),
            )
        )
        cards = [
            _LookupCardChip(
                id=row.id,
                lemma_l2=row.lemma_l2,
                pos=row.pos,
                deck_id=row.deck_id,
                lexical_entry_id=row.lexical_entry_id,
                enrichment_status=row.enrichment_status,
            )
            for row in cards_result.all()
        ]
        lists_result = await self.db.execute(
            select(
                WordList.id,
                WordList.name,
                WordList.is_system,
            ).where(
                WordList.profile_id == profile_id,
                WordList.deleted_at.is_(None),
            )
        )
        lists_by_id = {
            row.id: _LookupListChip(id=row.id, name=row.name, is_system=row.is_system)
            for row in lists_result.all()
        }

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
                    **c,
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
        if not candidates:
            return candidates
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        lemmas = [normalize_text(c["lemma"]) for c in candidates if c.get("lemma")]
        if not lemmas:
            return candidates

        result = await self.db.execute(
            select(
                LexicalEntry.id,
                LexicalEntry.lemma_l2,
                LexicalEntry.pos,
            ).where(
                LexicalEntry.lang_pair == pair,
                func.lower(LexicalEntry.lemma_l2).in_(lemmas),
            )
        )
        by_key: dict[tuple[str, str], _LookupEntryRef] = {}
        for row in result.all():
            bucket = normalize_pos_bucket(row.pos)
            if bucket == "unknown":
                continue
            by_key[(normalize_text(row.lemma_l2), bucket)] = _LookupEntryRef(
                id=row.id,
                lemma_l2=row.lemma_l2,
                pos=row.pos,
            )
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

    def _raw_to_candidates(
        self,
        raw: list[dict],
        *,
        query: str | None = None,
        learning_lang: str | None = None,
    ) -> list[dict]:
        out: list[dict] = []
        for c in raw:
            if not c.get("lemma"):
                continue
            if (
                query
                and learning_lang
                and not row_translates_its_word(c, query, learning_lang=learning_lang)
            ):
                continue
            item = {
                "lemma": c.get("lemma", ""),
                "pos": c.get("pos"),
                "gloss": c.get("gloss", ""),
                "lexical_entry_id": None,
            }
            reading = (c.get("reading") or "").strip()
            if reading:
                item["reading"] = reading
            typed = (c.get("typed_as") or "").strip()
            if typed:
                item["typed_as"] = typed
            out.append(item)
        return out

    def _rank_lookup_candidates(
        self,
        candidates: list[dict],
        text: str,
        *,
        learning_lang: str,
        native_lang: str | None = None,
    ) -> list[dict]:
        # Drop a malformed lemma, then an echo of the query (much → mucha) and a
        # second part of speech pasted onto the same gloss. Rank what remains.
        candidates = sanitize_lookup_candidates(
            candidates, learning_lang=learning_lang
        )
        candidates = drop_implausible_lookup_rows(
            candidates, text, learning_lang=learning_lang, native_lang=native_lang
        )
        return rank_lookup_candidates(candidates, text, learning_lang=learning_lang)

    @staticmethod
    def _clean_lookup_rows(
        candidates: list[dict], text: str, profile: LanguageProfile
    ) -> list[dict]:
        """Citation forms first, so a stored row and its inflected repeat share one key."""
        return drop_implausible_lookup_rows(
            sanitize_lookup_candidates(
                candidates, learning_lang=profile.learning_lang, limit=None
            ),
            text,
            learning_lang=profile.learning_lang,
            native_lang=profile.app_lang,
        )

    async def _fuzzy_l1_db_candidates(
        self, profile: LanguageProfile, text: str
    ) -> list[dict]:
        """Recover L1 typos against known glosses for this language pair."""
        q = normalize_text(text)
        if not q or len(q) < 3:
            return []
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        rows: list[tuple[str, str | None, str, str | None]] = []

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
        cands = [
            {
                "lemma": e.lemma_l2,
                "pos": e.pos,
                "gloss": e.lemma_l1_primary or "",
                "lexical_entry_id": str(e.id),
            }
            for e in entries
        ]
        ranked = (
            self._rank_lookup_candidates(
                cands,
                text,
                learning_lang=profile.learning_lang,
                native_lang=profile.app_lang,
            )
            if cands
            else []
        )
        if any(
            candidate_is_confident(c, text, learning_lang=profile.learning_lang)
            for c in ranked
        ):
            return ranked
        fuzzy = await self._fuzzy_l1_db_candidates(profile, text)
        if not ranked and not fuzzy:
            return []
        merged, _ = append_lookup_candidates(
            ranked, fuzzy, learning_lang=profile.learning_lang
        )
        if not merged:
            return []
        return self._rank_lookup_candidates(
            merged,
            text,
            learning_lang=profile.learning_lang,
            native_lang=profile.app_lang,
        )

    async def _db_exact_candidates(
        self, profile: LanguageProfile, text: str
    ) -> list[dict]:
        """Lexicon hits for the typed word, without a typo search."""
        entries = await self.search_db(text, profile)
        cands = [
            {
                "lemma": e.lemma_l2,
                "pos": e.pos,
                "gloss": e.lemma_l1_primary or "",
                "lexical_entry_id": str(e.id),
            }
            for e in entries
        ]
        if not cands:
            return []
        return self._rank_lookup_candidates(
            cands,
            text,
            learning_lang=profile.learning_lang,
            native_lang=profile.app_lang,
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
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
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
        *,
        category: bool = False,
        annotate: bool = True,
        cache_row_id: UUID | None = None,
        lang_pair: str | None = None,
        persist: bool = False,
        suggestions_exhausted: bool = False,
        preserve_order: bool = False,
    ) -> LookupOutcome:
        if preserve_order:
            ranked = stored
        elif category:
            ranked = rank_category_candidates(
                stored, text, learning_lang=profile.learning_lang
            )
        else:
            ranked = self._rank_lookup_candidates(
                stored,
                text,
                learning_lang=profile.learning_lang,
                native_lang=profile.app_lang,
            )
        if not annotate:
            return LookupOutcome(
                ranked,
                source,
                ai_complete,
                cache_row_id=cache_row_id,
                lang_pair=lang_pair,
                persist=persist,
                suggestions_exhausted=suggestions_exhausted,
            )
        attached = await self._attach_lexical_ids(profile, ranked)
        annotated = await self._annotate_candidates(user.id, profile.id, attached)
        return LookupOutcome(
            annotated,
            source,
            ai_complete,
            cache_row_id=cache_row_id,
            lang_pair=lang_pair,
            persist=persist,
            suggestions_exhausted=suggestions_exhausted,
        )

    async def _merge_into_query_cache(
        self,
        pair: str,
        key: str,
        incoming: list[dict],
        *,
        learning_lang: str,
        limit: int | None = LOOKUP_CACHE_LIMIT,
    ) -> list[dict]:
        row = await self._ensure_query_cache_row(pair, key)
        merged, _added = append_lookup_candidates(
            list(row.candidates or []),
            incoming,
            learning_lang=learning_lang,
            limit=limit,
        )
        row.candidates = merged
        flag_modified(row, "candidates")
        row.hit_count = (row.hit_count or 0) + 1
        row.updated_at = datetime.now(UTC)
        await self.db.flush()
        return merged

    async def _light_draft_candidates(
        self, profile: LanguageProfile, text: str, *, user_id: UUID | None = None
    ) -> list[dict]:
        try:
            bind_llm_usage_context(
                overwrite_operation=True,
                operation_id=uuid4(),
                operation_kind="lookup_draft",
                query=text,
                lang_pair=lang_pair_key(profile.app_lang, profile.learning_lang),
                user_id=user_id,
                profile_id=profile.id,
            )
            raw = await self.llm.lookup_draft(
                text,
                profile.app_lang,
                profile.learning_lang,
            )
            return self._raw_to_candidates(
                raw, query=text, learning_lang=profile.learning_lang
            )
        except Exception:
            logger.warning("lookup draft failed for %r", text, exc_info=True)
            return []

    async def lookup_cached_fast(
        self, user_id: UUID, profile_id: UUID, text: str
    ) -> LookupOutcome | None:
        """Jeden SELECT: profil i gotowy wiersz cache. None, gdy wiersza nie ma."""
        text = letters_of_query(text)
        key = self._query_cache_key(text)
        pair_expr = func.concat(LanguageProfile.app_lang, ">", LanguageProfile.learning_lang)
        stmt = (
            select(
                LanguageProfile.app_lang,
                LanguageProfile.learning_lang,
                LookupQueryCache.id,
                LookupQueryCache.candidates,
                LookupQueryCache.ai_complete,
                LookupQueryCache.more_exhausted,
            )
            .select_from(LanguageProfile)
            .outerjoin(
                LookupQueryCache,
                and_(
                    LookupQueryCache.lang_pair == pair_expr,
                    LookupQueryCache.input_norm == key,
                ),
            )
            .where(
                LanguageProfile.id == profile_id,
                LanguageProfile.user_id == user_id,
            )
        )
        found = (await self.db.execute(stmt)).one_or_none()
        await self.db.rollback()
        if found is None:
            raise ValueError("Profile not found")
        app_lang, learning_lang, cache_id, candidates, ai_complete, more_exhausted = found
        if cache_id is None or not (candidates or ai_complete):
            return None
        ranked = self._rank_lookup_candidates(
            list(candidates or []),
            text,
            learning_lang=learning_lang,
            native_lang=app_lang,
        )
        return LookupOutcome(
            ranked,
            "db",
            bool(ai_complete),
            cache_row_id=cache_id,
            lang_pair=lang_pair_key(app_lang, learning_lang),
            suggestions_exhausted=bool(more_exhausted),
        )

    async def lookup_cached(
        self, user: User, profile_id: UUID, text: str, *, annotate: bool = True
    ) -> LookupOutcome:
        """Cache, a przy pustym cache jedno pytanie do modelu. Trafienie leksykonu wchodzi do tej samej listy."""
        profile = await self.get_profile(user.id, profile_id)
        text = letters_of_query(text)
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        key = self._query_cache_key(text)
        if not text:
            return LookupOutcome([], "db", False, lang_pair=pair)
        row = await self._fetch_query_cache(pair, key)
        if row is not None and (row.candidates or row.ai_complete):
            return await self._present_lookup(
                user,
                profile,
                text,
                list(row.candidates or []),
                "db",
                bool(row.ai_complete),
                annotate=annotate,
                cache_row_id=row.id,
                lang_pair=pair,
                suggestions_exhausted=bool(row.more_exhausted),
                preserve_order=True,
            )
        empty_row_id = row.id if row is not None else None
        await self.db.commit()
        lexicon = await self._db_exact_candidates(profile, text)
        confident = [
            c
            for c in lexicon
            if candidate_is_confident(c, text, learning_lang=profile.learning_lang)
        ]
        await self.db.commit()
        model_rows = self._clean_lookup_rows(
            await self._light_draft_candidates(profile, text, user_id=user.id),
            text,
            profile,
        )
        combined, _added = append_lookup_candidates(
            confident, model_rows, learning_lang=profile.learning_lang
        )
        if combined:
            combined = self._rank_lookup_candidates(
                combined,
                text,
                learning_lang=profile.learning_lang,
                native_lang=profile.app_lang,
            )
            merged = await self._merge_into_query_cache(
                pair, key, combined, learning_lang=profile.learning_lang
            )
            return await self._present_lookup(
                user,
                profile,
                text,
                merged,
                "ai" if model_rows else "db",
                False,
                preserve_order=True,
                annotate=annotate,
                lang_pair=pair,
                persist=True,
            )
        return LookupOutcome(
            [],
            "db",
            False,
            cache_row_id=empty_row_id,
            lang_pair=pair,
        )

    async def lookup_expand(
        self, user_id: UUID, profile_id: UUID, text: str, *, more: bool = False
    ) -> LookupOutcome:
        """Docelowy model. more=True dopisuje nawet gdy lista jest już zamknięta."""
        profile = await self.get_profile(user_id, profile_id)
        text = letters_of_query(text)
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        key = self._query_cache_key(text)
        if not text:
            return LookupOutcome([], "db", False, added=0, lang_pair=pair)
        row = await self._fetch_query_cache(pair, key)
        if not more and row is not None and row.ai_complete:
            stored = list(row.candidates or [])
            await self.db.execute(
                update(LookupQueryCache)
                .where(LookupQueryCache.id == row.id)
                .values(
                    hit_count=LookupQueryCache.hit_count + 1,
                    updated_at=func.now(),
                )
            )
            await self.db.commit()
            return LookupOutcome(
                stored,
                "db",
                True,
                added=0,
                lang_pair=pair,
                suggestions_exhausted=bool(row.more_exhausted),
            )

        already = self._clean_lookup_rows(
            list(row.candidates or []) if row is not None else [],
            text,
            profile,
        )
        await self.db.commit()
        bind_llm_usage_context(
            overwrite_operation=True,
            operation_id=uuid4(),
            operation_kind="lookup",
            query=text,
            lang_pair=pair,
            user_id=user_id,
            profile_id=profile.id,
        )
        raw = await self.llm.lookup_expand(
            text,
            profile.app_lang,
            profile.learning_lang,
            already,
        )
        incoming = self._clean_lookup_rows(
            self._raw_to_candidates(raw, query=text, learning_lang=profile.learning_lang),
            text,
            profile,
        )
        row = await self._ensure_query_cache_row(pair, key)
        if not more and row.ai_complete:
            return LookupOutcome(
                list(row.candidates or []),
                "db",
                True,
                added=0,
                lang_pair=pair,
                suggestions_exhausted=bool(row.more_exhausted),
            )
        before = self._clean_lookup_rows(list(row.candidates or []), text, profile)
        merged, _added = append_lookup_candidates(
            before,
            incoming,
            learning_lang=profile.learning_lang,
        )
        merged = self._clean_lookup_rows(merged, text, profile)
        added = count_new_lookup_rows(
            before, merged, learning_lang=profile.learning_lang
        )
        if more:
            row.more_exhausted = added == 0
        row.candidates = merged
        flag_modified(row, "candidates")
        row.ai_complete = True
        row.hit_count = (row.hit_count or 0) + 1
        row.updated_at = datetime.now(UTC)
        await self.db.flush()
        return LookupOutcome(
            merged,
            "ai",
            True,
            added=added,
            lang_pair=pair,
            suggestions_exhausted=bool(row.more_exhausted),
        )

    async def annotate_outcome(
        self, user_id: UUID, profile_id: UUID, outcome: LookupOutcome
    ) -> LookupOutcome:
        profile = await self.get_profile(user_id, profile_id)
        attached = await self._attach_lexical_ids(profile, list(outcome.candidates))
        annotated = await self._annotate_candidates(user_id, profile_id, attached)
        return LookupOutcome(
            annotated,
            outcome.source,
            outcome.ai_complete,
            added=outcome.added,
            cache_row_id=outcome.cache_row_id,
            lang_pair=outcome.lang_pair or lang_pair_key(profile.app_lang, profile.learning_lang),
            persist=outcome.persist,
            suggestions_exhausted=outcome.suggestions_exhausted,
        )

    async def lookup(self, user: User, profile_id: UUID, text: str) -> LookupOutcome:
        """Pełna ścieżka: cache/wiki/luna, terra tylko gdy nadal pusto."""
        cached = await self.lookup_cached(user, profile_id, text)
        if cached.ai_complete or cached.candidates:
            return cached
        return await self.lookup_expand(user.id, profile_id, text)

    def _assoc_key(self, text: str, round: int | None = None) -> str:
        base = "assoc:" + self._query_cache_key(text)[:190]
        return base if round is None else f"{base}:{round}"

    async def lookup_category_cached(
        self, user: User, profile_id: UUID, text: str
    ) -> LookupOutcome:
        """Jedno słowo tematu. Zapis assoc: albo jedno krótkie pytanie do modelu."""
        profile = await self.get_profile(user.id, profile_id)
        text = letters_of_query(text)
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        key = self._assoc_key(text)
        if not text:
            return LookupOutcome([], "db", False, lang_pair=pair)
        row = await self._fetch_query_cache(pair, key)
        if row is not None and row.candidates:
            return LookupOutcome(
                list(row.candidates)[:1],
                "db",
                False,
                cache_row_id=row.id,
                lang_pair=pair,
            )
        await self.db.commit()
        bind_llm_usage_context(
            overwrite_operation=True,
            operation_id=uuid4(),
            operation_kind="lookup_category_draft",
            query=text,
            lang_pair=pair,
            user_id=user.id,
            profile_id=profile.id,
        )
        raw = await self.llm.lookup_category_draft(
            text, profile.app_lang, profile.learning_lang
        )
        incoming = sanitize_lookup_candidates(
            self._raw_to_candidates(
                raw, query=text, learning_lang=profile.learning_lang
            ),
            learning_lang=profile.learning_lang,
            limit=1,
        )
        if not incoming:
            return LookupOutcome([], "ai", False, lang_pair=pair)
        merged = await self._merge_into_query_cache(
            pair, key, incoming, learning_lang=profile.learning_lang, limit=1
        )
        stored = await self._fetch_query_cache(pair, key)
        if stored is not None:
            stored.ai_complete = False
        await self.db.commit()
        return LookupOutcome(
            merged[:1],
            "ai",
            False,
            cache_row_id=stored.id if stored is not None else None,
            lang_pair=pair,
            persist=True,
        )

    async def lookup_assoc_round(
        self, user_id: UUID, profile_id: UUID, text: str, round: int
    ) -> LookupOutcome:
        """Jedna ósemka skojarzeń. Runda 2 i 3 czekają na poprzedni zapis."""
        if round > 3:
            return LookupOutcome([], "db", True, added=0)
        profile = await self.get_profile(user_id, profile_id)
        text = letters_of_query(text)
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        key = self._assoc_key(text, round)
        row = await self._fetch_query_cache(pair, key)
        if row is not None and row.candidates:
            words, meaning = _assoc_words_and_meaning(list(row.candidates))
            return LookupOutcome(
                words,
                "db",
                True,
                added=len(words),
                cache_row_id=row.id,
                lang_pair=pair,
                headword_meaning=meaning,
            )
        if round >= 2:
            previous = await self._fetch_query_cache(pair, self._assoc_key(text, round - 1))
            if previous is None or not previous.candidates:
                raise AssocRoundNotReady()
        already = await self._assoc_already_lemmas(pair, text, round)
        await self.db.commit()
        bind_llm_usage_context(
            overwrite_operation=True,
            operation_id=uuid4(),
            operation_kind="lookup_category",
            query=text,
            lang_pair=pair,
            user_id=user_id,
            profile_id=profile.id,
        )
        raw, meaning = await self.llm.lookup_category_expand(
            text,
            profile.app_lang,
            profile.learning_lang,
            already,
        )
        incoming = sanitize_lookup_candidates(
            self._raw_to_candidates(
                raw, query=text, learning_lang=profile.learning_lang
            ),
            learning_lang=profile.learning_lang,
        )
        incoming = [
            item
            for item in incoming
            if canonical_lemma(item.get("lemma")) not in already
        ]
        if not incoming:
            return LookupOutcome([], "ai", True, added=0, lang_pair=pair, headword_meaning=meaning)
        fresh = await self._ensure_query_cache_row(pair, key)
        if fresh.candidates:
            words, stored_meaning = _assoc_words_and_meaning(list(fresh.candidates))
            return LookupOutcome(
                words,
                "db",
                True,
                added=len(words),
                cache_row_id=fresh.id,
                lang_pair=pair,
                headword_meaning=stored_meaning or meaning,
            )
        fresh.candidates = ([{"_meaning": meaning}] if meaning else []) + incoming
        flag_modified(fresh, "candidates")
        fresh.ai_complete = True
        fresh.hit_count = (fresh.hit_count or 0) + 1
        fresh.updated_at = datetime.now(UTC)
        await self.db.flush()
        return LookupOutcome(
            incoming,
            "ai",
            True,
            added=len(incoming),
            cache_row_id=fresh.id,
            lang_pair=pair,
            persist=True,
            headword_meaning=meaning,
        )

    async def _assoc_already_lemmas(self, pair: str, text: str, round: int) -> set[str]:
        keys = [self._assoc_key(text)]
        keys.extend(self._assoc_key(text, index) for index in range(1, round))
        rows = (
            await self.db.execute(
                select(LookupQueryCache).where(
                    LookupQueryCache.lang_pair == pair,
                    LookupQueryCache.input_norm.in_(keys),
                )
            )
        ).scalars().all()
        seen: set[str] = set()
        for row in rows:
            for item in row.candidates or []:
                if isinstance(item, dict):
                    key = canonical_lemma(item.get("lemma"))
                    if key:
                        seen.add(key)
        return seen

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
                    from app.services.word_families import sync_word_family

                    synced = await sync_word_family(
                        self.db, profile, dict(entry.content or {}), entry
                    )
                    entry.content = synced
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
            from app.services.word_families import sync_word_family

            synced = await sync_word_family(
                self.db, profile, dict(existing.content or {}), existing
            )
            existing.content = synced
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
        from app.services.word_families import sync_word_family

        synced = await sync_word_family(self.db, profile, content, entry)
        entry.content = synced
        return entry

