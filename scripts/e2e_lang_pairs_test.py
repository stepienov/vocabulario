"""
Language-pair import + lookup QA harness.

Pairs (6 distinct languages):
  pl → es, en → fr, de → ja

Runs for each pair:
  1) preserve import (paste + CSV file) → commit-display → DB/API check
  2) vocabulario import (paste + CSV) → create cards → wait enrichment → check
  3) lookup L2 lemmas (exact + typo) and L1 glosses (exact + typo)

Usage (from repo root, backend up):
  backend\\.venv\\Scripts\\python scripts\\e2e_lang_pairs_test.py
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "e2e" / "fixtures" / "lang-pairs"
API = "http://127.0.0.1:8000/api/v1"

PAIRS = [
    {
        "id": "pl-es",
        "native": "pl",
        "learning": "es",
        "l2_exact": ["casa", "hablar", "amigo"],
        "l2_typo": [
            {"q": "csa", "expect_lemma": "casa"},
            {"q": "habalr", "expect_lemma": "hablar"},
        ],
        "l1_exact": ["dom", "mówić", "przyjaciel"],
        "l1_typo": [
            {"q": "doem", "expect_lemma": "casa", "expect_gloss": "dom"},
            {"q": "przyjacel", "expect_lemma": "amigo", "expect_gloss": "przyjaciel"},
        ],
    },
    {
        "id": "en-fr",
        "native": "en",
        "learning": "fr",
        "l2_exact": ["maison", "parler", "livre"],
        "l2_typo": [
            {"q": "maisn", "expect_lemma": "maison"},
            {"q": "parller", "expect_lemma": "parler"},
        ],
        "l1_exact": ["house", "book"],
        "l1_typo": [
            {"q": "houes", "expect_lemma": "maison", "expect_gloss": "house"},
            {"q": "boook", "expect_lemma": "livre", "expect_gloss": "book"},
        ],
    },
    {
        "id": "de-ja",
        "native": "de",
        "learning": "ja",
        "l2_exact": ["水", "猫", "本"],
        # Real near-miss kanji still a valid L2 headword — must resolve cleanly.
        "l2_typo": [{"q": "木", "expect_lemma": "木"}],
        "l1_exact": ["Wasser", "Katze", "Buch"],
        "l1_typo": [
            {"q": "Waser", "expect_lemma": "水", "expect_gloss": "Wasser"},
            {"q": "Katzze", "expect_lemma": "猫", "expect_gloss": "Katze"},
        ],
    },
]


class Api:
    def __init__(self, base: str = API):
        self.base = base.rstrip("/")
        self.token: str | None = None

    def _req(self, method: str, path: str, body=None, form=None, files=None, timeout=180):
        url = f"{self.base}{path}"
        headers = {}
        data = None
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if files is not None:
            # multipart via requests if available; else fall back to paste-only note
            import requests

            r = requests.request(
                method,
                url,
                headers=headers,
                data=form or {},
                files=files,
                timeout=timeout,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path} → {r.status_code}: {r.text[:500]}")
            return r.json() if r.content else {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} → {e.code}: {err[:500]}") from e

    def register_or_login(self, email: str, password: str) -> None:
        try:
            tok = self._req("POST", "/auth/register", {"email": email, "password": password})
        except RuntimeError as e:
            if "409" not in str(e) and "already" not in str(e).lower():
                # try login
                pass
            tok = self._req("POST", "/auth/login", {"email": email, "password": password})
        self.token = tok["access_token"]

    def create_profile(self, native: str, learning: str) -> str:
        # reuse existing pair if present
        profiles = self._req("GET", "/profiles")
        for p in profiles:
            app = p.get("app_lang") or p.get("native_lang")
            if app == native and p["learning_lang"] == learning:
                if not p.get("is_active"):
                    self._req("PUT", f"/profiles/{p['id']}/activate")
                return p["id"]
        tenses = {
            "es": ["presente", "preterito_indefinido"],
            "fr": ["present", "passe_compose"],
            "ja": ["polite_nonpast", "polite_past"],
        }.get(learning, [])
        p = self._req(
            "POST",
            "/profiles",
            {
                "app_lang": native,
                "learning_lang": learning,
                "cefr_level": "A2",
                "selected_tenses": tenses,
            },
        )
        return p["id"]

    def lists(self, profile_id: str):
        return self._req("GET", f"/lists?profile_id={profile_id}")

    def learning_list_id(self, profile_id: str) -> str:
        for lst in self.lists(profile_id):
            if lst.get("is_system"):
                return lst["id"]
        raise RuntimeError("No system learning list")

    def ingest_paste(self, profile_id: str, text: str, mode: str):
        return self._req(
            "POST",
            "/imports/ingest",
            {"text": text, "profile_id": profile_id, "mode": mode},
            timeout=300,
        )

    def ingest_file(self, profile_id: str, path: Path, mode: str):
        import requests

        headers = {"Authorization": f"Bearer {self.token}"}
        with path.open("rb") as f:
            r = requests.post(
                f"{self.base}/imports/file",
                headers=headers,
                data={"profile_id": profile_id, "mode": mode},
                files={"file": (path.name, f, "text/csv")},
                timeout=300,
            )
        if r.status_code >= 400:
            raise RuntimeError(f"file import {r.status_code}: {r.text[:500]}")
        return r.json()

    def commit_preserve(self, profile_id: str, list_id: str, cards: list):
        return self._req(
            "POST",
            "/imports/commit-display",
            {"profile_id": profile_id, "list_id": list_id, "cards": cards},
        )

    def create_card(self, profile_id: str, entry: dict):
        return self._req(
            "POST",
            "/cards",
            {
                "lemma": entry["lemma"],
                "pos": entry.get("pos"),
                "gloss": entry.get("gloss") or None,
                "profile_id": profile_id,
                "entry_kind": entry.get("entry_kind") or "lemma",
                "base_lemma": entry.get("base_lemma"),
                "pattern": entry.get("pattern"),
            },
            timeout=120,
        )

    def cards(self, profile_id: str):
        return self._req("GET", f"/cards?profile_id={profile_id}")

    def lookup(self, profile_id: str, text: str):
        return self._req(
            "POST",
            "/lookup",
            {"text": text, "profile_id": profile_id},
            timeout=120,
        )


def strip_csv_comments(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(ln)
    return "\n".join(lines)


def _is_preserve(card: dict) -> bool:
    return ((card.get("content") or {}).get("schema_version") or "") == "import_display.v1"


def wait_enrichment(api: Api, profile_id: str, lemmas: set[str], timeout_s: int = 180) -> dict:
    deadline = time.time() + timeout_s
    last = []
    while time.time() < deadline:
        cards = api.cards(profile_id)
        last = cards
        relevant = [
            c for c in cards if c.get("lemma_l2") in lemmas and not _is_preserve(c)
        ]
        if relevant and all(c.get("enrichment_status") in ("ready", "failed") for c in relevant):
            return {"cards": relevant, "all": cards}
        time.sleep(3)
    return {
        "cards": [c for c in last if c.get("lemma_l2") in lemmas and not _is_preserve(c)],
        "all": last,
        "timeout": True,
    }


def assert_preserve_cards(cards_resp: dict, label: str, report: list):
    cards = cards_resp.get("cards") or []
    if len(cards) < 3:
        report.append(f"FAIL {label}: preserve returned <3 cards ({len(cards)})")
        return
    for c in cards[:3]:
        disp = (c.get("display") or {})
        if not disp.get("prompt") or not disp.get("answer"):
            report.append(f"FAIL {label}: card missing prompt/answer display: {c.get('lemma_l2')}")
            return
    report.append(f"OK   {label}: preserve {len(cards)} cards with display blocks")


def assert_vocab_cards(api_cards: list, expected_lemmas: set[str], label: str, report: list):
    by_lemma = {c["lemma_l2"]: c for c in api_cards}
    found = expected_lemmas & set(by_lemma)
    if len(found) < max(1, len(expected_lemmas) // 2):
        report.append(
            f"FAIL {label}: few vocab cards in DB/API. expected~{expected_lemmas}, found={found}"
        )
        return
    ready = [by_lemma[l] for l in found if by_lemma[l].get("enrichment_status") == "ready"]
    failed = [by_lemma[l] for l in found if by_lemma[l].get("enrichment_status") == "failed"]
    pending = [by_lemma[l] for l in found if by_lemma[l].get("enrichment_status") == "pending"]
    report.append(
        f"INFO {label}: ready={len(ready)} failed={len(failed)} pending={len(pending)} matched={len(found)}"
    )
    for c in ready[:5]:
        content = c.get("content") or {}
        schema = content.get("schema_version")
        gloss = c.get("gloss_primary")
        lang = content.get("language")
        meanings = content.get("meanings") or []
        ok_bits = []
        if gloss:
            ok_bits.append("gloss")
        if schema:
            ok_bits.append(f"schema={schema}")
        if lang:
            ok_bits.append(f"lang={lang}")
        if meanings:
            ok_bits.append(f"meanings={len(meanings)}")
        # language on enrich should match learning when possible
        report.append(f"  card {c['lemma_l2']}: {', '.join(ok_bits) or 'minimal'}")
        if schema == "vocabulario.card.v1" and not meanings and not content.get("similar_words"):
            report.append(f"WARN {label}: lemma card {c['lemma_l2']} ready but thin content")
        elif schema == "1.0" and not meanings and not content.get("similar_words"):
            report.append(f"WARN {label}: legacy card {c['lemma_l2']} ready but thin content")
    if failed:
        for c in failed:
            report.append(
                f"FAIL {label}: enrichment failed for {c['lemma_l2']}: {c.get('enrichment_error')}"
            )


def _gloss_has(gloss: str, needle: str) -> bool:
    g = (gloss or "").casefold()
    n = (needle or "").strip().casefold()
    if not n:
        return True
    if n in g:
        return True
    # tolerate 1-char distance on a gloss token (model may return synonym)
    import unicodedata
    from difflib import SequenceMatcher

    def strip(s: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
        )

    for tok in re.split(r"[,;/|\s]+", g):
        if not tok:
            continue
        if SequenceMatcher(None, strip(tok), strip(n)).ratio() >= 0.85:
            return True
    return False


def assert_lookup(
    api: Api,
    profile_id: str,
    query: str,
    *,
    expect_hit: bool,
    label: str,
    report: list,
    learning_lang: str | None = None,
    require_lemma_ne_query: bool = False,
    require_top_lemma_eq_query: bool = False,
    expect_lemma: str | None = None,
    expect_gloss: str | None = None,
):
    try:
        resp = api.lookup(profile_id, query)
    except Exception as e:
        report.append(f"FAIL {label}: lookup crashed for {query!r}: {e}")
        return
    cands = resp.get("candidates") or []
    if expect_hit and not cands:
        report.append(f"FAIL {label}: lookup {query!r} -> 0 candidates")
        return
    if not cands:
        report.append(f"FAIL {label}: lookup {query!r} -> empty (not acceptable)")
        return

    top = cands[0]
    top_lemma = (top.get("lemma") or "").strip()
    top_gloss = (top.get("gloss") or "").strip()
    q = query.strip()
    lemmas = [(c.get("lemma") or "").strip() for c in cands]

    if require_lemma_ne_query and top_lemma.casefold() == q.casefold():
        report.append(
            f"FAIL {label}: lookup {query!r} echoed L1 as lemma {top_lemma!r} "
            f"(gloss={top_gloss!r})"
        )
        return
    if require_top_lemma_eq_query and top_lemma.casefold() != q.casefold():
        if any(l.casefold() == q.casefold() for l in lemmas):
            report.append(
                f"FAIL {label}: lookup {query!r} has exact lemma but top={top_lemma!r}"
            )
            return
        report.append(
            f"FAIL {label}: lookup {query!r} top={top_lemma!r} "
            f"(expected exact lemma {q!r})"
        )
        return
    if expect_lemma:
        exp = expect_lemma.strip()
        if top_lemma.casefold() != exp.casefold():
            if any(l.casefold() == exp.casefold() for l in lemmas):
                report.append(
                    f"FAIL {label}: lookup {query!r} has {exp!r} but top={top_lemma!r}"
                )
                return
            report.append(
                f"FAIL {label}: lookup {query!r} top={top_lemma!r} "
                f"(expected lemma {exp!r}; gloss={top_gloss!r})"
            )
            return
    if expect_gloss and not _gloss_has(top_gloss, expect_gloss):
        report.append(
            f"FAIL {label}: lookup {query!r} gloss={top_gloss!r} "
            f"missing expected {expect_gloss!r}"
        )
        return
    report.append(
        f"OK   {label}: {query!r} -> {len(cands)} cand; "
        f"top={top_lemma!r} / {top_gloss!r}"
    )


def run_pair(pair: dict, report: list) -> None:
    pid = pair["id"]
    native, learning = pair["native"], pair["learning"]
    email = f"e2e.pair.{pid}.{uuid.uuid4().hex[:8]}@example.com"
    password = "e2e-test-pass-123"
    api = Api()
    report.append(f"\n===== PAIR {pid} ({native}->{learning}) user={email} =====")
    api.register_or_login(email, password)
    profile_id = api.create_profile(native, learning)
    list_id = api.learning_list_id(profile_id)
    report.append(f"INFO profile={profile_id} list={list_id}")

    paste = strip_csv_comments((FIXTURES / pid / "paste.txt").read_text(encoding="utf-8"))
    csv_path = FIXTURES / pid / "words.csv"
    csv_text = strip_csv_comments(csv_path.read_text(encoding="utf-8"))
    # write cleaned temp csv for upload (no comment lines)
    tmp_csv = FIXTURES / pid / "_upload.csv"
    tmp_csv.write_text(csv_text, encoding="utf-8")

    # --- PRESERVE paste ---
    try:
        pres = api.ingest_paste(profile_id, paste, "preserve")
        cards = pres.get("cards") or []
        assert_preserve_cards(pres, f"{pid}/preserve-paste", report)
        if cards:
            commit = api.commit_preserve(
                profile_id,
                list_id,
                [
                    {
                        "key": c.get("key") or f"k{i}",
                        "lemma_l2": c.get("lemma_l2") or "",
                        "gloss_primary": c.get("gloss_primary"),
                        "display": c.get("display"),
                    }
                    for i, c in enumerate(cards)
                ],
            )
            report.append(
                f"OK   {pid}/preserve-paste commit created={commit.get('created')} skipped={commit.get('skipped')}"
            )
    except Exception as e:
        report.append(f"FAIL {pid}/preserve-paste: {e}")

    # --- PRESERVE file ---
    try:
        pres_f = api.ingest_file(profile_id, tmp_csv, "preserve")
        assert_preserve_cards(pres_f, f"{pid}/preserve-file", report)
        cards = pres_f.get("cards") or []
        if cards:
            api.commit_preserve(
                profile_id,
                list_id,
                [
                    {
                        "key": c.get("key") or f"f{i}",
                        "lemma_l2": c.get("lemma_l2") or "",
                        "gloss_primary": c.get("gloss_primary"),
                        "display": c.get("display"),
                    }
                    for i, c in enumerate(cards[:5])
                ],
            )
            report.append(f"OK   {pid}/preserve-file commit (first 5)")
    except Exception as e:
        report.append(f"FAIL {pid}/preserve-file: {e}")

    # --- VOCABULARIO paste ---
    expected = set()
    try:
        vocab = api.ingest_paste(profile_id, paste, "vocabulario")
        valid = vocab.get("valid") or []
        invalid = vocab.get("invalid") or []
        report.append(f"INFO {pid}/vocab-paste valid={len(valid)} invalid={len(invalid)} {invalid[:5]}")
        if len(valid) < 3:
            report.append(f"FAIL {pid}/vocab-paste: expected ≥3 valid entries")
        created = []
        for entry in valid:
            try:
                card = api.create_card(profile_id, entry)
                created.append(card.get("lemma_l2") or entry["lemma"])
            except RuntimeError as e:
                if "409" in str(e) or "już" in str(e).lower() or "already" in str(e).lower():
                    created.append(entry["lemma"])
                else:
                    report.append(f"FAIL {pid}/vocab create {entry.get('lemma')}: {e}")
        expected |= set(created)
        waited = wait_enrichment(api, profile_id, set(created), timeout_s=240)
        if waited.get("timeout"):
            report.append(f"WARN {pid}/vocab-paste: enrichment timeout")
        assert_vocab_cards(waited.get("cards") or [], set(created), f"{pid}/vocab-paste", report)
    except Exception as e:
        report.append(f"FAIL {pid}/vocab-paste: {e}")

    # --- VOCABULARIO file ---
    try:
        vocab_f = api.ingest_file(profile_id, tmp_csv, "vocabulario")
        valid = vocab_f.get("valid") or []
        report.append(f"INFO {pid}/vocab-file valid={len(valid)} invalid={len(vocab_f.get('invalid') or [])}")
        created = []
        for entry in valid[:6]:
            try:
                card = api.create_card(profile_id, entry)
                created.append(card.get("lemma_l2") or entry["lemma"])
            except RuntimeError as e:
                if "409" in str(e) or "już" in str(e).lower() or "already" in str(e).lower():
                    created.append(entry["lemma"])
                else:
                    report.append(f"WARN {pid}/vocab-file create {entry.get('lemma')}: {e}")
        waited = wait_enrichment(api, profile_id, set(created), timeout_s=240)
        assert_vocab_cards(waited.get("cards") or [], set(created), f"{pid}/vocab-file", report)
    except Exception as e:
        report.append(f"FAIL {pid}/vocab-file: {e}")

    # --- LOOKUP matrix ---
    for q in pair["l2_exact"]:
        assert_lookup(
            api,
            profile_id,
            q,
            expect_hit=True,
            label=f"{pid}/L2-exact",
            report=report,
            require_top_lemma_eq_query=True,
        )
    for q in pair["l2_typo"]:
        assert_lookup(api, profile_id, q, expect_hit=False, label=f"{pid}/L2-typo", report=report)
    for q in pair["l1_exact"]:
        assert_lookup(
            api,
            profile_id,
            q,
            expect_hit=True,
            label=f"{pid}/L1-exact",
            report=report,
            learning_lang=learning,
            require_lemma_ne_query=True,
        )
    for q in pair["l1_typo"]:
        assert_lookup(api, profile_id, q, expect_hit=False, label=f"{pid}/L1-typo", report=report)

    # DB-ish summary via API
    all_cards = api.cards(profile_id)
    schemas = {}
    for c in all_cards:
        sv = (c.get("content") or {}).get("schema_version") or "?"
        schemas[sv] = schemas.get(sv, 0) + 1
    report.append(f"INFO {pid} card schemas: {schemas} total={len(all_cards)}")


def main() -> int:
    # health
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
            print("health:", r.read().decode())
    except Exception as e:
        print("Backend not up:", e)
        return 2

    report: list[str] = []
    for pair in PAIRS:
        run_pair(pair, report)

    out = ROOT / "e2e" / "fixtures" / "lang-pairs" / "LAST_REPORT.txt"
    text = "\n".join(report) + "\n"
    out.write_text(text, encoding="utf-8")
    # Windows consoles may be cp1250 — avoid UnicodeEncodeError on arrows/CJK.
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    print(f"Wrote {out}")

    fails = [ln for ln in report if ln.startswith("FAIL")]
    print(f"\nSUMMARY: {len(fails)} FAIL lines")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
