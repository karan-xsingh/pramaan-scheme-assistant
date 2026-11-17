import { useEffect, useRef } from "react";

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function Highlight({ text, terms }) {
  if (!terms?.length) return text;
  // Whole words only: letters or digits on either side mean it is part of a longer word.
  const re = new RegExp(`(?<![\\p{L}\\p{N}])(${terms.map(escapeRe).join("|")})(?![\\p{L}\\p{N}])`, "giu");
  return text.split(re).map((part, i) =>
    i % 2 === 1 ? (
      <mark key={i}>{part}</mark>
    ) : (
      part
    ),
  );
}

/** The documents behind one answer. activeN is the source picked via a [n] marker. */
export default function Evidence({ sources, claims = [], activeN, t }) {
  const refs = useRef({});
  const cited = new Set(claims.flatMap((c) => c.sources || []));

  useEffect(() => {
    if (activeN && refs.current[activeN]) {
      refs.current[activeN].scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [activeN]);

  return (
    <ol className="slips">
      {sources.map((s) => (
        <li
          key={s.n}
          ref={(el) => (refs.current[s.n] = el)}
          className={`slip ${activeN === s.n ? "active" : ""}`}
        >
          <header>
            <span className="slip-n">{s.n}</span>
            <div className="slip-title">
              <strong>{s.title}</strong>
              {s.page ? (
                <span className="muted">
                  {" "}
                  {t.page} {s.page}
                </span>
              ) : null}
            </div>
            {s.origin === "web" && <span className="slip-web">{t.webSource}</span>}
            {cited.has(s.n) && <span className="slip-cited">{t.cited}</span>}
          </header>
          <blockquote lang={s.lang}>
            <Highlight text={s.excerpt} terms={s.terms} />
          </blockquote>
          {s.url && (
            <a href={s.url} target="_blank" rel="noreferrer noopener" className="slip-link">
              {s.origin === "web" && s.domain ? s.domain : t.openSource}
            </a>
          )}
        </li>
      ))}
    </ol>
  );
}
