"""Web fallback for schemes that are not in the verified library.

Flow:  xAI (Grok) web_search finds official pages  ->  THIS module downloads them  ->
       text is split into passages  ->  the normal gate, LLM and verifier run on them.

Grok is only used to find URLs. Its own written answer is ignored, so every sentence shown
to the user is still checked against page text that this app fetched itself.

Safety: only https pages on WEB_ALLOWED_DOMAINS are fetched, every redirect is re-checked,
hosts that resolve to private addresses are refused, and downloads are size-limited.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from . import config
from .ingest import Chunk, chunk_words

DEV = re.compile(r"[ऀ-ॿ]")
URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
USER_AGENT = "PramaanBot/0.2 (student project; reads official government pages)"
MAX_PDF_PAGES = 30

SEARCH_PROMPT = (
    "Find official Government of India web pages that answer this question about a government "
    "scheme or public service. Prefer the scheme's own portal, myScheme, or a ministry page. "
    "Question: {q}"
)

_cache: dict[str, tuple[float, list[Chunk]]] = {}
_cache_lock = threading.Lock()


def enabled() -> bool:
    return bool(config.WEB_SEARCH and config.XAI_API_KEY)


# ---------------------------------------------------------------- domain safety
def host_allowed(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in config.WEB_ALLOWED_DOMAINS)


def _public(host: str) -> bool:
    """False if the host cannot be resolved or points at a private or local address."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return bool(infos)


def url_ok(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and bool(p.hostname) and host_allowed(p.hostname)


# ---------------------------------------------------------------- finding pages
def extract_urls(resp: dict) -> list[str]:
    """Pull page URLs out of an xAI Responses-API reply, tolerating different shapes."""
    found: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "url_citation" and isinstance(o.get("url"), str):
                found.append(o["url"])
            for k, v in o.items():
                if k == "citations" and isinstance(v, list):
                    for c in v:
                        if isinstance(c, str):
                            found.append(c)
                        elif isinstance(c, dict) and isinstance(c.get("url"), str):
                            found.append(c["url"])
                else:
                    walk(v)
        elif isinstance(o, list):
            for i in o:
                walk(i)

    walk(resp)
    if not found:  # last resort: URLs mentioned anywhere in the reply text
        found = [u.rstrip(".,;:") for u in URL_RE.findall(json.dumps(resp, ensure_ascii=False))]

    clean = []
    for u in found:
        u = urldefrag(u.strip())[0]
        if url_ok(u) and u not in clean:
            clean.append(u)
    return clean[: config.WEB_MAX_PAGES]


def find_pages(question: str) -> list[str]:
    body = {
        "model": config.XAI_MODEL,
        "input": [{"role": "user", "content": SEARCH_PROMPT.format(q=question)}],
        "tools": [
            {"type": "web_search", "filters": {"allowed_domains": config.WEB_ALLOWED_DOMAINS[:5]}}
        ],
    }
    r = httpx.post(
        f"{config.XAI_BASE_URL}/responses",
        headers={"Authorization": f"Bearer {config.XAI_API_KEY}"},
        json=body,
        timeout=60,
    )
    r.raise_for_status()
    return extract_urls(r.json())


# ---------------------------------------------------------------- downloading
def fetch(url: str, transport: httpx.BaseTransport | None = None) -> tuple[str, bytes, str]:
    """Download one page. Returns (final_url, body, content_type). Raises ValueError if unsafe."""
    cur = url
    with httpx.Client(
        timeout=15, follow_redirects=False, headers={"User-Agent": USER_AGENT}, transport=transport
    ) as client:
        for _ in range(4):
            if not url_ok(cur) or not _public(urlparse(cur).hostname):
                raise ValueError("blocked address")
            with client.stream("GET", cur) as r:
                if r.is_redirect:
                    cur = urljoin(cur, r.headers.get("location", ""))
                    continue
                r.raise_for_status()
                data = bytearray()
                for part in r.iter_bytes():
                    data += part
                    if len(data) > config.WEB_MAX_BYTES:
                        raise ValueError("page too large")
                return cur, bytes(data), r.headers.get("content-type", "").lower()
    raise ValueError("too many redirects")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form", "iframe"}
    BLOCK = {"p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "h5", "section", "article", "table"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n\n" if tag in {"p", "h1", "h2", "h3", "section", "article"} else "\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    ex = _TextExtractor()
    ex.feed(html)
    text = re.sub(r"[ \t\xa0]+", " ", "".join(ex.parts))
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return ex.title.strip(), text


def pdf_pages(data: bytes) -> list[tuple[int, str]]:
    import pymupdf

    pages = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            if i > MAX_PDF_PAGES:
                break
            pages.append((i, page.get_text()))
    return pages


# ---------------------------------------------------------------- chunks
def page_to_chunks(url: str, body: bytes, ctype: str) -> list[Chunk]:
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        title, pages = url.rsplit("/", 1)[-1], pdf_pages(body)
    else:
        title, text = html_to_text(body.decode("utf-8", errors="replace"))
        pages = [(None, text)]
    host = urlparse(url).hostname or ""
    title = title or host
    tag = hashlib.sha1(url.encode()).hexdigest()[:8]
    out, n = [], 0
    for page_no, text in pages:
        for piece in chunk_words(text, config.CHUNK_WORDS, config.CHUNK_OVERLAP):
            out.append(
                Chunk(
                    id=f"web-{tag}#{n}",
                    scheme="web",
                    title=title,
                    url=url,
                    lang="hi" if DEV.search(piece) else "en",
                    page=page_no,
                    text=piece,
                )
            )
            n += 1
    return out


def chunks_for_url(url: str) -> list[Chunk]:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < config.WEB_CACHE_TTL:
            return hit[1]
    final, body, ctype = fetch(url)
    chunks = page_to_chunks(final, body, ctype)
    with _cache_lock:
        if len(_cache) >= 50:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[url] = (now, chunks)
    return chunks


def search(question: str) -> list[Chunk]:
    """Find official pages for the question and return their passages. May return []."""
    chunks: list[Chunk] = []
    for url in find_pages(question):
        try:
            chunks += chunks_for_url(url)
        except Exception:  # one bad page must not sink the others
            continue
    return chunks
