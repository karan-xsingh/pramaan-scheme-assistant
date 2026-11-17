import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import config, ratelimit, rag, web_search
from app.ingest import Chunk
from app.main import app
from app.ratelimit import RateLimiter
from app.retriever import TfidfRetriever

KCC_TEXT = (
    "The Kisan Credit Card scheme gives farmers short term credit for crops. "
    "Under the scheme the interest subvention is 2 percent per year and prompt repayment gives "
    "an additional 3 percent benefit. Farmers can apply at any bank branch with land records."
)


def kcc_chunks():
    return [Chunk("web-1#0", "web", "Kisan Credit Card", "https://www.example.gov.in/kcc", "en", None, KCC_TEXT)]


# These tests need a library that does NOT contain the Kisan Credit Card question's words. Schemes
# added later with add_scheme (Mudra, SVANidhi ...) legitimately mention "interest subvention", so the
# tests use a fixed library of the original sample schemes instead of whatever is in data/docs.
ORIGINAL_SCHEMES = {"pm-kisan", "pm-jay", "pmay-g", "pmuy", "apy", "ssy"}


def original_library():
    from app.retriever import _load_chunks

    return TfidfRetriever([c for c in _load_chunks() if c.scheme in ORIGINAL_SCHEMES])


@pytest.fixture(scope="module")
def retriever():
    return original_library()


# ---------------------------------------------------------------- domain rules
def test_host_allowed_matches_subdomains_but_not_lookalikes():
    assert web_search.host_allowed("pmkisan.gov.in")
    assert web_search.host_allowed("www.myscheme.gov.in")
    assert not web_search.host_allowed("gov.in.evil.com")
    assert not web_search.host_allowed("evilgov.in")
    assert not web_search.host_allowed("")


def test_url_ok_requires_https_and_allowed_host():
    assert web_search.url_ok("https://pmkisan.gov.in/a")
    assert not web_search.url_ok("http://pmkisan.gov.in/a")
    assert not web_search.url_ok("https://example.com/a")
    assert not web_search.url_ok("file:///etc/passwd")


# ---------------------------------------------------------------- reading the xAI reply
def test_extract_urls_from_annotations_and_citations():
    resp = {
        "output": [
            {
                "content": [
                    {
                        "text": "see",
                        "annotations": [
                            {"type": "url_citation", "url": "https://pmkisan.gov.in/faq#top"},
                            {"type": "url_citation", "url": "https://example.com/spam"},
                        ],
                    }
                ]
            }
        ],
        "citations": ["https://www.myscheme.gov.in/schemes/x", "http://insecure.gov.in/a"],
    }
    assert web_search.extract_urls(resp) == [
        "https://pmkisan.gov.in/faq",
        "https://www.myscheme.gov.in/schemes/x",
    ]


def test_extract_urls_falls_back_to_urls_in_text_and_caps_count(monkeypatch):
    monkeypatch.setattr(config, "WEB_MAX_PAGES", 2)
    text = " ".join(f"https://a{i}.gov.in/p." for i in range(5))
    assert len(web_search.extract_urls({"output_text": text})) == 2


# ---------------------------------------------------------------- downloading
def test_fetch_blocks_redirect_to_other_domain(monkeypatch):
    monkeypatch.setattr(web_search, "_public", lambda host: True)
    seen = []

    def handler(request: httpx.Request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example.com/x"})

    with pytest.raises(ValueError, match="blocked"):
        web_search.fetch("https://pmkisan.gov.in/a", transport=httpx.MockTransport(handler))
    assert seen == ["https://pmkisan.gov.in/a"]  # the evil host was never requested


def test_fetch_refuses_private_addresses_and_http(monkeypatch):
    monkeypatch.setattr(web_search, "_public", lambda host: False)
    with pytest.raises(ValueError, match="blocked"):
        web_search.fetch("https://pmkisan.gov.in/a", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    monkeypatch.setattr(web_search, "_public", lambda host: True)
    with pytest.raises(ValueError, match="blocked"):
        web_search.fetch("http://pmkisan.gov.in/a", transport=httpx.MockTransport(lambda r: httpx.Response(200)))


def test_fetch_enforces_size_limit_and_returns_page(monkeypatch):
    monkeypatch.setattr(web_search, "_public", lambda host: True)
    monkeypatch.setattr(config, "WEB_MAX_BYTES", 100)
    big = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 500, headers={"content-type": "text/html"}))
    with pytest.raises(ValueError, match="large"):
        web_search.fetch("https://pmkisan.gov.in/a", transport=big)
    monkeypatch.setattr(config, "WEB_MAX_BYTES", 10_000)
    ok = httpx.MockTransport(lambda r: httpx.Response(200, content=b"<p>hi</p>", headers={"content-type": "text/html"}))
    url, body, ctype = web_search.fetch("https://pmkisan.gov.in/a", transport=ok)
    assert body == b"<p>hi</p>" and "html" in ctype


# ---------------------------------------------------------------- text extraction
def test_html_to_text_drops_scripts_and_navigation():
    html = (
        "<html><head><title>PM Test</title><script>var secret=1;</script></head><body>"
        "<nav>Home About Contact</nav><h1>Benefit</h1><p>Farmers get Rs. 6,000 a year.</p>"
        "<footer>Copyright</footer></body></html>"
    )
    title, text = web_search.html_to_text(html)
    assert title == "PM Test"
    assert "6,000" in text and "secret" not in text and "Home About" not in text and "Copyright" not in text


def test_pdf_pages_become_chunks_with_page_numbers():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 700), KCC_TEXT * 2, fontsize=11)
    data = doc.tobytes()
    chunks = web_search.page_to_chunks("https://example.gov.in/kcc.pdf", data, "application/pdf")
    assert chunks and chunks[0].page == 1 and chunks[0].scheme == "web"
    assert "interest subvention" in " ".join(c.text for c in chunks)


# ---------------------------------------------------------------- library first, web second
def _boom(*a, **k):
    raise AssertionError("web search must not be called")


OUT_OF_LIBRARY = "What is the interest subvention under the Kisan Credit Card scheme?"


def test_web_not_used_when_library_answers(retriever, monkeypatch):
    monkeypatch.setattr(web_search, "enabled", lambda: True)
    monkeypatch.setattr(web_search, "search", _boom)
    monkeypatch.setattr("app.llm.available", lambda: False)
    a = rag.answer_question(retriever, "How much does PM-KISAN pay each year?", web_gate=lambda: True)
    assert a.origin == "library" and a.sources


def test_web_not_used_without_gate_or_when_disabled_or_scheme_chosen(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    monkeypatch.setattr(web_search, "search", _boom)
    monkeypatch.setattr(web_search, "enabled", lambda: True)
    assert rag.answer_question(retriever, OUT_OF_LIBRARY).mode == "none"  # no gate given
    assert rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: False).mode == "none"
    assert rag.answer_question(retriever, OUT_OF_LIBRARY, scheme="pm-kisan", web_gate=lambda: True).origin == "library"
    monkeypatch.setattr(web_search, "enabled", lambda: False)
    assert rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: True).mode == "none"


def test_web_fallback_returns_labelled_passages(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    monkeypatch.setattr(web_search, "enabled", lambda: True)
    monkeypatch.setattr(web_search, "search", lambda q: kcc_chunks())
    a = rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: True)
    assert a.origin == "web" and a.mode == "extractive" and a.top_scheme is None
    assert a.sources[0]["origin"] == "web" and a.sources[0]["domain"] == "www.example.gov.in"
    assert any("not from the verified library" in w for w in a.warnings)


def test_web_answer_goes_through_the_verifier(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: True)
    monkeypatch.setattr(web_search, "enabled", lambda: True)
    monkeypatch.setattr(web_search, "search", lambda q: kcc_chunks())

    monkeypatch.setattr("app.llm.chat", lambda *a, **k: "The interest subvention is 2 percent per year [1].")
    good = rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: True)
    assert good.origin == "web" and good.mode == "llm" and good.verification["level"] == "high"

    monkeypatch.setattr("app.llm.chat", lambda *a, **k: "The interest subvention is 9 percent per year [1]. It is 7 percent for all [1].")
    bad = rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: True)
    assert bad.mode == "extractive" and bad.origin == "web"


def test_irrelevant_web_pages_are_rejected_by_the_gate(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    monkeypatch.setattr(web_search, "enabled", lambda: True)
    other = [Chunk("web-2#0", "web", "Passport", "https://www.example.gov.in/p", "en", None,
                   "Apply for a passport at the regional passport office with proof of address and age.")]
    monkeypatch.setattr(web_search, "search", lambda q: other)
    assert rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: True).mode == "none"


def test_web_failure_degrades_to_not_found_with_note(retriever, monkeypatch):
    monkeypatch.setattr("app.llm.available", lambda: False)
    monkeypatch.setattr(web_search, "enabled", lambda: True)

    def fail(q):
        raise TimeoutError

    monkeypatch.setattr(web_search, "search", fail)
    a = rag.answer_question(retriever, OUT_OF_LIBRARY, web_gate=lambda: True)
    assert a.mode == "none" and any("Web search was unavailable" in w for w in a.warnings)


# ---------------------------------------------------------------- API: separate web rate limit
def test_api_web_limit_is_separate_and_stricter(monkeypatch):
    import app.main as main

    monkeypatch.setattr("app.llm.available", lambda: False)
    monkeypatch.setattr(main, "retriever", original_library())
    monkeypatch.setattr(ratelimit, "limiter", RateLimiter(1000))
    monkeypatch.setattr(main, "web_limiter", RateLimiter(1))
    monkeypatch.setattr(web_search, "enabled", lambda: True)
    monkeypatch.setattr(web_search, "search", lambda q: kcc_chunks())
    c = TestClient(app)

    first = c.post("/api/ask", json={"question": OUT_OF_LIBRARY}).json()
    second = c.post("/api/ask", json={"question": OUT_OF_LIBRARY}).json()
    assert first["origin"] == "web" and second["mode"] == "none"
    # library questions are unaffected by the web limit
    assert c.post("/api/ask", json={"question": "How much does PM-KISAN pay each year?"}).json()["origin"] == "library"
    assert c.get("/api/health").json()["web_search"] is True
