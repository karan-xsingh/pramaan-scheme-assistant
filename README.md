# Pramaan (प्रमाण): Evidence-Grounded Generative AI for Government Schemes

Minor Project-I · Doon School of Advanced Computing
*Evidence-Grounded Generative AI System for Government Schemes and Public Services*

Pramaan answers questions about Indian government schemes **only from retrieved official documents**. Every answer shows the passages it came from, and a verifier checks each sentence of the answer against the source it cites. When the documents do not contain the answer, or the written answer cannot be matched to its sources, the system says so instead of guessing. *Pramaan* means "proof" or "evidence" in Hindi.

```
                       ┌──────────────────────── FastAPI ────────────────────────┐
 React UI ──/api/ask──▶│ contextualise ─▶ detect scheme ─▶ retrieve (TF-IDF/FAISS)│
 (EN / हिं)            │      │                                  │               │
                       │      ▼                           evidence gate           │
                       │  LLM rewrite                     (refuse if no match)    │
                       │                                         │               │
 ◀── answer + seal ────│  verifier ◀── LLM answer with [n] ◀─────┘               │
     + evidence        │     │  reject if >=50% unsupported ─▶ show source passages│
                       └─────┴───────────────────────────────────────────────────┘
```

## What it does

| Feature | How it works | Code |
|---|---|---|
| Grounded answers with citations | Retrieval first; the LLM may use only the numbered passages and must cite `[n]` | `rag.py` |
| **Answer verifier** | Per sentence: does the cited source exist, do all numbers appear in it, do most words appear in it. Flags invented numbers, fake citations and unrelated sentences | `verifier.py` |
| Verification seal | Each answer gets a stamp: *Verified / Partly verified / Not verified / Direct quotes*, with a per-sentence breakdown | `Seal.jsx` |
| Safe fallback | If at least half of the checked sentences are unsupported, the written answer is dropped and the source passages are shown | `rag.py` |
| Honest refusal | An evidence gate refuses questions the documents do not cover | `rag.py` |
| Conflict warning | If two documents of one scheme give different rupee amounts, the user is warned | `rag.py` |
| Scheme-aware retrieval | A scheme named in the question (by name or alias, English or Hindi) restricts the search to that scheme | `rag.py`, `schemes.json` |
| **Web fallback for any scheme** | When the verified library has nothing, Grok (xAI) finds official `.gov.in` pages; this app downloads them itself, then runs the same gate, LLM and verifier. Labelled "From official web pages" | `web_search.py` |
| Follow-up questions | Short follow-ups are rewritten into standalone questions using the last 3 questions | `rag.py` |
| English and Hindi | Hindi UI, Hindi documents, Hindi to English query rewrite, matched Latin/Devanagari typeface | `i18n.js` |
| Scheme comparison | Side-by-side benefit, eligibility, documents and how to apply, each with its source | `compare.py` |
| Eligibility checklist | Compares user details with published conditions. Never decides eligibility | `eligibility.py` |
| Evaluation harness and in-app dashboard | 40 questions, 8 metrics, results shown in the Evaluation tab | `eval/` |
| Feedback, rate limiting | Thumbs up/down to a JSONL file (no IP stored); per-IP limiter protects the API key | `main.py`, `ratelimit.py` |
| Tests and CI | 53 pytest tests; GitHub Actions runs tests, a retrieval-quality gate and the frontend build | `tests/`, `.github/` |

## Run it locally (Windows PowerShell)

**Window 1: backend**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --default-timeout=300 --retries 10 -r requirements.txt
Copy-Item .env.example .env          # then: notepad .env  and set LLM_API_KEY=...
python -m app.ingest
python -m uvicorn app.main:app --reload --port 8000
```

**Window 2: frontend**
```powershell
cd frontend
npm install
npm run dev                           # open http://localhost:5173
```

Without `LLM_API_KEY` the app still works: it shows the best source passages instead of a written answer.

**Tests and evaluation** (from `backend/`, venv active)
```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m eval.evaluate               # with LLM key: adds answer-quality and faithfulness metrics
python -m eval.evaluate --no-llm      # retrieval only, no API calls
```

**Docker** (not tested in the environment this was written in): `docker compose up --build`, then open http://localhost:8080. Needs `backend/.env`.

## Add more schemes for free (no API key)

`app/add_scheme.py` downloads official pages or PDFs, saves them in the library and registers the scheme's name and aliases, so questions that mention the scheme search only its documents.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.add_scheme --id pm-mudra --name "PM Mudra Yojana" `
    --url https://OFFICIAL-SITE/guidelines.pdf `
    --url https://OFFICIAL-SITE/faq `
    --alias mudra --alias "pm mudra"
python -m app.ingest
python -m uvicorn app.main:app --reload --port 8000
```

* Use the scheme's own official site: open it, find the "Guidelines", "Operational guidelines" or "FAQ" link, and copy that link. PDFs are best because citations keep their page numbers.
* Only `https` links on `WEB_ALLOWED_DOMAINS` are accepted. Add `--any-domain` for an official site outside those (check that it is genuine first).
* Pages that need JavaScript to show their text are skipped with a message; use the PDF instead.
* Open each saved file in `data/docs/` and check it contains the scheme's real text before relying on it.
* Eligibility rules are not written automatically, because a person must read the guidelines. Until you add `criteria` for the scheme in `data/schemes.json`, it appears in Ask and Compare but not in the Eligibility checklist.
* Then add 2 to 3 questions about the new scheme to `eval/questions.json`.

## Web fallback (optional, needs a paid xAI key): covering schemes outside the library

The library holds a limited set of schemes, so for everything else Pramaan can look on official websites.

```
question ─▶ library has evidence? ──yes──▶ normal answer (verified library)
                 │ no
                 ▼
     xAI web_search (allowed domains only) ─▶ list of page URLs
                 ▼
     this app downloads each page (https, allowed domain, size limit) ─▶ text ─▶ passages
                 ▼
     same evidence gate ─▶ same LLM prompt ─▶ same verifier ─▶ labelled "From official web pages"
```

* **Why Grok only finds URLs:** if the web-search model wrote the answer, nothing could check it. Here the answer is written from page text this app fetched itself, so the verifier can check every sentence.
* **Setup:** get an xAI API key (separate from the Groq key) and set `XAI_API_KEY` in `backend/.env`. Check the model name in your xAI console and set `XAI_MODEL` (the default `grok-4.7` comes from xAI's documentation example). Leave the key empty to switch the fallback off.
* **Your Groq key keeps writing the answers.** Groq's own built-in search models (`groq/compound`) are listed as retired on 21 September 2026, so they are not used.
* **Safety:** only `https` pages on `WEB_ALLOWED_DOMAINS` are fetched; every redirect is re-checked; addresses that resolve to private or local networks are refused; downloads are size-limited. The web path has its own stricter rate limit (`WEB_RATE_LIMIT_PER_MIN`, default 6) because each search costs money and takes seconds.
* **Honest labelling:** web answers carry a "From official web pages" note, and their seal says "Matches the web page" instead of "Verified", because a web page is not a vetted document.
* **Not available for web answers:** the eligibility checklist and scheme comparison, which use hand-written rules for library schemes.

**Tested with mocks only.** The 16 web tests (URL extraction, domain and redirect rules, HTML/PDF extraction, library-first logic, rate limit) use fake xAI replies. I could not call the real xAI API from the environment this was built in. When you first run it with your key, check three things: (1) that the model name works, (2) that pages are found for a scheme not in the library, (3) whether xAI's `allowed_domains` filter matches subdomains such as `pmkisan.gov.in` when you list `gov.in`. xAI accepts at most 5 domains and this app never downloads a page outside `WEB_ALLOWED_DOMAINS` either way.

## Evaluation

`python -m eval.evaluate` runs 40 questions (33 answerable in English and Hindi, 7 outside the documents) and writes `backend/eval/results.json` and `report.md`. The Evaluation tab in the app shows the same results.

Retrieval-only results from the version in this repo (extractive mode, no LLM):

| Metric | Result |
|---|---|
| Right passage retrieved (33 answerable) | 100% |
| Wrongly refused (answerable) | 0% |
| Retrieved passages from the right scheme | 100% |
| Conflicting sources flagged | 1 of 1 |
| Correctly refused (7 out of scope) | 43% (3 of 7) |

**Read the last row honestly.** The four failures name a real scheme and ask for something the documents do not contain (for example the PM-KISAN helpline number). A word-matching retriever cannot tell that apart from a real question. With an LLM key these are refused by the model, and `eval.evaluate` then also reports answer accuracy and faithfulness. **Run it with your key and put those numbers in your report.** The numbers above are measured on sample documents and on questions written by the author of the sample documents, so treat them as a regression test, not as a claim about real-world accuracy.

## Replace the sample documents before you present or publish

The files in `backend/data/docs/` are **short summaries written for the prototype**, each marked "SAMPLE DOCUMENT". They are not official text and may be out of date. (`pmuy_update_note.md` exists on purpose to demonstrate conflict detection.)

1. Download the official guideline or FAQ PDFs from the scheme portals (pmkisan.gov.in, pmjay.gov.in, pmayg.nic.in, pmuy.gov.in, and so on).
2. Put them in `backend/data/docs/` and describe each in `backend/data/docs/sources.json`:
   ```json
   {"PMKISAN_Guidelines.pdf": {"scheme": "pm-kisan", "title": "PM-KISAN Operational Guidelines", "url": "https://pmkisan.gov.in", "lang": "en"}}
   ```
3. Delete the sample `.md` files and run `python -m app.ingest` again.
4. Check `backend/data/schemes.json` (eligibility rules and name aliases) against the official text.
5. Rewrite `backend/eval/questions.json` with questions and expected facts from the real documents, ideally written by a teammate who has not read the answers.

## Deployment

* **Backend:** Render, Railway or any Python host (or the Dockerfile). Start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `LLM_API_KEY`, `CORS_ORIGINS=https://<your-frontend>` and `TRUST_PROXY=1`. Run `python -m app.ingest` in the build step.
* **Frontend:** Vercel. Root directory `frontend`, build `npm run build`, environment variable `VITE_API_URL=https://<your-backend>`.

## Design decisions

* **Verify, do not trust.** The model's `[1]` marker proves nothing by itself, so a separate check compares each sentence with its cited passage. The check is lexical, which makes it fast, deterministic and easy to test.
* **Fail safe.** Every failure path (no evidence, LLM error, unverifiable answer) ends in showing real source text, never an unsupported claim.
* **No decisions about people.** The prompt forbids eligibility verdicts, and the eligibility tool only reports "appears to match".
* **Privacy.** Feedback stores the question, answer and rating with a timestamp. No IP address, no user id.
* **Swap-in retrieval.** `RETRIEVER=dense` switches to Sentence-Transformers plus FAISS for meaning-based and cross-language search (install the two optional lines in `requirements.txt`).

## Known limitations

* The verifier catches invented numbers, fake citations and off-topic sentences. It cannot catch a sentence that reuses the source's words but reverses its meaning.
* TF-IDF matches words, not meaning, and does not work across languages. Hindi questions about English-only documents need the LLM query rewrite or the dense retriever.
* Eligibility rules are transcribed by hand and need re-checking when schemes change.
* The conflict check only compares rupee amounts.
* Web answers are only as good as the pages found: scanned PDFs, script-heavy pages and pages that are very long are read poorly or only in part (first 30 PDF pages).
* The rate limiter is in memory and per process.
* No accounts, no stored chat history, no automated browser tests.

## Resume bullets

Use these only after you have replaced the sample documents and run the evaluation with your API key. Fill the brackets with your own measured numbers.

* Built **Pramaan**, a bilingual (English/Hindi) retrieval-augmented assistant for Indian government schemes with FastAPI, React and a Groq-hosted LLaMA model, where every answer is tied to cited official-document passages.
* Designed a **grounding verifier** that checks each generated sentence against its cited source (numbers, citations, vocabulary overlap) and falls back to quoted source text when answers cannot be verified; [X]% of checked statements were supported in evaluation.
* Created an evaluation harness with [N] labelled questions measuring retrieval hit rate, false and correct refusals, conflict flagging, answer accuracy, faithfulness and latency, shown in an in-app dashboard and enforced in CI.
* Added a safe web fallback (domain allowlist, redirect and private-network checks, separate rate limit) that answers questions about schemes outside the library, with the same verifier and clear labelling.
* Added scheme-aware retrieval, follow-up question rewriting, per-IP rate limiting, 53 automated tests, Docker packaging and a GitHub Actions pipeline.

## Voice, languages and skins

**Speak instead of typing.** The microphone button (large on the welcome screen, small beside the text box) uses the browser's built-in speech recognition, so it needs no API key and no extra install. It works in Chrome, Edge and Samsung Internet; Firefox and some iPhones do not support it, and the app then shows the text box only. In Chrome the audio is sent to Google's speech service to be turned into text. Pramaan itself never records or stores audio, and the app says so on the listening screen.

**Languages.** English and Hindi have full screen text. Marathi, Bengali, Tamil, Telugu, Gujarati and Punjabi can be spoken and answered in. For these the question is translated to English, answered and checked against the documents in English, then the answer is translated back. The verification seal belongs to the English original, which is one tap away ("Verified English original"). This needs the LLM key; without it the answer is shown in English with a note. Translation quality of the regional answers has not been evaluated, so treat it as a demo feature and say so in your viva.

**Tell your whole situation.** A long spoken description (22 words or more) is first reduced by the LLM to a short search query, so a rambling story does not fail the evidence check. The answer is still checked against the documents only.

**Listen to answers.** A "Listen" button reads the answer aloud when the device has a voice for the selected language.

**Skins.** Appearance menu: match device, Daylight, Night, Tiranga, Midnight, Aurora (glass), High contrast. A skin is one block of colour tokens in `frontend/src/styles.css`; add your own by copying one.
