import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DOCS_DIR = BASE_DIR / "data" / "docs"
INDEX_DIR = BASE_DIR / "data" / "index"

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

RETRIEVER = os.getenv("RETRIEVER", "tfidf").lower()
EMBED_MODEL = os.getenv(
    "EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

TOP_K = int(os.getenv("TOP_K", "4"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.08"))
# Share of the question's content words the best passage must contain (tfidf only)
MIN_COVERAGE = float(os.getenv("MIN_COVERAGE", "0.6"))

CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "120"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "25"))

# Web fallback: xAI (Grok) finds official pages, this app downloads and checks them itself.
XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4.7")  # check the model name in your xAI console
WEB_SEARCH = os.getenv("WEB_SEARCH", "1").lower() in {"1", "true", "yes"}
WEB_ALLOWED_DOMAINS = [
    d.strip().lower().lstrip(".")
    for d in os.getenv("WEB_ALLOWED_DOMAINS", "myscheme.gov.in,india.gov.in,gov.in,nic.in").split(",")
    if d.strip()
]
WEB_MAX_PAGES = int(os.getenv("WEB_MAX_PAGES", "3"))
WEB_MAX_BYTES = int(os.getenv("WEB_MAX_BYTES", "3000000"))
WEB_CACHE_TTL = int(os.getenv("WEB_CACHE_TTL", "3600"))
WEB_RATE_LIMIT_PER_MIN = int(os.getenv("WEB_RATE_LIMIT_PER_MIN", "6"))  # 0 = no limit

RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))  # 0 disables
TRUST_PROXY = os.getenv("TRUST_PROXY", "").lower() in {"1", "true", "yes"}

FEEDBACK_FILE = BASE_DIR / "data" / "feedback.jsonl"
EVAL_RESULTS = BASE_DIR / "eval" / "results.json"

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
