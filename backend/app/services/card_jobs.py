"""Enrichment poza cyklem żądania.

Karta zapisuje się natychmiast ze statusem `pending`, więc użytkownik może dalej
korzystać z aplikacji. Pełną treść — znaczenia, przykłady, dystraktory,
koniugację — dociąga zadanie w tle i przestawia status na `ready`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas.similar_words import MIN_SIMILAR_FOR_QUIZ
from app.core.deps import lang_pair_key, normalize_text
from app.core.lemma_keys import cache_lookup_keys, canonical_lemma
from app.db.session import async_session_factory
from app.lsp.lang_utils import articles_for
from app.models import LanguageProfile, LearningCard, LexicalEntry, User
from app.services.distractors import in_learning_lemma, lemma_keys
from app.services.enrichment import enrich_adaptive_card_content, enrich_card_content
from app.services.lexical import LexicalService
from app.services.pos_normalize import normalize_pos_bucket
from app.services.similar_words import ensure_similar_words

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PREPARING = "preparing"
STATUS_PREPARATION_PROBLEM = "prep_problem"
STATUS_READY = "ready"
STATUS_FAILED = "failed"

_MAX_MANUAL_ENRICH_RETRIES = 3
_AUTO_RETRY_DELAY = timedelta(minutes=15)

# Max kart wzbogacanych naraz. 9× równolegle = ~36 calli reasoning-modelu i lawina.
_ENRICH_CONCURRENCY = 3
_ENRICH_TIMEOUT_S = 120
_ENRICH_STALE_S = 45
_ENRICH_RESUME_BATCH = 40
_enrich_gate: asyncio.Semaphore | None = None
_claimed: set[UUID] = set()
_resume_lock = asyncio.Lock()


def _enrich_semaphore() -> asyncio.Semaphore:
    global _enrich_gate
    if _enrich_gate is None:
        _enrich_gate = asyncio.Semaphore(_ENRICH_CONCURRENCY)
    return _enrich_gate


def _card_lookup_resolved(card: LearningCard) -> bool:
    """Lookup w enrichment pomijamy, gdy karta ma już rozwiązany lemat (z UI / importu)."""
    if card.lexical_entry_id is not None:
        return True
    gloss = (card.gloss_primary or "").strip()
    pos = (card.pos or "").strip()
    return bool(gloss and pos)


def spawn_enrich(card_id: UUID) -> None:
    """Odpal enrichment w tle. Bezpieczne do wielokrotnego wołania."""
    if card_id in _claimed:
        return
    _claimed.add(card_id)
    task = asyncio.create_task(_run_claimed_enrich(card_id), name=f"enrich:{card_id}")

    def _done(done: asyncio.Task) -> None:
        _claimed.discard(card_id)
        if done.cancelled():
            return
        exc = done.exception()
        if exc is not None:
            logger.error("enrich task %s died: %s", card_id, exc)

    task.add_done_callback(_done)


async def _mark_enrich_failed(card_id: UUID, error: str) -> None:
    try:
        async with async_session_factory() as db:
            card = (
                await db.execute(select(LearningCard).where(LearningCard.id == card_id))
            ).scalar_one_or_none()
            if card is None or card.enrichment_status == STATUS_READY:
                return
            _apply_enrich_retry(card, RuntimeError(error))
            await db.commit()
    except Exception:
        logger.exception("Nie udało się oznaczyć karty %s jako failed", card_id)


def _apply_enrich_retry(card: LearningCard, exc: BaseException) -> None:
    """Jeden auto-retry za 15 min, potem prep_problem; ręcznie max 3×."""
    err = public_enrichment_error(exc)

    if bool(getattr(card, "enrichment_manual_triggered", False)):
        card.enrichment_manual_triggered = False
        card.enrichment_retry_count = int(card.enrichment_retry_count or 0) + 1
        card.enrichment_retry_at = None
        if card.enrichment_retry_count >= _MAX_MANUAL_ENRICH_RETRIES:
            card.enrichment_status = STATUS_FAILED
            card.enrichment_error = err
            logger.info(
                "Enrichment karty %s → failed po %s ręcznych próbach (%s)",
                card.id,
                card.enrichment_retry_count,
                card.lemma_l2,
            )
            return
        card.enrichment_status = STATUS_PREPARATION_PROBLEM
        card.enrichment_error = err
        logger.info(
            "Enrichment karty %s → prep_problem (manual %s/%s) (%s)",
            card.id,
            card.enrichment_retry_count,
            _MAX_MANUAL_ENRICH_RETRIES,
            card.lemma_l2,
        )
        return

    if not bool(getattr(card, "enrichment_auto_retry_used", False)):
        card.enrichment_auto_retry_used = True
        card.enrichment_status = STATUS_PREPARING
        card.enrichment_error = err
        card.enrichment_retry_at = datetime.now(UTC) + _AUTO_RETRY_DELAY
        logger.info(
            "Enrichment karty %s → preparing; auto-retry za %s (%s)",
            card.id,
            _AUTO_RETRY_DELAY,
            card.lemma_l2,
        )
        return

    card.enrichment_status = STATUS_PREPARATION_PROBLEM
    card.enrichment_error = err
    card.enrichment_retry_at = None
    logger.info(
        "Enrichment karty %s → prep_problem po auto-retry (%s)",
        card.id,
        card.lemma_l2,
    )


def _clear_enrich_retry(card: LearningCard) -> None:
    card.enrichment_retry_count = 0
    card.enrichment_retry_at = None
    card.enrichment_error = None
    card.enrichment_auto_retry_used = False
    card.enrichment_manual_triggered = False


async def request_manual_enrichment_retry(db: AsyncSession, card: LearningCard) -> None:
    """Użytkownik klika refresh — max 3 ręczne próby przed trwałym failed."""
    if card.enrichment_status != STATUS_PREPARATION_PROBLEM:
        raise ValueError("card_not_retryable")
    if int(card.enrichment_retry_count or 0) >= _MAX_MANUAL_ENRICH_RETRIES:
        raise ValueError("manual_retries_exhausted")
    card.enrichment_status = STATUS_PENDING
    card.enrichment_error = None
    card.enrichment_retry_at = None
    card.enrichment_manual_triggered = True
    card.lexical_entry_id = None
    await db.flush()
    spawn_enrich(card.id)


def build_pending_content(
    *,
    lemma: str,
    pos: str | None,
    gloss: str | None,
    learning_lang: str,
    entry_kind: str = "lemma",
    base_lemma: str | None = None,
    pattern: str | None = None,
) -> dict:
    """Minimalna treść karty z danych, które lookup zwrócił bez dodatkowego kosztu."""
    meanings = [{"gloss_l1": gloss, "synonyms_l1": [], "examples": [], "usages": []}] if gloss else []
    kind = (entry_kind or "lemma").strip().lower()
    base: dict = {
        "schema_version": "vocabulario.card.v1" if kind == "lemma" else "vocabulario.adaptive.v1",
        "lemma": lemma,
        "language": learning_lang,
        "pos": pos,
        "ipa": None,
        "meanings": meanings,
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "similar_words": [],
        "inflection": None,
        "conjugation": None,
    }
    if kind != "lemma":
        base["entry_kind"] = kind
        base["pattern"] = pattern
        base["related_lemma"] = base_lemma
        base["source_import"] = {
            "gloss_hint": gloss,
            "base_lemma": base_lemma,
            "pattern": pattern,
        }
    return base


def build_import_display_content(
    *,
    lemma: str,
    gloss: str | None,
    learning_lang: str,
    display: dict,
) -> dict:
    """Treść fiszki zachowanej z importu — gotowa do renderu bloków, bez enrichmentu."""
    lemma_from_sem, gloss_from_sem, has_both_semantics = _extract_semantic_l2_l1(display)
    lemma_out = (lemma_from_sem or lemma or "").strip() or lemma
    gloss_out = ((gloss_from_sem or gloss or "").strip() or None)
    display_out = dict(display or {})
    # Dwustronność tylko gdy AI pewnie otagowało L2/L1 (semantic) — inaczej false.
    flag = display_out.get("bidirectional")
    display_out["bidirectional"] = bool(
        has_both_semantics and (True if flag is None else bool(flag))
    )

    return {
        "schema_version": "import_display.v1",
        "card_kind": "imported",
        "lemma": lemma_out,
        "lemma_l2": lemma_out,
        "gloss_primary": gloss_out,
        "language": learning_lang,
        "pos": "imported",
        "ipa": None,
        "meanings": (
            [{"gloss_l1": gloss_out, "synonyms_l1": [], "examples": [], "usages": []}]
            if gloss_out
            else []
        ),
        "synonyms_l2": [],
        "antonyms_l2": [],
        "word_family_l2": [],
        "similar_words": [],
        "conjugation": None,
        "display": display_out,
    }


def _extract_semantic_l2_l1(display: dict | None) -> tuple[str | None, str | None, bool]:
    """Pull lemma (headword) and gloss (translation) from display blocks."""
    if not isinstance(display, dict):
        return None, None, False
    blocks: list[dict] = []
    for side in ("prompt", "answer"):
        side_obj = display.get(side) or {}
        if isinstance(side_obj, dict):
            for b in side_obj.get("blocks") or []:
                if isinstance(b, dict):
                    blocks.append(b)
                    for ch in b.get("children") or []:
                        if isinstance(ch, dict):
                            blocks.append(ch)
    headword = None
    translation = None
    for b in blocks:
        sem = (b.get("semantic") or "").strip()
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if sem == "headword" and not headword:
            headword = text
        elif sem == "translation" and not translation:
            translation = text
    return headword, translation, bool(headword and translation)


def content_is_complete(content: dict | None) -> bool:
    """Gotowa treść ma znaczenia z przykładami i pełny zestaw dystraktorów."""
    if not content:
        return False
    meanings = content.get("meanings") or []
    if not meanings:
        return False
    if not all(isinstance(m, dict) and m.get("examples") for m in meanings):
        return False
    # Adaptive: bez similar_words / conjugation
    if content.get("schema_version") == "vocabulario.adaptive.v1":
        return True
    if content.get("schema_version") == "vocabulario.card.v1":
        inf = content.get("inflection") or {}
        verbs = inf.get("verbs") if isinstance(inf, dict) else None
        has_inflection = isinstance(verbs, dict) and (
            verbs.get("tenses") or verbs.get("non_finite")
        )
        if content.get("pos") == "verb" and not has_inflection and not content.get("conjugation"):
            return False
        return len(content.get("similar_words") or []) >= MIN_SIMILAR_FOR_QUIZ
    return len(content.get("similar_words") or []) >= MIN_SIMILAR_FOR_QUIZ


def lexical_lookup_variants(raw: str, learning_lang: str | None) -> set[str]:
    """el negocio / negocio / le rêve — te same klucze do cache."""
    articles = articles_for(learning_lang)
    variants = {normalize_text(v) for v in lemma_keys(raw, articles)}
    bare = ""
    for key in list(variants):
        parts = key.split()
        if len(parts) > 1:
            bare = " ".join(parts[1:])
            variants.add(bare)
        else:
            bare = key
    if bare:
        for art in ("el", "la", "los", "las", "le", "la", "les", "the"):
            variants.add(f"{art} {bare}")
    key = canonical_lemma(raw)
    if key:
        variants.add(key)
    return {v for v in variants if v}


def apply_lexical_keys(entry: LexicalEntry) -> None:
    entry.lemma_key_l2 = canonical_lemma(entry.lemma_l2) or None
    entry.lemma_key_l1 = canonical_lemma(entry.lemma_l1_primary) or None


def public_enrichment_error(exc: BaseException) -> str:
    """Nigdy nie pokazuj userowi raw OpenAI / billingu."""
    raw = str(exc)
    lowered = raw.lower()
    if any(
        tok in lowered
        for tok in (
            "insufficient_quota",
            "credit_balance",
            "you have no credits",
            "error code:",
            "rate limit",
            "429",
            "openai",
        )
    ):
        return "enrichment_unavailable"
    return raw[:500]


def _entry_has_paid_content(entry: LexicalEntry) -> bool:
    """Tylko pełna treść — samo similar_words / odmiana bez znaczeń nie wchodzi do cache."""
    return content_is_complete(getattr(entry, "content", None) or {})


def same_pos_bucket(left: str | None, right: str | None) -> bool:
    """True when both sides name the same POS, or one side is unknown."""
    a = normalize_pos_bucket(left)
    b = normalize_pos_bucket(right)
    if a == "unknown" or b == "unknown":
        return True
    return a == b


def same_headword(left: str | None, right: str | None) -> bool:
    """True when both sides are the same citation form (articles/punct ignored)."""
    a = canonical_lemma(left)
    b = canonical_lemma(right)
    return bool(a and b and a == b)


def pick_ready_entry(rows: list, pos: str | None, require_lemma: str | None = None):
    """Pick a cached lexical row. Never return a different POS than requested."""
    if not rows:
        return None
    pool = [e for e in rows if content_is_complete(getattr(e, "content", None))]
    if not pool:
        return None
    if require_lemma:
        pool = [e for e in pool if same_headword(require_lemma, getattr(e, "lemma_l2", None))]
        if not pool:
            return None
    if not pos:
        return pool[0]
    want = normalize_pos_bucket(pos)
    if want == "unknown":
        return None
    for e in pool:
        content = getattr(e, "content", None) or {}
        entry_pos = None
        if isinstance(content, dict):
            entry_pos = content.get("pos")
        entry_pos = entry_pos or getattr(e, "pos", None)
        if normalize_pos_bucket(entry_pos) == want:
            return e
    return None


def entry_compatible_with_card(card: LearningCard, entry: LexicalEntry) -> bool:
    content = dict(entry.content or {})
    if not same_pos_bucket(card.pos, content.get("pos") or entry.pos):
        return False
    return same_headword(card.lemma_l2, entry.lemma_l2)


async def find_ready_entry(
    db: AsyncSession,
    *,
    lang_pair: str,
    lemma: str,
    pos: str | None,
    learning_lang: str | None = None,
    gloss: str | None = None,
    require_l2: bool = False,
) -> LexicalEntry | None:
    """Szuka po kanonicznym kluczu L2 albo L1. Trafienie = zero OpenAI.

    ``require_l2=True`` (hydrate karty): tylko ten sam headword L2 — synonim
    z tym samym glossem (acabar/terminar → kończyć) nie może nadpisać lematu.
    """
    keys = cache_lookup_keys(lemma) if require_l2 else cache_lookup_keys(lemma, gloss)
    if not keys:
        return None
    match = or_(
        LexicalEntry.lemma_key_l2.in_(keys),
        LexicalEntry.lemma_key_l1.in_(keys),
    )
    stmt = select(LexicalEntry).where(LexicalEntry.lang_pair == lang_pair, match)
    rows = [e for e in (await db.execute(stmt)).scalars().all() if _entry_has_paid_content(e)]
    if not rows:
        # Stare wiersze sprzed backfillu kluczy — ostatnia siatka, nadal bez LLM.
        variants = lexical_lookup_variants(lemma, learning_lang)
        if gloss:
            variants |= lexical_lookup_variants(gloss, learning_lang)
        variants |= keys
        if variants:
            legacy = or_(
                func.lower(LexicalEntry.lemma_l2).in_(variants),
                func.lower(LexicalEntry.lemma_l1_primary).in_(variants),
            )
            legacy_rows = list(
                (
                    await db.execute(
                        select(LexicalEntry).where(LexicalEntry.lang_pair == lang_pair, legacy)
                    )
                ).scalars().all()
            )
            rows = [e for e in legacy_rows if _entry_has_paid_content(e)]
    if not rows:
        logger.info("lexical cache MISS pair=%s keys=%s lemma=%r gloss=%r", lang_pair, keys, lemma, gloss)
        from app.services.app_log import log_event

        await log_event(
            level="info",
            category="enrichment",
            event="lexical_cache_miss",
            status="ok",
            message=f"cache miss {lemma!r}",
            payload={"lang_pair": lang_pair, "keys": sorted(keys), "lemma": lemma, "gloss": gloss},
        )
        return None
    hit = pick_ready_entry(rows, pos, require_lemma=lemma if require_l2 else None)
    if hit is None:
        logger.info(
            "lexical cache MISS pair=%s keys=%s lemma=%r pos=%r (wrong-POS only)",
            lang_pair,
            keys,
            lemma,
            pos,
        )
        return None
    logger.info(
        "lexical cache HIT pair=%s query=%r pos=%r → %r / %r",
        lang_pair,
        lemma,
        pos,
        hit.lemma_l2,
        hit.lemma_l1_primary,
    )
    return hit


async def hydrate_from_lexical_cache(
    db: AsyncSession,
    card: LearningCard,
    profile: LanguageProfile,
) -> bool:
    """Jeśli PG ma już gotową kartę — wstaw treść i READY. Zero LLM."""
    pair = lang_pair_key(profile.app_lang, profile.learning_lang)
    if card.lexical_entry_id is not None:
        pinned = (
            await db.execute(
                select(LexicalEntry).where(LexicalEntry.id == card.lexical_entry_id)
            )
        ).scalar_one_or_none()
        if pinned is not None and entry_compatible_with_card(card, pinned):
            try:
                async with db.begin_nested():
                    _apply_entry_to_card(card, pinned, profile)
                    pinned.usage_count = (pinned.usage_count or 0) + 1
                    await db.flush()
            except IntegrityError:
                return False
            return True
    cached = await find_ready_entry(
        db,
        lang_pair=pair,
        lemma=card.lemma_l2,
        pos=card.pos,
        learning_lang=profile.learning_lang,
        require_l2=True,
    )
    if cached is None or not entry_compatible_with_card(card, cached):
        return False
    try:
        async with db.begin_nested():
            _apply_entry_to_card(card, cached, profile)
            cached.usage_count = (cached.usage_count or 0) + 1
            await db.flush()
    except IntegrityError:
        # Unique (lemma, pos) — nie zatruwaj sesji importu. Karta zostaje pending.
        return False
    return True


def _apply_entry_to_card(
    card: LearningCard,
    entry: LexicalEntry,
    profile: LanguageProfile,
) -> None:
    content = dict(entry.content or {})
    card.content = content
    card.lexical_entry_id = entry.id
    applied_pos = content.get("pos") or entry.pos
    if card.pos and applied_pos and not same_pos_bucket(card.pos, applied_pos):
        applied_pos = card.pos
        content["pos"] = card.pos
    card.pos = applied_pos or card.pos
    meanings = content.get("meanings") or []
    card.gloss_primary = (
        meanings[0].get("gloss_l1") if meanings else None
    ) or entry.lemma_l1_primary or card.gloss_primary
    articles = articles_for(profile.learning_lang)
    if same_headword(card.lemma_l2, entry.lemma_l2) and not in_learning_lemma(
        card.lemma_l2, lemma_keys(entry.lemma_l2, articles), articles
    ):
        card.lemma_l2 = entry.lemma_l2
    elif not same_headword(card.lemma_l2, entry.lemma_l2):
        content["lemma"] = card.lemma_l2
    card.enrichment_status = STATUS_READY
    _clear_enrich_retry(card)


async def _find_ready_entry(
    db: AsyncSession,
    *,
    lang_pair: str,
    lemma: str,
    pos: str | None,
    learning_lang: str | None = None,
) -> LexicalEntry | None:
    return await find_ready_entry(
        db, lang_pair=lang_pair, lemma=lemma, pos=pos, learning_lang=learning_lang
    )


async def _resolve_content(
    db: AsyncSession,
    profile: LanguageProfile,
    lemma: str,
    pos: str | None,
    *,
    user_id: UUID | None,
    gloss_hint: str | None = None,
) -> tuple[dict, LexicalEntry | None]:
    """Zwraca gotową treść — z bazy, jeśli ktoś już to słowo wzbogacił."""
    pair = lang_pair_key(profile.app_lang, profile.learning_lang)

    cached = await find_ready_entry(
        db,
        lang_pair=pair,
        lemma=lemma,
        pos=pos,
        learning_lang=profile.learning_lang,
    )
    if cached is not None:
        cached.usage_count = (cached.usage_count or 0) + 1
        return dict(cached.content), cached

    content = await enrich_card_content(profile, lemma, pos, gloss_hint=gloss_hint)
    content = await ensure_similar_words(
        content, profile, content.get("lemma") or lemma, content.get("pos") or pos
    )

    final_lemma = content.get("lemma") or lemma
    final_pos = content.get("pos") or pos
    if pos and final_pos and not same_pos_bucket(pos, final_pos):
        content = dict(content)
        content["pos"] = pos
        final_pos = pos
    cached = await find_ready_entry(
        db,
        lang_pair=pair,
        lemma=final_lemma,
        pos=final_pos,
        learning_lang=profile.learning_lang,
    )
    if cached is not None:
        cached.usage_count = (cached.usage_count or 0) + 1
        return dict(cached.content), cached

    meanings = content.get("meanings") or []
    gloss = meanings[0].get("gloss_l1", "") if meanings else ""
    entry = LexicalEntry(
        lang_pair=pair,
        lemma_l2=final_lemma,
        lemma_l1_primary=gloss,
        pos=final_pos,
        cefr=profile.cefr_level,
        content=content,
        source="ai",
        created_by_user_id=user_id,
        usage_count=1,
    )
    apply_lexical_keys(entry)
    try:
        async with db.begin_nested():
            db.add(entry)
            await db.flush()
        return content, entry
    except IntegrityError:
        existing = await find_ready_entry(
            db,
            lang_pair=pair,
            lemma=final_lemma,
            pos=final_pos,
            learning_lang=profile.learning_lang,
        )
        if existing is not None:
            return dict(existing.content), existing
        raise


async def enrich_card(card_id: UUID) -> None:
    """Zadanie w tle dla karty dodanej do nauki. Awaitowalne (testy)."""
    if card_id in _claimed:
        return
    _claimed.add(card_id)
    try:
        await _run_claimed_enrich(card_id)
    finally:
        _claimed.discard(card_id)


async def _run_claimed_enrich(card_id: UUID) -> None:
    try:
        async with _enrich_semaphore():
            try:
                await asyncio.wait_for(
                    _enrich_card_unlocked(card_id),
                    timeout=_ENRICH_TIMEOUT_S,
                )
            except TimeoutError:
                logger.error(
                    "Enrichment timeout card=%s after %ss",
                    card_id,
                    _ENRICH_TIMEOUT_S,
                )
                async with async_session_factory() as db:
                    card = (
                        await db.execute(
                            select(LearningCard).where(LearningCard.id == card_id)
                        )
                    ).scalar_one_or_none()
                    if card is not None and card.enrichment_status != STATUS_READY:
                        _apply_enrich_retry(card, TimeoutError("enrichment_timeout"))
                        await db.commit()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Enrichment karty %s wywalił się", card_id)
        await _mark_enrich_failed(card_id, "enrichment_crash")


async def _enrich_card_unlocked(card_id: UUID) -> None:
    async with async_session_factory() as db:
        card = (
            await db.execute(select(LearningCard).where(LearningCard.id == card_id))
        ).scalar_one_or_none()
        if card is None:
            return
        if card.enrichment_status == STATUS_READY and content_is_complete(card.content):
            return
        if card.enrichment_status == STATUS_PREPARING:
            retry_at = card.enrichment_retry_at
            if retry_at is not None and retry_at > datetime.now(UTC):
                return
        if card.enrichment_status == STATUS_FAILED:
            return
        if card.enrichment_status == STATUS_PREPARATION_PROBLEM:
            return

        card.enrichment_status = STATUS_PENDING
        await db.flush()

        content0 = dict(card.content or {})
        if content0.get("schema_version") == "import_display.v1":
            card.enrichment_status = STATUS_READY
            _clear_enrich_retry(card)
            await db.commit()
            from app.services.push import notify_cards_ready

            await notify_cards_ready(db, card.user_id)
            return

        profile = (
            await db.execute(
                select(LanguageProfile).where(LanguageProfile.id == card.profile_id)
            )
        ).scalar_one_or_none()
        if profile is None:
            return

        try:
            if await hydrate_from_lexical_cache(db, card, profile):
                await db.commit()
                from app.services.push import notify_cards_ready

                await notify_cards_ready(db, card.user_id)
                return

            if not _card_lookup_resolved(card):
                user = (
                    await db.execute(select(User).where(User.id == card.user_id))
                ).scalar_one_or_none()
                if user is not None:
                    resolved = await LexicalService(db).best_lookup_candidate(
                        user, card.profile_id, card.lemma_l2
                    )
                    resolved_lemma = (resolved or {}).get("lemma") if resolved else None
                    articles = articles_for(profile.learning_lang)
                    same_headword = bool(
                        resolved_lemma
                        and in_learning_lemma(
                            resolved_lemma,
                            lemma_keys(card.lemma_l2, articles),
                            articles,
                        )
                    )
                    if resolved and same_headword:
                        resolved_pos = resolved.get("pos")
                        if card.pos and resolved_pos and not same_pos_bucket(card.pos, resolved_pos):
                            resolved = None
                    if resolved and same_headword:
                        card.lemma_l2 = resolved_lemma or card.lemma_l2
                        card.pos = resolved.get("pos") or card.pos
                        card.gloss_primary = resolved.get("gloss") or card.gloss_primary
                        if resolved.get("lexical_entry_id"):
                            card.lexical_entry_id = UUID(resolved["lexical_entry_id"])
                        card.content = build_pending_content(
                            lemma=card.lemma_l2,
                            pos=card.pos,
                            gloss=card.gloss_primary,
                            learning_lang=profile.learning_lang,
                        )
                        content0 = dict(card.content or {})

            entry_kind = (content0.get("entry_kind") or "lemma").strip().lower()
            schema0 = content0.get("schema_version") or "vocabulario.card.v1"
            if schema0 == "vocabulario.adaptive.v1" or entry_kind in {
                "phrase",
                "construction",
                "sentence",
                "other",
            }:
                src = content0.get("source_import") or {}
                content = await enrich_adaptive_card_content(
                    profile,
                    headword=card.lemma_l2,
                    entry_kind=entry_kind if entry_kind != "lemma" else "other",
                    gloss=card.gloss_primary or src.get("gloss_hint"),
                    pos=card.pos,
                    base_lemma=src.get("base_lemma") or content0.get("related_lemma"),
                    pattern=src.get("pattern") or content0.get("pattern"),
                )
                entry = None
            else:
                content, entry = await _resolve_content(
                    db,
                    profile,
                    card.lemma_l2,
                    card.pos,
                    user_id=card.user_id,
                    gloss_hint=card.gloss_primary,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Enrichment karty %s nie powiódł się", card_id)
            from app.services.app_log import log_event

            await log_event(
                level="error",
                category="enrichment",
                event="enrichment_failed",
                status="error",
                user_id=card.user_id,
                profile_id=card.profile_id,
                entity_type="card",
                entity_id=str(card_id),
                message=f"enrichment failed {card.lemma_l2!r}",
                payload={"lemma": card.lemma_l2, "pos": card.pos},
                exc=exc,
            )
            _apply_enrich_retry(card, exc)
            await db.commit()
            return

        meanings = content.get("meanings") or []
        card.content = content
        card.pos = content.get("pos") or card.pos
        card.gloss_primary = (
            meanings[0].get("gloss_l1") if meanings else card.gloss_primary
        )
        if entry is not None:
            card.lexical_entry_id = entry.id
        card.enrichment_status = STATUS_READY
        _clear_enrich_retry(card)
        await db.commit()
        from app.services.push import notify_cards_ready

        await notify_cards_ready(db, card.user_id)


async def resume_pending_enrichment(*, stale_only: bool = False) -> None:
    """Wznowienie pending/preparing. Failed nie jest retry'owany — backoff w preparing."""
    if _resume_lock.locked():
        return
    async with _resume_lock:
        try:
            await _resume_pending_enrichment(stale_only=stale_only)
        except asyncio.CancelledError:
            logger.info("Resume enrichment przerwany (shutdown/reload)")
            return


async def _resume_pending_enrichment(*, stale_only: bool = False) -> None:
    now = datetime.now(UTC)
    preparing_due = and_(
        LearningCard.enrichment_status == STATUS_PREPARING,
        LearningCard.enrichment_retry_at.isnot(None),
        LearningCard.enrichment_retry_at <= now,
    )
    if stale_only:
        cutoff = datetime.now(UTC) - timedelta(seconds=_ENRICH_STALE_S)
        pending_stuck = and_(
            LearningCard.enrichment_status == STATUS_PENDING,
            LearningCard.updated_at < cutoff,
        )
        eligible = or_(pending_stuck, preparing_due)
    else:
        eligible = or_(
            LearningCard.enrichment_status == STATUS_PENDING,
            preparing_due,
        )
    stmt = (
        select(LearningCard.id)
        .where(
            LearningCard.deleted_at.is_(None),
            eligible,
        )
        .limit(_ENRICH_RESUME_BATCH)
    )
    async with async_session_factory() as db:
        rows = await db.execute(stmt)
        card_ids = [row[0] for row in rows.all()]
    spawned = 0
    for card_id in card_ids:
        if card_id in _claimed:
            continue
        spawn_enrich(card_id)
        spawned += 1
    if spawned:
        logger.info(
            "Wznawiam enrichment %s kart (max %s naraz)",
            spawned,
            _ENRICH_CONCURRENCY,
        )
