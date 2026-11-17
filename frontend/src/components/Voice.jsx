import { useEffect, useRef } from "react";
import { langOf } from "../langs";

export function MicIcon({ size = 28 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <rect x="9" y="2.5" width="6" height="11.5" rx="3" fill="currentColor" />
      <path d="M5.5 11.5a6.5 6.5 0 0013 0M12 18v3.5M8.5 21.5h7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

/** The large microphone on the welcome screen. */
export function Orb({ onClick, label, lang }) {
  return (
    <button type="button" className="orb" onClick={onClick} aria-label={label}>
      <span className="orb-ring r1" aria-hidden="true" />
      <span className="orb-ring r2" aria-hidden="true" />
      <span className="orb-core">
        <MicIcon size={44} />
      </span>
      <span className="orb-lang" lang={lang.code}>
        {lang.native}
      </span>
    </button>
  );
}

/** Bottom sheet that shows what is being heard while the person speaks. */
export default function VoiceSheet({ open, lang, listening, text, error, autoSend, onAutoSend, onStop, onCancel, onRetry, t }) {
  const L = langOf(lang);
  const primary = useRef(null);
  const v = t.voice;

  useEffect(() => {
    if (!open) return undefined;
    primary.current?.focus();
    const esc = (e) => e.key === "Escape" && onCancel();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div className="sheet-backdrop" onClick={onCancel}>
      <div
        className={`sheet ${listening ? "live" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={v.listening}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sheet-head">
          <span className="sheet-lang" lang={L.code}>
            {L.native}
          </span>
          <span className="sheet-state" lang={L.code}>
            {error ? "" : listening ? L.listening : ""}
          </span>
        </div>

        <div className="sheet-orb" aria-hidden="true">
          <span className="wave w1" />
          <span className="wave w2" />
          <span className="wave w3" />
          <span className="orb-core">
            <MicIcon size={40} />
          </span>
        </div>
        <div className="eq" aria-hidden="true">
          {Array.from({ length: 9 }, (_, i) => (
            <i key={i} style={{ animationDelay: `${(i % 5) * 90}ms` }} />
          ))}
        </div>

        <p className="transcript" lang={L.code} aria-live="polite">
          {error ? <span className="sheet-error">{v[error] || v.failed}</span> : text || <span className="muted">{v.speakNow}</span>}
        </p>

        <div className="sheet-actions">
          {error ? (
            <button type="button" className="primary" ref={primary} onClick={onRetry}>
              {v.tap}
            </button>
          ) : (
            <button type="button" className="primary" ref={primary} onClick={onStop} disabled={!listening}>
              {v.stop}
            </button>
          )}
          <button type="button" className="ghost" onClick={onCancel}>
            {v.cancel}
          </button>
        </div>

        <label className="auto-send">
          <input type="checkbox" checked={autoSend} onChange={(e) => onAutoSend(e.target.checked)} />
          <span>{v.autoSend}</span>
        </label>
        <p className="muted small privacy">{v.privacy}</p>
      </div>
    </div>
  );
}
