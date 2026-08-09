"""Pobieranie haseł z publicznych URL Quizlet / AnkiWeb."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

from app.services.import_package import ImportPackageError, words_from_anki_package

_QUIZLET_ID = re.compile(
    r"quizlet\.com/(?:[a-z]{2}/)?(\d+)(?:/|$)",
    re.IGNORECASE,
)
_ANKIWEB_ID = re.compile(
    r"ankiweb\.net/shared/info/(\d+)",
    re.IGNORECASE,
)

_BROWSER_HEADERS = {
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
}


class ImportUrlError(ValueError):
    """Nie udało się pobrać zestawu z URL."""


def detect_import_url(text: str) -> str | None:
    """URL tylko gdy wklejka to pojedyncza linia z linkiem Quizlet/AnkiWeb."""
    raw = (text or "").strip()
    if not raw:
        return None
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) != 1:
        return None
    first = lines[0].strip().strip("<>").strip()
    if not first.startswith("http://") and not first.startswith("https://"):
        if "quizlet.com/" in first or "ankiweb.net/shared/" in first:
            first = "https://" + first.lstrip("/")
        else:
            return None
    host = urlparse(first).netloc.lower()
    if "quizlet.com" in host or "ankiweb.net" in host:
        return first
    return None


async def fetch_words_from_url(url: str) -> list[str]:
    if _QUIZLET_ID.search(url):
        return await asyncio.to_thread(_fetch_quizlet_sync, url)
    if _ANKIWEB_ID.search(url):
        return await asyncio.to_thread(_fetch_ankiweb_sync, url)
    raise ImportUrlError("Obsługiwane są tylko linki Quizlet i AnkiWeb (shared deck).")


def _http_get(url: str, *, params: dict | None = None, headers: dict | None = None):
    """GET z fingerprintem przeglądarki (curl_cffi), fallback httpx."""
    hdrs = {**_BROWSER_HEADERS, **(headers or {})}
    try:
        from curl_cffi import requests as creq

        last = None
        # chrome131 bywa świeżo zablokowany — rotacja fingerprintów
        for impersonate in (
            "chrome124",
            "chrome123",
            "chrome120",
            "safari17_0",
            "edge101",
            "chrome131",
        ):
            res = creq.get(
                url,
                params=params,
                headers=hdrs,
                impersonate=impersonate,
                timeout=60,
                allow_redirects=True,
            )
            last = res
            if res.status_code < 400 and not _looks_like_captcha(res):
                return res
        return last
    except Exception:
        import httpx

        with httpx.Client(timeout=60.0, follow_redirects=True, headers=hdrs) as client:
            return client.get(url, params=params)


def _looks_like_captcha(res) -> bool:
    text = (res.text or "")[:800].lower()
    if "captcha" in text or "just a moment" in text:
        return True
    if "px" in text and "init.js" in text:
        return True
    if '"appid"' in text and "jsclientsrc" in text:
        return True
    return False


def _fetch_quizlet_sync(url: str) -> list[str]:
    m = _QUIZLET_ID.search(url)
    if not m:
        raise ImportUrlError("Nie rozpoznano ID zestawu Quizlet w URL.")
    set_id = m.group(1)
    words: list[str] = []
    page = 1
    paging_token: str | None = None
    per_page = 100

    while page <= 50:
        params: dict[str, str] = {
            "filters[studiableContainerId]": set_id,
            "filters[studiableContainerType]": "1",
            "perPage": str(per_page),
            "page": str(page),
        }
        if paging_token:
            params["pagingToken"] = paging_token
        res = _http_get(
            "https://quizlet.com/webapi/3.4/studiable-item-documents",
            params=params,
            headers={"Referer": url, "Origin": "https://quizlet.com"},
        )
        if res.status_code >= 400:
            if page == 1:
                raise ImportUrlError(
                    "Quizlet zablokował pobranie (captcha / zestaw prywatny). "
                    "Skopiuj słowa i wklej jako listę, albo użyj „Importuj z pliku”."
                )
            raise ImportUrlError(f"Quizlet zwrócił błąd HTTP {res.status_code}.")

        ctype = (res.headers.get("content-type") or "").lower()
        if "json" not in ctype and not str(res.text).lstrip().startswith("{"):
            raise ImportUrlError(
                "Quizlet zwrócił captcha zamiast danych. "
                "Spróbuj później albo wklej listę / plik."
            )

        data = res.json()
        resp = (data.get("responses") or [{}])[0]
        items = ((resp.get("models") or {}).get("studiableItem")) or []
        if not items and page == 1:
            raise ImportUrlError("Nie znaleziono kart w zestawie Quizlet.")

        for it in items:
            term = _quizlet_headword(it)
            if term:
                words.append(term)

        paging = resp.get("paging") or {}
        paging_token = paging.get("token")
        total = paging.get("total")
        if len(items) < per_page:
            break
        if total is not None and len(words) >= int(total):
            break
        page += 1

    return _dedupe(words, empty_msg="Zestaw Quizlet jest pusty lub niedostępny.")


def _quizlet_headword(item: dict) -> str | None:
    """Pierwsza strona karty; przy formacie „lemma - przykład” bierz lemma."""
    sides = item.get("cardSides") or []
    if not sides:
        return None
    media = sides[0].get("media") or []
    text = ""
    for m in media:
        text = (m.get("plainText") or m.get("text") or "").strip()
        if text:
            break
    if not text:
        return None
    # często: reto - "cytat…"
    if " - " in text:
        left = text.split(" - ", 1)[0].strip()
        if left and len(left) <= 60:
            text = left
    # principiante (m,f) - "…"
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    return text or None


def _fetch_ankiweb_sync(url: str) -> list[str]:
    m = _ANKIWEB_ID.search(url)
    if not m:
        raise ImportUrlError("Nie rozpoznano ID talii AnkiWeb w URL.")
    shared_id = m.group(1)

    # Bez podpisanego tokenu ?t= AnkiWeb odmawia (400 missing field t).
    # Próbujemy i tak — gdy kiedyś token nie będzie wymagany / pojawi się inna ścieżka.
    for download_url in (
        f"https://ankiweb.net/svc/shared/download-deck/{shared_id}",
        f"https://ankiweb.net/shared/download/{shared_id}",
    ):
        res = _http_get(download_url, headers={"Referer": url})
        if res.status_code == 200 and (
            res.content[:2] == b"PK"
            or "zip" in (res.headers.get("content-type") or "").lower()
            or "octet-stream" in (res.headers.get("content-type") or "").lower()
        ):
            # octet-stream może być protobufem — tylko ZIP
            if res.content[:2] != b"PK":
                continue
            try:
                return words_from_anki_package(res.content)
            except ImportPackageError as exc:
                raise ImportUrlError(str(exc)) from exc

        body = ""
        try:
            body = res.text.lower()
        except Exception:
            body = ""
        if res.status_code == 400 and ("missing field `t`" in body or "missing field t" in body):
            raise ImportUrlError(
                "AnkiWeb wymaga tokenu pobrania z przeglądarki (chroni przed masowym "
                "ściąganiem). Otwórz link, pobierz .apkg i użyj „Importuj z pliku”."
            )

    raise ImportUrlError(
        "Nie udało się pobrać talii z AnkiWeb. "
        "Pobierz .apkg w przeglądarce i użyj „Importuj z pliku”."
    )


def _dedupe(words: list[str], *, empty_msg: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        key = w.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    if not out:
        raise ImportUrlError(empty_msg)
    return out
