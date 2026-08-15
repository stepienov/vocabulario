import asyncio
import re
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import lang_pair_key, normalize_text
from app.models import LanguageProfile, LearningCard, LexicalEntry, User
from app.services.llm import LLMService
from app.services.enrichment import enrich_card_content
from app.services.lookup_candidates import (
    gloss_query_score,
    has_confident_match,
    merge_candidates,
    rank_lookup_candidates,
    sanitize_lookup_candidates,
    token_similarity,
)
from app.services.similar_words import ensure_similar_words
from app.services.word_persistence import (
    EphemeralLexicalEntry,
    build_ephemeral_entry,
    words_persistence_enabled,
)


LexicalEntryLike = LexicalEntry | EphemeralLexicalEntry


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
                    if normalize_text(card.lemma_l2) == lemma_norm
                    and (not pos or card.pos == pos)
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
        by_key: dict[tuple[str, str | None], LexicalEntry] = {}
        for entry in result.scalars().all():
            by_key[(normalize_text(entry.lemma_l2), entry.pos)] = entry
            by_key.setdefault((normalize_text(entry.lemma_l2), None), entry)
        out = []
        for c in candidates:
            key_pos = (normalize_text(c["lemma"]), c.get("pos"))
            key_any = (normalize_text(c["lemma"]), None)
            entry = by_key.get(key_pos) or by_key.get(key_any)
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
            if (card.content or {}).get("schema_version") == "import_display.v1":
                continue
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
        seen: set[str] = set()
        for _, item in scored:
            key = normalize_text(item["lemma"])
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

    async def lookup(self, user: User, profile_id: UUID, text: str) -> tuple[list[dict], str]:
        """Candidates from AI (+ DB fuzzy L1 typo recovery); membership annotated.

        PG-first: if the shared PostgreSQL lexicon already holds a *confident* reading of
        the query (exact / diacritic-completed L2 headword), serve it directly and skip the
        (paid, slower) AI call. Otherwise fall back to the high-recall AI union below — the
        lookup is this app's core feature, so a missed suggestion is a fatal bug while an
        extra plausible one is harmless.
        """
        profile = await self.get_profile(user.id, profile_id)

        # PG-first short-circuit — only when the DB match is confident, never on a guess.
        db_first = await self._db_first_candidates(profile, text)
        if db_first and has_confident_match(
            db_first, text, learning_lang=profile.learning_lang
        ):
            attached = await self._attach_lexical_ids(profile, db_first)
            return (
                await self._annotate_candidates(user.id, profile_id, attached),
                "db",
            )

        raw = await self.llm.lookup(
            text, profile.app_lang, profile.learning_lang, profile.cefr_level
        )
        candidates = self._rank_lookup_candidates(
            self._raw_to_candidates(raw),
            text,
            learning_lang=profile.learning_lang,
        )

        db_fuzzy = await self._fuzzy_l1_db_candidates(profile, text)
        if db_fuzzy:
            candidates = self._rank_lookup_candidates(
                merge_candidates(candidates, db_fuzzy, limit=12, learning_lang=profile.learning_lang),
                text,
                learning_lang=profile.learning_lang,
            )

        # Recovery pass whenever we have no exact/diacritic-completed reading yet.
        # This catches the classic "ksiazka → książka → libro" case the model may miss
        # on the first pass because it latched onto a different-word typo (kiszka).
        if not has_confident_match(candidates, text, learning_lang=profile.learning_lang):
            raw2 = await self.llm.lookup_l1_typo(
                text, profile.app_lang, profile.learning_lang, profile.cefr_level
            )
            recovery = self._rank_lookup_candidates(
                self._raw_to_candidates(raw2),
                text,
                learning_lang=profile.learning_lang,
            )
            if recovery:
                # Recovery first so the diacritic-completed intent wins the size cap,
                # then rank restores the correct ordering across the whole union.
                candidates = self._rank_lookup_candidates(
                    merge_candidates(
                        recovery, candidates, limit=12, learning_lang=profile.learning_lang
                    ),
                    text,
                    learning_lang=profile.learning_lang,
                )

        candidates = await self._attach_lexical_ids(profile, candidates)
        return await self._annotate_candidates(user.id, profile_id, candidates), "ai"

    async def best_lookup_candidate(
        self, user: User, profile_id: UUID, text: str
    ) -> dict | None:
        """Top-ranked lookup reading for offline-queued headwords (L1 or L2)."""
        candidates, _ = await self.lookup(user, profile_id, text)
        return candidates[0] if candidates else None

    async def _exact_db_entry(
        self, profile: LanguageProfile, text: str
    ) -> LexicalEntry | None:
        if not words_persistence_enabled():
            return None
        pair = lang_pair_key(profile.app_lang, profile.learning_lang)
        norm = normalize_text(text)
        result = await self.db.execute(
            select(LexicalEntry).where(
                LexicalEntry.lang_pair == pair,
                or_(
                    LexicalEntry.lemma_l2 == norm,
                    LexicalEntry.lemma_l1_primary == norm,
                ),
            ).limit(1)
        )
        entry = result.scalar_one_or_none()
        if entry is not None:
            return entry
        # ilike exact ignoring case for stored mixed case
        result = await self.db.execute(
            select(LexicalEntry).where(
                LexicalEntry.lang_pair == pair,
                or_(
                    LexicalEntry.lemma_l2.ilike(norm),
                    LexicalEntry.lemma_l1_primary.ilike(norm),
                ),
            ).limit(5)
        )
        for row in result.scalars().all():
            if normalize_text(row.lemma_l2) == norm or normalize_text(
                row.lemma_l1_primary or ""
            ) == norm:
                return row
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
                entry.usage_count += 1
                content = await ensure_similar_words(
                    dict(entry.content or {}),
                    profile,
                    entry.lemma_l2,
                    entry.pos,
                )
                if content != entry.content:
                    entry.content = content
                return entry

        norm_lemma = normalize_text(lemma)
        stmt = select(LexicalEntry).where(
            LexicalEntry.lang_pair == pair,
            LexicalEntry.lemma_l2.ilike(norm_lemma),
        )
        if pos:
            stmt = stmt.where(LexicalEntry.pos == pos)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.usage_count += 1
            content = await ensure_similar_words(
                dict(existing.content or {}),
                profile,
                existing.lemma_l2,
                existing.pos,
            )
            if content != existing.content:
                existing.content = content
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
        self.db.add(entry)
        await self.db.flush()
        return entry

