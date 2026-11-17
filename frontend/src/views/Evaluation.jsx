import { useEffect, useState } from "react";
import { api } from "../api";

const ORDER = [
  "retrieval_hit_rate",
  "correct_refusal_rate",
  "false_refusal_rate",
  "scheme_precision",
  "conflict_flagged",
  "answer_fact_match",
  "faithfulness",
];
const LOWER_IS_BETTER = new Set(["false_refusal_rate"]);

export default function Evaluation({ t }) {
  const [res, setRes] = useState(null);
  const [missing, setMissing] = useState(false);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    api
      .evaluation()
      .then(setRes)
      .catch(() => setMissing(true));
  }, []);

  if (missing) {
    return (
      <section className="page">
        <h1>{t.evalTitle}</h1>
        <p className="lede">{t.evalEmpty}</p>
        <p className="muted">{t.evalEmptyHint}</p>
        <pre className="code">python -m eval.evaluate</pre>
      </section>
    );
  }
  if (!res) return <section className="page"><h1>{t.evalTitle}</h1></section>;

  const m = res.metrics;
  const rows = res.rows.filter((r) => filter === "all" || !r.ok);

  return (
    <section className="page">
      <h1>{t.evalTitle}</h1>
      <p className="lede">{t.evalIntro}</p>
      <p className="muted small">{t.evalMeta(res)}</p>

      <table className="metrics">
        <tbody>
          {ORDER.filter((k) => m[k] !== null && m[k] !== undefined).map((k) => {
            const [label, hint] = t.evalMetrics[k];
            const good = LOWER_IS_BETTER.has(k) ? 100 - m[k] : m[k];
            return (
              <tr key={k}>
                <th scope="row">
                  {label}
                  <span className="muted small">{hint}</span>
                </th>
                <td className="metric-value">{m[k]}%</td>
                <td className="metric-bar" aria-hidden="true">
                  <span style={{ width: `${Math.max(2, good)}%` }} />
                </td>
              </tr>
            );
          })}
          <tr>
            <th scope="row">{t.latency}</th>
            <td className="metric-value">{m.latency_median_ms} ms</td>
            <td />
          </tr>
        </tbody>
      </table>

      <div className="eval-head">
        <h2>{t.perQuestion}</h2>
        <div className="seg" role="group">
          <button type="button" className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>
            {t.all}
          </button>
          <button type="button" className={filter === "failed" ? "on" : ""} onClick={() => setFilter("failed")}>
            {t.failed}
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table className="rows">
          <thead>
            <tr>
              <th scope="col">{t.colQuestion}</th>
              <th scope="col">{t.colKind}</th>
              <th scope="col">{t.colResult}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r.q}</td>
                <td className="muted">{r.kind}</td>
                <td className={r.ok ? "pass" : "fail"}>{r.ok ? t.pass : t.fail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
