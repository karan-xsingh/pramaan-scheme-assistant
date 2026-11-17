import json

import httpx
import pymupdf
import pytest

from app import add_scheme, config, eligibility, ingest, web_search

PAGE_WORDS = " ".join(
    "The Mudra scheme gives collateral free loans to small business owners who want to start or grow a shop."
    for _ in range(4)
)
HTML = f"<html><head><title>PM Mudra Yojana FAQ</title></head><body><nav>menu</nav><p>{PAGE_WORDS}</p></body></html>"


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    schemes = tmp_path / "schemes.json"
    schemes.write_text(json.dumps({"existing": {"name": "Existing", "criteria": [{"id": "a"}], "aliases": ["old"]}}))
    monkeypatch.setattr(config, "DOCS_DIR", docs)
    monkeypatch.setattr(eligibility, "SCHEMES_FILE", schemes)
    monkeypatch.setattr(web_search, "_public", lambda host: True)
    return docs, schemes


def transport(body: bytes, ctype: str):
    return httpx.MockTransport(lambda r: httpx.Response(200, content=body, headers={"content-type": ctype}))


def test_html_page_is_saved_and_ingested(sandbox):
    docs, schemes = sandbox
    res = add_scheme.add_scheme(
        "PM Mudra", "PM Mudra Yojana", ["https://www.mudra.gov.in/faq"], aliases=["mudra"],
        transport=transport(HTML.encode(), "text/html"),
    )
    assert res["saved"] == ["pm-mudra_1.md"] and not res["skipped"]
    text = (docs / "pm-mudra_1.md").read_text(encoding="utf-8")
    assert text.startswith("---\nscheme: pm-mudra\ntitle: PM Mudra Yojana FAQ\nurl: https://www.mudra.gov.in/faq")
    assert "menu" not in text and "collateral free loans" in text

    chunks = ingest.build_chunks()
    assert chunks and {c.scheme for c in chunks} == {"pm-mudra"}

    data = json.loads(schemes.read_text())
    assert data["pm-mudra"]["criteria"] == []
    assert {"mudra", "pm mudra yojana", "pm-mudra"} <= set(data["pm-mudra"]["aliases"])
    assert data["existing"]["aliases"] == ["old"]  # other schemes untouched


def test_pdf_is_kept_as_pdf_with_page_numbers(sandbox):
    docs, _ = sandbox
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 700), PAGE_WORDS, fontsize=11)
    res = add_scheme.add_scheme(
        "mudra", "PM Mudra Yojana", ["https://www.example.gov.in/guidelines.pdf"],
        transport=transport(doc.tobytes(), "application/pdf"),
    )
    assert res["saved"] == ["mudra_1.pdf"]
    manifest = json.loads((docs / "sources.json").read_text())
    assert manifest["mudra_1.pdf"]["scheme"] == "mudra" and manifest["mudra_1.pdf"]["lang"] == "en"
    chunks = ingest.build_chunks()
    assert chunks and chunks[0].page == 1 and chunks[0].url.endswith("guidelines.pdf")


def test_other_domains_http_and_thin_pages_are_refused(sandbox):
    docs, schemes = sandbox
    ok = transport(HTML.encode(), "text/html")
    res = add_scheme.add_scheme(
        "x", "X Scheme",
        ["https://example.com/page", "http://www.mudra.gov.in/faq", "https://www.mudra.gov.in/empty"],
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"<p>too short</p>", headers={"content-type": "text/html"})
        ),
    )
    reasons = {u: why for u, why in res["skipped"]}
    assert "WEB_ALLOWED_DOMAINS" in reasons["https://example.com/page"]
    assert "https" in reasons["http://www.mudra.gov.in/faq"]
    assert "almost no readable text" in reasons["https://www.mudra.gov.in/empty"]
    assert res["saved"] == []
    assert "x" not in json.loads(schemes.read_text())  # nothing registered when nothing saved

    allowed = add_scheme.add_scheme("x", "X Scheme", ["https://example.com/page"], any_domain=True, transport=ok)
    assert allowed["saved"] == ["x_1.md"]


def test_private_addresses_are_refused(sandbox, monkeypatch):
    monkeypatch.setattr(web_search, "_public", lambda host: False)
    res = add_scheme.add_scheme(
        "x", "X", ["https://www.mudra.gov.in/faq"], transport=transport(HTML.encode(), "text/html")
    )
    assert res["saved"] == [] and "not a public website" in res["skipped"][0][1]


def test_scheme_without_rules_has_no_checklist(sandbox):
    add_scheme.add_scheme(
        "pm-mudra", "PM Mudra Yojana", ["https://www.mudra.gov.in/faq"], transport=transport(HTML.encode(), "text/html")
    )
    with pytest.raises(KeyError):
        eligibility.check("pm-mudra", {})


def test_missing_arguments_are_rejected(sandbox):
    with pytest.raises(ValueError):
        add_scheme.add_scheme("", "Name", ["https://www.mudra.gov.in/faq"])
    assert add_scheme.main(["--id", "x", "--name", "X", "--url", "http://insecure.gov.in/a"]) == 1
