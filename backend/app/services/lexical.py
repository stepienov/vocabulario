from uuid import UUID



from sqlalchemy import or_, select

from sqlalchemy.ext.asyncio import AsyncSession



from app.core.deps import lang_pair_key, normalize_text

from app.models import FavoriteWord, LanguageProfile, LearningCard, LexicalEntry, User

from app.services.llm import LLMService

from app.services.enrichment import enrich_card_content
from app.services.lookup_candidates import sanitize_lookup_candidates
from app.services.similar_words import ensure_similar_words

from app.services.word_persistence import (

    EphemeralLexicalEntry,

    build_ephemeral_entry,

    words_persistence_enabled,

)



LexicalEntryLike = LexicalEntry | EphemeralLexicalEntry





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

        pair = lang_pair_key(profile.native_lang, profile.learning_lang)

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

                    "is_favorite": False,

                    "learning_card_id": None,

                }

                for c in candidates

            ]



        cards_result = await self.db.execute(

            select(LearningCard).where(

                LearningCard.user_id == user_id,

                LearningCard.profile_id == profile_id,

                LearningCard.deck_id.is_(None),

            )

        )

        cards = list(cards_result.scalars().all())

        fav_result = await self.db.execute(

            select(FavoriteWord).where(

                FavoriteWord.user_id == user_id,

                FavoriteWord.profile_id == profile_id,

            )

        )

        favorites = list(fav_result.scalars().all())



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

            favorite = next(

                (

                    f

                    for f in favorites

                    if normalize_text(f.lemma) == lemma_norm

                    and (not pos or f.pos == pos)

                ),

                None,

            )

            annotated.append(

                {

                    **c,

                    "in_learning": learning_card is not None,

                    "is_favorite": favorite is not None,

                    "learning_card_id": str(learning_card.id) if learning_card else None,

                }

            )

        return annotated



    async def lookup(self, user: User, profile_id: UUID, text: str) -> tuple[list[dict], str]:

        profile = await self.get_profile(user.id, profile_id)

        entries = await self.search_db(text, profile)



        if entries:

            candidates = [

                {

                    "lemma": e.lemma_l2,

                    "pos": e.pos,

                    "gloss": e.lemma_l1_primary or "",

                    "lexical_entry_id": str(e.id),

                }

                for e in entries

            ]

            return await self._annotate_candidates(user.id, profile_id, candidates), "db"



        raw = await self.llm.lookup(

            text, profile.native_lang, profile.learning_lang, profile.cefr_level

        )

        candidates = [

            {

                "lemma": c.get("lemma", ""),

                "pos": c.get("pos"),

                "gloss": c.get("gloss", ""),

                "lexical_entry_id": None,

            }

            for c in raw

            if c.get("lemma")

        ]

        candidates = sanitize_lookup_candidates(candidates)

        return await self._annotate_candidates(user.id, profile_id, candidates), "ai"



    async def _enrich_ephemeral(

        self,

        profile: LanguageProfile,

        lemma: str,

        pos: str | None,

    ) -> EphemeralLexicalEntry:

        pair = lang_pair_key(profile.native_lang, profile.learning_lang)

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



        pair = lang_pair_key(profile.native_lang, profile.learning_lang)



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


