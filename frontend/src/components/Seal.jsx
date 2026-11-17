import { useState } from "react";

const TONE = { high: "ok", medium: "warn", low: "bad", quote: "quote", unchecked: "muted", none: "muted" };
const ICON = { high: "✓", medium: "!", low: "✕", quote: "“", unchecked: "?", none: "–" };

/** Rubber-stamp style verdict for one answer, with an expandable per-sentence check. */
export default function Seal({ verification, answer, origin, t }) {
  const [open, setOpen] = useState(false);
  if (!verification) return null;
  const level = verification.level;
  const tone = TONE[level] || "muted";
  const count =
    level === "unchecked" || level === "none"
      ? ICON[level]
      : level === "quote"
        ? verification.total
        : `${verification.supported}/${verification.total}`;
  const claims = (verification.claims || []).filter((c) => c.status !== "unchecked");
  // A web page is not a vetted document, so the seal must not say "Verified" for it.
  const web = origin === "web" && t.sealWeb[level];
  const label = web ? t.sealWeb[level] : t.seal[level];
  const detail = t.sealDetail(level, verification) + (web ? ` ${t.sealWebNote}` : "");

  return (
    <div className={`verdict ${tone}`}>
      <div className="verdict-row">
        <div className="seal" aria-hidden="true">
          <span className="seal-count">{count}</span>
          <span className="seal-icon">{ICON[level]}</span>
        </div>
        <div className="verdict-text">
          <strong>{label}</strong>
          <span>{detail}</span>
        </div>
      </div>

      {claims.length > 0 && (
        <div className="how">
          <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
            {t.howChecked}
          </button>
          {open && (
            <div className="how-body">
              <p className="muted">{t.howCheckedText}</p>
              <ol className="claims">
                {claims.map((c, i) => (
                  <li key={i} className={`claim-row ${c.status}`}>
                    <span className="claim-status">{t.claim[c.status]}</span>
                    <span className="claim-text">{answer.slice(c.start, c.end).replace(/\s*\[\d+\]/g, "")}</span>
                    <span className="claim-reason">
                      {c.sources?.length ? `${t.cited}: ${c.sources.join(", ")}. ` : ""}
                      {c.reason}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
