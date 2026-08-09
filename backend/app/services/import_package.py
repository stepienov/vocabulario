"""Parsowanie plików importu do surowej struktury notatek (bez zgadywania lemma)."""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


class ImportPackageError(ValueError):
    """Nie udało się odczytać pliku importu."""


_MAX_BYTES = 80 * 1024 * 1024


@dataclass
class RawImportDeck:
    """Surowe notatki / linie przed mapowaniem na hasła."""

    kind: str  # "plain" | "notes" | "cards_html" | "anki_package" | "raw_text"
    notes: list[list[str]] = field(default_factory=list)
    field_names: list[str] | None = None
    meta: dict = field(default_factory=dict)
    # Pełny tekst źródłowy (wklejka/CSV) — do LLM analizy formatu
    raw_text: str | None = None

    @property
    def is_plain_word_list(self) -> bool:
        if self.kind == "plain":
            return True
        if not self.notes:
            return False
        return all(len(n) == 1 for n in self.notes)

    @property
    def needs_format_analysis(self) -> bool:
        """Czy przed mapowaniem pól trzeba zapytać LLM o segmentację raw tekstu."""
        if self.kind in {"anki_package", "cards_html"}:
            return False
        if "guid column" in self.meta or "notetype column" in self.meta:
            return False
        return bool(self.raw_text and self.raw_text.strip())


def extract_words_from_upload(filename: str | None, data: bytes) -> list[str]:
    """Kompatybilność: surowy extract + naiwne pierwsze pole (bez LLM)."""
    deck = load_raw_import(filename, data)
    return words_from_raw_deck_naive(deck)


def load_raw_import(filename: str | None, data: bytes) -> RawImportDeck:
    if not data:
        raise ImportPackageError("Pusty plik.")
    if len(data) > _MAX_BYTES:
        raise ImportPackageError("Plik jest za duży (max 80 MB).")

    name = (filename or "").lower().strip()
    if name.endswith((".apkg", ".colpkg")) or (
        data[:2] == b"PK" and _looks_like_anki_zip(data)
    ):
        return load_anki_package(data)

    if name.endswith((".xlsx", ".xls")):
        raise ImportPackageError(
            "Excel (.xlsx) na razie nieobsługiwany — zapisz jako CSV albo TXT."
        )

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise ImportPackageError(
                "Nie udało się odczytać pliku jako tekst. "
                "Użyj CSV/TSV/TXT albo .apkg / .colpkg."
            ) from exc

    return load_text_import(text)


def load_text_import(text: str) -> RawImportDeck:
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    meta: dict[str, str] = {}
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("#"):
            if ":" in line:
                key, val = line[1:].split(":", 1)
                meta[key.strip().lower()] = val.strip()
            body_start = i + 1
            continue
        body_start = i
        break

    body = "\n".join(lines[body_start:])
    separator = "\t"
    if meta.get("separator", "").lower() in ("comma", ","):
        separator = ","
    elif meta.get("separator", "").lower() in ("semicolon", ";"):
        separator = ";"

    # Anki Notes z metadanymi kolumn — już posegmentowane
    if "guid column" in meta or "notetype column" in meta:
        notes = _parse_anki_notes_tsv(body, separator=separator, meta=meta)
        return RawImportDeck(
            kind="notes", notes=notes, field_names=None, meta=meta, raw_text=body
        )

    # Anki Cards HTML (często wieloliniowe cytowane pola)
    if meta.get("html", "").lower() == "true" or (
        'class=""front' in body or 'class="front' in body or "answer-word" in body
    ):
        notes = _parse_anki_cards_tsv(body, separator=separator)
        if notes:
            return RawImportDeck(
                kind="cards_html",
                notes=notes,
                field_names=["Front", "Back"],
                meta=meta,
                raw_text=body,
            )

    # Tekst / Quizlet / mieszanki — NIE zgadujemy formatu tu.
    # Zostawiamy raw_text; LLM zwróci instrukcję segmentacji.
    # notes = tylko tymczasowy fallback (mock / awaria LLM).
    notes = _parse_generic_table(
        body, separator=separator if "\t" in body or separator != "\t" else None
    )
    if notes and all(len(n) == 1 for n in notes):
        return RawImportDeck(kind="plain", notes=notes, meta=meta, raw_text=body)
    if notes:
        return RawImportDeck(kind="notes", notes=notes, meta=meta, raw_text=body)
    if body.strip():
        return RawImportDeck(kind="raw_text", notes=[], meta=meta, raw_text=body)
    raise ImportPackageError("W pliku nie znaleziono haseł ani notatek.")


def load_anki_package(data: bytes) -> RawImportDeck:
    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "deck.apkg"
        zpath.write_bytes(data)
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                db_bytes = _read_best_anki_db(zf)
                db_path = Path(tmp) / "collection.db"
                db_path.write_bytes(db_bytes)
        except zipfile.BadZipFile as exc:
            raise ImportPackageError("Uszkodzony lub nieprawidłowy pakiet Anki.") from exc

        conn = sqlite3.connect(db_path)
        try:
            field_names = _field_names_from_col(conn)
            rows = conn.execute("SELECT flds FROM notes").fetchall()
        except sqlite3.Error as exc:
            raise ImportPackageError("Nie udało się odczytać bazy z pakietu Anki.") from exc
        finally:
            conn.close()

    notes: list[list[str]] = []
    for (flds,) in rows:
        if not flds:
            continue
        fields = [_clean_field(f) for f in str(flds).split("\x1f")]
        if _is_anki_stub_note(fields):
            continue
        if any(fields):
            notes.append(fields)

    if not notes:
        raise ImportPackageError(
            "Pakiet nie zawiera odczytywalnych notatek "
            "(częsty przypadek: AnkiDroid .apkg z anki21b). "
            "Użyj eksportu Notes (.txt) albo .apkg z Anki desktop."
        )

    return RawImportDeck(
        kind="anki_package",
        notes=notes,
        field_names=field_names,
        meta={"note_count": str(len(notes))},
    )


def words_from_raw_deck_naive(deck: RawImportDeck) -> list[str]:
    """Fallback bez LLM: plain list albo pierwsze krótkie pole."""
    if deck.is_plain_word_list:
        return _dedupe([n[0] for n in deck.notes if n and n[0]])

    # Prefer znane nazwy pól
    idx = None
    if deck.field_names:
        for prefer in ("spanish", "lemma", "word", "front", "l2", "target", "verb"):
            for i, name in enumerate(deck.field_names):
                if prefer in name.lower().replace(" ", ""):
                    idx = i
                    break
            if idx is not None:
                break
        if idx is None and "Spanish" in deck.field_names:
            idx = deck.field_names.index("Spanish")

    out: list[str] = []
    for note in deck.notes:
        if idx is not None and idx < len(note) and note[idx]:
            out.append(note[idx][:80])
            continue
        for cell in note:
            if _is_likely_lemma(cell):
                out.append(cell[:80])
                break
    words = _dedupe(out)
    if not words:
        raise ImportPackageError("Nie udało się wyciągnąć haseł z pliku.")
    return words


def apply_field_index(deck: RawImportDeck, field_index: int) -> list[str]:
    out: list[str] = []
    for note in deck.notes:
        if field_index < 0 or field_index >= len(note):
            continue
        val = (note[field_index] or "").strip()
        if not val:
            continue
        # z HTML kart — spróbuj wyciągnąć krótkie hasło z class
        if "<" in val:
            m = re.search(
                r'class=["\'](?:answer-word|front-word|word)["\'][^>]*>([^<]+)',
                val,
                re.I,
            )
            if m:
                val = m.group(1).strip()
            else:
                val = _strip_html(val)
        if val and len(val) <= 80:
            out.append(val)
    words = _dedupe(out)
    if not words:
        raise ImportPackageError("Po mapowaniu pól nie zostało żadnych haseł.")
    return words


def apply_html_class(deck: RawImportDeck, css_class: str) -> list[str]:
    pattern = re.compile(
        rf'class=["\']{re.escape(css_class)}["\'][^>]*>([^<]+)',
        re.I,
    )
    out: list[str] = []
    for note in deck.notes:
        blob = "\n".join(note)
        for m in pattern.finditer(blob):
            val = m.group(1).strip()
            if val:
                out.append(val)
                break
    words = _dedupe(out)
    if not words:
        raise ImportPackageError(
            f"Nie znaleziono haseł w klasie HTML „{css_class}”."
        )
    return words


def sample_notes_for_llm(deck: RawImportDeck, limit: int = 12) -> list[list[str]]:
    """Równomierna próbka notatek, pola przycięte pod prompt."""
    if not deck.notes:
        return []
    n = len(deck.notes)
    if n <= limit:
        idxs = list(range(n))
    else:
        step = max(n // limit, 1)
        idxs = list(range(0, n, step))[:limit]
    samples: list[list[str]] = []
    for i in idxs:
        row = []
        for cell in deck.notes[i]:
            text = cell if len(cell) <= 220 else cell[:220] + "…"
            row.append(text)
        samples.append(row)
    return samples


def parse_import_text(raw: str) -> list[str]:
    """Wklejka tekstowa — plain albo tabela; bez LLM (ingest używa LLM osobno dla plików)."""
    deck = load_text_import(raw)
    return words_from_raw_deck_naive(deck)


def words_from_anki_package(data: bytes) -> list[str]:
    return words_from_raw_deck_naive(load_anki_package(data))


# --- internals ---


def _read_best_anki_db(zf: zipfile.ZipFile) -> bytes:
    names = set(zf.namelist())
    for candidate in ("collection.anki21", "collection.anki2"):
        if candidate not in names:
            continue
        raw = zf.read(candidate)
        if _db_has_real_notes(raw):
            return raw
    if "collection.anki21b" in names:
        raise ImportPackageError(
            "Talia jest w formacie anki21b (skompresowany). "
            "Wyeksportuj z Anki ze zgodnością wstecz albo jako Notes (.txt)."
        )
    raise ImportPackageError("To nie wygląda na prawidłowy plik .apkg / .colpkg.")


def _db_has_real_notes(db_bytes: bytes) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "t.db"
        path.write_bytes(db_bytes)
        try:
            conn = sqlite3.connect(path)
            try:
                rows = conn.execute("SELECT flds FROM notes").fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            return False
    real = 0
    for (flds,) in rows:
        fields = str(flds or "").split("\x1f")
        if _is_anki_stub_note(fields):
            continue
        if any(f.strip() for f in fields):
            real += 1
    return real > 0


def _is_anki_stub_note(fields: list[str]) -> bool:
    blob = " ".join(fields)
    return "Zaktualizuj Anki" in blob or "Update to the latest Anki" in blob


def _looks_like_anki_zip(data: bytes) -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "probe.zip"
            zpath.write_bytes(data)
            with zipfile.ZipFile(zpath, "r") as zf:
                names = set(zf.namelist())
            return bool(
                names
                & {
                    "collection.anki2",
                    "collection.anki21",
                    "collection.anki21b",
                }
            )
    except zipfile.BadZipFile:
        return False


def _field_names_from_col(conn: sqlite3.Connection) -> list[str] | None:
    try:
        row = conn.execute("SELECT models FROM col").fetchone()
        if not row or not row[0]:
            return None
        models = json.loads(row[0])
        # weź najczęściej używany model z notes
        mid_row = conn.execute(
            "SELECT mid, COUNT(*) AS c FROM notes GROUP BY mid ORDER BY c DESC LIMIT 1"
        ).fetchone()
        if not mid_row:
            return None
        mid = str(mid_row[0])
        model = models.get(mid) or models.get(int(mid))  # type: ignore[arg-type]
        if model is None:
            # keys czasem int w JSON jako str
            for k, v in models.items():
                if str(k) == mid:
                    model = v
                    break
        if not model:
            return None
        names = [str(f.get("name") or f"Field{i}") for i, f in enumerate(model.get("flds") or [])]
        return names or None
    except Exception:
        return None


def _parse_anki_notes_tsv(body: str, separator: str, meta: dict[str, str]) -> list[list[str]]:
    guid_col = _meta_col(meta, "guid column")
    notetype_col = _meta_col(meta, "notetype column")
    deck_col = _meta_col(meta, "deck column")
    tags_col = _meta_col(meta, "tags column")
    skip = {c for c in (guid_col, notetype_col, deck_col, tags_col) if c is not None}

    notes: list[list[str]] = []
    reader = csv.reader(io.StringIO(body), delimiter=separator, quotechar='"')
    for row in reader:
        if not row or all(not (c or "").strip() for c in row):
            continue
        fields = [
            _clean_field(cell)
            for i, cell in enumerate(row)
            if i not in skip
        ]
        if fields and any(fields):
            notes.append(fields)
    return notes


def _parse_anki_cards_tsv(body: str, separator: str) -> list[list[str]]:
    notes: list[list[str]] = []
    reader = csv.reader(io.StringIO(body), delimiter=separator, quotechar='"')
    for row in reader:
        if not row:
            continue
        # Zachowaj surowy HTML (klasy CSS); LLM / extractor class na tym działa.
        raw_cells = [(c or "").strip() for c in row[:2]]
        if any(raw_cells):
            notes.append(raw_cells)
    return notes


def _parse_generic_table(body: str, separator: str | None) -> list[list[str]]:
    """Tymczasowy fallback (mock / awaria). Prawdziwa segmentacja = LLM + apply_import_format."""
    if not body.strip():
        return []
    sep = separator
    sample = next((ln for ln in body.split("\n") if ln.strip() and not ln.strip().startswith("#")), "")
    if sep is None:
        if "\t" in sample:
            sep = "\t"
        elif ";" in sample:
            sep = ";"
        elif "," in sample:
            sep = ","
        else:
            return [
                [_clean_field(ln)]
                for ln in body.split("\n")
                if ln.strip() and not ln.strip().startswith("#")
            ]

    notes: list[list[str]] = []
    reader = csv.reader(io.StringIO(body), delimiter=sep, quotechar='"')
    for row in reader:
        if not row or (len(row) == 1 and not row[0].strip()):
            continue
        if row[0].strip().startswith("#"):
            continue
        notes.append([_clean_field(c) for c in row])
    return notes


def apply_import_format(raw_text: str, fmt: dict) -> tuple[list[list[str]], list[str] | None]:
    """Wykonaj instrukcję segmentacji z LLM na całym tekście → notatki + nazwy pól."""
    if fmt.get("already_segmented"):
        raise ImportPackageError(
            "LLM oznaczył already_segmented, ale wywołano apply_import_format na raw."
        )
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return [], None

    # Nowa schema (card_separator) + kompatybilność ze starą (block_separator)
    card_sep, card_val = _normalize_card_separator(fmt)
    cards = _split_into_cards(text, separator=card_sep, value=card_val)

    row_mode = str(fmt.get("row_mode") or "delimited")
    delim_name = str(fmt.get("field_delimiter") or "tab")
    delim = {"tab": "\t", "comma": ",", "semicolon": ";", "none": None}.get(delim_name)
    field_split = str(fmt.get("field_split") or "all")
    append_cont = bool(fmt.get("append_continuation_lines_to_answer"))

    notes: list[list[str]] = []
    for card in cards:
        notes.extend(
            _notes_from_block(
                card,
                row_mode=row_mode,
                delim=delim,
                append_continuation=append_cont,
                field_split=field_split,
            )
        )

    names = fmt.get("inferred_field_names")
    if isinstance(names, list) and names:
        field_names = [str(n) for n in names]
    else:
        field_names = None
    return notes, field_names


def _normalize_card_separator(fmt: dict) -> tuple[str, str | None]:
    """Zwraca (card_separator, value). Mapuje też legacy block_separator."""
    if fmt.get("card_separator"):
        return str(fmt["card_separator"]), (fmt.get("card_separator_value") or None)

    # legacy
    block = str(fmt.get("block_separator") or "none")
    val = fmt.get("block_separator_value") or None
    if block == "literal_line":
        return "custom_string", val
    if block == "blank_lines":
        return "blank_lines", None
    if block == "none":
        # stary „none” = zwykle wiersze / jedna linia TSV
        return "newline", None
    return "newline", None


def _split_into_cards(text: str, *, separator: str, value: str | None) -> list[str]:
    if separator == "semicolon":
        parts = [p.strip() for p in text.split(";")]
        return [p for p in parts if p]
    if separator == "custom_string":
        marker = (value or "").strip()
        if not marker:
            return [text]
        # Separatorem może być cała linia LUB inline (np. |)
        if "\n" in text and any(ln.strip() == marker for ln in text.split("\n")):
            parts: list[str] = []
            buf: list[str] = []
            for ln in text.split("\n"):
                if ln.strip() == marker:
                    chunk = "\n".join(buf).strip()
                    if chunk:
                        parts.append(chunk)
                    buf = []
                else:
                    buf.append(ln)
            chunk = "\n".join(buf).strip()
            if chunk:
                parts.append(chunk)
            return parts or [text]
        return [p.strip() for p in text.split(marker) if p.strip()]
    if separator == "blank_lines":
        return [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if separator == "none":
        return [text]
    # newline — każda niepusta linia; jeśli jedna długa linia bez \n, zostaje 1 karta
    lines = [ln.strip() for ln in text.split("\n") if ln.strip() and not ln.strip().startswith("#")]
    return lines or [text]


def _notes_from_block(
    block: str,
    *,
    row_mode: str,
    delim: str | None,
    append_continuation: bool,
    field_split: str = "all",
) -> list[list[str]]:
    if row_mode == "whole_block_one_field":
        return [[_clean_field(block)]]

    if row_mode == "multiline_first_rest":
        lines = [ln for ln in block.split("\n") if ln.strip() and not ln.strip().startswith("#")]
        if not lines:
            return []
        if len(lines) == 1:
            if delim and delim in lines[0]:
                return [_split_fields(lines[0], delim, field_split)]
            return [[_clean_field(lines[0])]]
        return [[_clean_field(lines[0]), _clean_field("\n".join(lines[1:]))]]

    if row_mode == "single_line_as_note":
        if delim and delim in block and "\n" not in block.strip():
            return [_split_fields(block, delim, field_split)]
        return [
            [_clean_field(ln)]
            for ln in block.split("\n")
            if ln.strip() and not ln.strip().startswith("#")
        ]

    # delimited
    if not delim:
        return [[_clean_field(block)]]

    # Jedna karta bez newline (np. po split Quizlet po ;)
    if "\n" not in block:
        if delim not in block:
            return [[_clean_field(block)]]
        return [_split_fields(block, delim, field_split)]

    if delim not in block:
        return _notes_from_block(
            block,
            row_mode="multiline_first_rest",
            delim=None,
            append_continuation=False,
            field_split=field_split,
        )

    notes: list[list[str]] = []
    pending_extra: list[str] = []

    def flush_extra() -> None:
        nonlocal pending_extra
        if not pending_extra or not notes:
            pending_extra = []
            return
        if append_continuation and len(notes[-1]) >= 2:
            extra = "\n".join(pending_extra)
            prev = notes[-1]
            ans = (prev[1] + "\n" + extra).strip() if prev[1] else extra
            notes[-1] = [prev[0], _clean_field(ans), *prev[2:]]
        elif append_continuation and len(notes[-1]) == 1:
            notes[-1] = [notes[-1][0], _clean_field("\n".join(pending_extra))]
        pending_extra = []

    for ln in block.split("\n"):
        if not ln.strip() or ln.strip().startswith("#"):
            flush_extra()
            continue
        if delim in ln:
            flush_extra()
            parts = _split_fields(ln, delim, field_split)
            if any(parts):
                notes.append(parts)
            continue
        if append_continuation and notes:
            pending_extra.append(ln.strip())
        else:
            flush_extra()
            notes.append([_clean_field(ln)])
    flush_extra()
    return notes


def _split_fields(cell: str, delim: str, field_split: str) -> list[str]:
    if field_split == "first_only":
        left, _, right = cell.partition(delim)
        return [_clean_field(left), _clean_field(right)]
    return [_clean_field(c) for c in cell.split(delim)]


def _meta_col(meta: dict[str, str], key: str) -> int | None:
    val = meta.get(key)
    if not val:
        return None
    try:
        return int(val) - 1
    except ValueError:
        return None


def _clean_field(s: str) -> str:
    return _strip_html(s or "").strip().strip('"')


def _strip_html(s: str) -> str:
    raw = s or ""
    has_markup = "<" in raw or "[anki:tts" in raw.lower()
    if not has_markup:
        # Zwykły tekst (wklejka preserve): zachowaj podział na linie
        lines = [
            re.sub(r"[ \t]+", " ", ln).strip()
            for ln in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        ]
        return "\n".join(ln for ln in lines if ln).strip()
    s = re.sub(r"<[^>]+>", " ", raw)
    s = re.sub(r"\[anki:tts[^\]]*].*?\[/anki:tts]", " ", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _is_likely_lemma(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    if s.count(" ") > 2:
        return False
    if len(s) >= 8 and any(ch in s for ch in "#$%^&*|{}[]"):
        return False
    # odrzuć typowe etykiety czasów
    if s.lower() in {
        "imperfecto",
        "indefinido",
        "perfecto",
        "subjuntivo",
        "presente",
        "futuro",
        "condicional",
    }:
        return False
    return any(ch.isalpha() for ch in s)


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        key = w.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(w.strip())
    return out
