/** Answer text with [n] markers turned into buttons and weak sentences marked. */
function withCites(text, onCite, activeN, keyBase) {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return part;
    const n = Number(m[1]);
    return (
      <button
        key={`${keyBase}-${i}`}
        type="button"
        className={`cite ${activeN === n ? "on" : ""}`}
        onClick={() => onCite(n)}
        aria-label={`Source ${n}`}
      >
        {n}
      </button>
    );
  });
}

export default function AnswerBody({ text, claims = [], onCite, activeN }) {
  const parts = [];
  let pos = 0;
  [...claims]
    .sort((a, b) => a.start - b.start)
    .forEach((c, i) => {
      if (c.start > pos) parts.push(<span key={`g${i}`}>{text.slice(pos, c.start)}</span>);
      const seg = text.slice(c.start, c.end);
      const flagged = c.status === "unsupported" || c.status === "weak";
      parts.push(
        <span key={`c${i}`} className={flagged ? `flag ${c.status}` : undefined} title={flagged ? c.reason : undefined}>
          {withCites(seg, onCite, activeN, `c${i}`)}
        </span>,
      );
      pos = c.end;
    });
  if (pos < text.length) parts.push(<span key="tail">{withCites(text.slice(pos), onCite, activeN, "tail")}</span>);
  if (!claims.length) return <p className="answer-text">{withCites(text, onCite, activeN, "all")}</p>;
  return <p className="answer-text">{parts}</p>;
}
