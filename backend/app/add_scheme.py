"""Add a scheme to the library from official web pages or PDFs. Free: no API key needed.

Run from backend/ with the venv active:

  python -m app.add_scheme --id pm-mudra --name "PM Mudra Yojana" \\
      --url https://example.gov.in/mudra-guidelines.pdf \\
      --url https://example.gov.in/mudra-faq \\
      --alias mudra --alias "pm mudra"

Then rebuild the index and restart the backend:

  python -m app.ingest

What it does
  * downloads each link (https only, public websites only, 25 MB limit)
  * PDFs are saved as they are (page numbers are kept in the citations)
  * web pages are converted to plain text and saved as .md files with the source link
  * registers the scheme name and aliases so questions that mention it search only its documents

It does NOT write eligibility rules. Those need a person to read the guidelines, so a scheme added
this way appears in Ask and Compare but not in the Eligibility checklist until you add its
"criteria" to data/schemes.json.

By default only links on WEB_ALLOWED_DOMAINS (gov.in, nic.in ...) are accepted. Use --any-domain for
an official site outside those (for example a bank or board website), after checking it is genuine.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx

from . import config, eligibility, web_search

MAX_BYTES = 25_000_000
MIN_WORDS = 40
DEV = re.compile(r"[ऀ-ॿ]")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def download(url: str, any_domain: bool = False, transport: httpx.BaseTransport | None = None):
    """Return (final_url, body, content_type). Raises ValueError with a plain-language reason."""
    cur = url
    with httpx.Client(
        timeout=30, follow_redirects=False, headers={"User-Agent": web_search.USER_AGENT}, transport=transport
    ) as client:
        for _ in range(5):
            p = urlparse(cur)
            if p.scheme != "https" or not p.hostname:
                raise ValueError(f"only https links are accepted: {cur}")
            if not any_domain and not web_search.host_allowed(p.hostname):
                raise ValueError(
                    f"{p.hostname} is not on WEB_ALLOWED_DOMAINS. Use --any-domain if it is an official site."
                )
            if not web_search._public(p.hostname):
                raise ValueError(f"{p.hostname} is not a public website address")
            with client.stream("GET", cur) as r:
                if r.is_redirect:
                    cur = urljoin(cur, r.headers.get("location", ""))
                    continue
                r.raise_for_status()
                data = bytearray()
                for part in r.iter_bytes():
                    data += part
                    if len(data) > MAX_BYTES:
                        raise ValueError("the file is larger than 25 MB")
                return cur, bytes(data), r.headers.get("content-type", "").lower()
    raise ValueError("too many redirects")


def _read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def add_scheme(
    scheme_id: str,
    name: str,
    urls: list[str],
    aliases: list[str] | None = None,
    lang: str | None = None,
    any_domain: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    scheme_id = slug(scheme_id)
    if not scheme_id or not name.strip() or not urls:
        raise ValueError("a scheme id, a name and at least one --url are required")

    docs = config.DOCS_DIR
    docs.mkdir(parents=True, exist_ok=True)
    manifest_path = docs / "sources.json"
    manifest = _read_json(manifest_path, {})
    saved, skipped = [], []

    for i, url in enumerate(urls, start=1):
        try:
            final, body, ctype = download(url, any_domain, transport)
        except Exception as e:
            skipped.append((url, str(e) or type(e).__name__))
            continue

        if "pdf" in ctype or final.lower().endswith(".pdf") or body[:5] == b"%PDF-":
            fname = f"{scheme_id}_{i}.pdf"
            (docs / fname).write_bytes(body)
            sample = " ".join(t for _, t in web_search.pdf_pages(body)[:3])
            manifest[fname] = {
                "scheme": scheme_id,
                "title": f"{name} (document {i})",
                "url": final,
                "lang": lang or ("hi" if DEV.search(sample) else "en"),
            }
            saved.append(fname)
            continue

        title, text = web_search.html_to_text(body.decode("utf-8", errors="replace"))
        if len(text.split()) < MIN_WORDS:
            skipped.append((url, "almost no readable text (the page may need JavaScript). Download its PDF instead."))
            continue
        fname = f"{scheme_id}_{i}.md"
        one_line = re.sub(r"\s+", " ", title or name).strip()
        page_lang = lang or ("hi" if DEV.search(text) else "en")
        front = f"---\nscheme: {scheme_id}\ntitle: {one_line}\nurl: {final}\nlang: {page_lang}\n---\n"
        (docs / fname).write_text(front + text + "\n", encoding="utf-8")
        saved.append(fname)

    if saved:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        schemes_path = eligibility.SCHEMES_FILE
        schemes = _read_json(schemes_path, {})
        entry = schemes.setdefault(scheme_id, {"name": name.strip(), "criteria": [], "aliases": []})
        wanted = [a.strip().lower() for a in (aliases or [])] + [name.strip().lower(), scheme_id]
        entry["aliases"] = list(dict.fromkeys(entry.get("aliases", []) + [a for a in wanted if a]))
        schemes_path.write_text(json.dumps(schemes, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"scheme": scheme_id, "saved": saved, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Add a scheme to the library from official links.")
    ap.add_argument("--id", required=True, help="short id, e.g. pm-mudra")
    ap.add_argument("--name", required=True, help='display name, e.g. "PM Mudra Yojana"')
    ap.add_argument("--url", action="append", required=True, help="official page or PDF (repeat for several)")
    ap.add_argument("--alias", action="append", default=[], help="other names people use (repeat for several)")
    ap.add_argument("--lang", choices=["en", "hi"], help="document language (auto-detected if omitted)")
    ap.add_argument("--any-domain", action="store_true", help="allow an official site outside WEB_ALLOWED_DOMAINS")
    a = ap.parse_args(argv)

    try:
        res = add_scheme(a.id, a.name, a.url, a.alias, a.lang, a.any_domain)
    except ValueError as e:
        print(f"Error: {e}")
        return 2
    for f in res["saved"]:
        print(f"saved   {config.DOCS_DIR / f}")
    for url, why in res["skipped"]:
        print(f"skipped {url}\n        {why}")
    if not res["saved"]:
        print("\nNothing was saved.")
        return 1
    print("\nNext:\n  1. Open the saved files and check they contain the scheme's real text.")
    print("  2. python -m app.ingest")
    print("  3. Restart the backend.")
    print("Eligibility rules are not added automatically; see data/schemes.json to add them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
