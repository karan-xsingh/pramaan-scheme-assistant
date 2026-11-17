"""Evaluation harness.   Run from backend/:   python -m eval.evaluate [--no-llm] [--sleep 2]

Metrics
  retrieval hit rate     answerable questions where the retrieved passages contain every expected fact
  scheme precision       retrieved passages that come from the expected scheme
  false refusal rate     answerable questions where the system said "not found"
  answer fact match      (LLM mode) the written answer contains every expected fact
  faithfulness           (LLM mode) share of checked statements the verifier found supported
  correct refusal rate   unanswerable questions where the system said "not found" or an LLM refusal
  conflict flagged       conflicting-source questions that raised a warning
  latency                median and p95 per question

Writes eval/results.json (read by the web UI) and eval/report.md.
Exit code 1 if --min-hit / --min-refusal are given and not met (used in CI).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app import config, llm, rag
from app.retriever import get_retriever

HERE = Path(__file__).parent
REFUSAL = re.compile(
    r"(could not|couldn.t|cannot|can.t|unable to) find|not (?:available|mentioned|specified|covered)"
    r"|नहीं मिली|नहीं मिला|उपलब्ध नहीं",
    re.I,
)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace(",", "").replace("₹", "")).strip()


def has_all(text: str, facts: list[str]) -> bool:
    t = norm(text)
    return all(norm(f) in t for f in facts)


def pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


def run(use_llm: bool, sleep: float) -> dict:
    if not use_llm:
        config.LLM_API_KEY = ""
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    retriever = get_retriever()
    llm_on = llm.available()

    rows, latencies = [], []
    n_ans = hit = prec_num = prec_den = false_ref = 0
    ans_ok = n_llm = 0
    faith_sup = faith_tot = 0
    n_un = refused = 0
    n_conf = conf_ok = 0
    llm_fallbacks = 0

    for item in questions:
        if llm_on and sleep:
            time.sleep(sleep)  # stay under free-tier rate limits
        t0 = time.perf_counter()
        a = rag.answer_question(retriever, item["q"])
        ms = round((time.perf_counter() - t0) * 1000)
        latencies.append(ms)
        joined = " ".join(s["excerpt"] for s in a.sources)
        row = {"q": item["q"], "kind": item["kind"], "mode": a.mode, "latency_ms": ms}

        if item["kind"] == "unanswerable":
            n_un += 1
            said_no = a.mode == "none" or (a.mode == "llm" and bool(REFUSAL.search(a.answer)))
            refused += said_no
            row["ok"] = said_no
            row["outcome"] = "refused" if said_no else "answered"
        else:
            n_ans += 1
            found = has_all(joined, item["expect"])
            hit += found
            if a.mode == "none":
                false_ref += 1
            if a.sources:
                prec_den += len(a.sources)
                prec_num += sum(s["scheme"] == item["scheme"] for s in a.sources)
            row["retrieved"] = found
            row["ok"] = found
            if llm_on and a.mode == "llm":
                n_llm += 1
                fact = has_all(a.answer, item["expect"])
                ans_ok += fact
                row["answer_fact"] = fact
                v = a.verification or {}
                faith_sup += v.get("supported", 0)
                faith_tot += v.get("total", 0)
                row["faithfulness"] = f'{v.get("supported", 0)}/{v.get("total", 0)}'
                row["ok"] = found and fact
            elif llm_on and a.mode == "extractive":
                llm_fallbacks += 1
            if item["kind"] == "conflict":
                n_conf += 1
                flagged = any("conflict" in w.lower() for w in a.warnings)
                conf_ok += flagged
                row["conflict_flagged"] = flagged
        rows.append(row)

    ls = sorted(latencies)
    metrics = {
        "retrieval_hit_rate": pct(hit, n_ans),
        "scheme_precision": pct(prec_num, prec_den),
        "false_refusal_rate": pct(false_ref, n_ans),
        "correct_refusal_rate": pct(refused, n_un),
        "conflict_flagged": pct(conf_ok, n_conf),
        "answer_fact_match": pct(ans_ok, n_llm) if llm_on else None,
        "faithfulness": pct(faith_sup, faith_tot) if llm_on else None,
        "llm_fallbacks": llm_fallbacks if llm_on else None,
        "latency_median_ms": int(statistics.median(ls)) if ls else None,
        "latency_p95_ms": ls[min(len(ls) - 1, int(0.95 * len(ls)))] if ls else None,
    }
    counts = {"answerable": n_ans, "unanswerable": n_un, "conflict": n_conf}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "retriever": config.RETRIEVER,
        "generator": config.LLM_MODEL if llm_on else "extractive (no LLM)",
        "questions": len(questions),
        "counts": counts,
        "metrics": metrics,
        "rows": rows,
    }


def write_report(res: dict) -> str:
    m = res["metrics"]
    f = lambda v, u="%": "n/a" if v is None else f"{v}{u}"
    lines = [
        "# Evaluation report",
        "",
        f"Retriever `{res['retriever']}` | Generator {res['generator']} | {res['questions']} questions "
        f"({res['counts']['answerable']} answerable, {res['counts']['unanswerable']} unanswerable) | {res['generated_at']}",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Retrieval hit rate | {f(m['retrieval_hit_rate'])} |",
        f"| Scheme precision of retrieved passages | {f(m['scheme_precision'])} |",
        f"| False refusals on answerable questions | {f(m['false_refusal_rate'])} |",
        f"| Correct refusals on unanswerable questions | {f(m['correct_refusal_rate'])} |",
        f"| Conflicting sources flagged | {f(m['conflict_flagged'])} |",
        f"| Answer contains expected fact (LLM) | {f(m['answer_fact_match'])} |",
        f"| Faithfulness: statements supported by cited source (LLM) | {f(m['faithfulness'])} |",
        f"| Latency median / p95 | {f(m['latency_median_ms'], ' ms')} / {f(m['latency_p95_ms'], ' ms')} |",
        "",
        "## Per question",
        "",
        "| Question | Kind | Result | Mode | ms |",
        "|---|---|---|---|---|",
    ]
    for r in res["rows"]:
        lines.append(f"| {r['q']} | {r['kind']} | {'pass' if r['ok'] else 'FAIL'} | {r['mode']} | {r['latency_ms']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="evaluate retrieval only (no API calls)")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between LLM calls")
    ap.add_argument("--min-hit", type=float, help="fail if retrieval hit rate (%) is lower")
    ap.add_argument("--min-refusal", type=float, help="fail if correct refusal rate (%) is lower")
    args = ap.parse_args()

    res = run(use_llm=not args.no_llm, sleep=args.sleep)
    (HERE / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    report = write_report(res)
    (HERE / "report.md").write_text(report, encoding="utf-8")
    print("\n".join(report.splitlines()[:14]))
    fails = [r["q"] for r in res["rows"] if not r["ok"]]
    if fails:
        print("\nFailing questions:")
        for q in fails:
            print(" -", q)

    m = res["metrics"]
    bad = False
    if args.min_hit is not None and (m["retrieval_hit_rate"] or 0) < args.min_hit:
        print(f"\nretrieval hit rate {m['retrieval_hit_rate']}% < {args.min_hit}%")
        bad = True
    if args.min_refusal is not None and (m["correct_refusal_rate"] or 0) < args.min_refusal:
        print(f"\ncorrect refusal rate {m['correct_refusal_rate']}% < {args.min_refusal}%")
        bad = True
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
