import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import AnswerBody from "../components/AnswerBody";
import ErrorBox from "../components/ErrorBox";
import Evidence from "../components/Evidence";
import Seal from "../components/Seal";
import VoiceSheet, { MicIcon, Orb } from "../components/Voice";
import { LANGS, langOf } from "../langs";
import { canListen, useListen, useSpeak } from "../voice";

const pref = (k, d) => {
  try {
    const v = localStorage.getItem(k);
    return v === null ? d : v === "1";
  } catch {
    return d;
  }
};

function Feedback({ turn, t, reader }) {
  const [sent, setSent] = useState(null);
  const [copied, setCopied] = useState(false);
  const a = turn.a;

  async function send(rating) {
    setSent(rating);
    try {
      await api.feedback({
        question: turn.q,
        answer: a.answer.slice(0, 4000),
        rating,
        mode: a.mode,
        level: a.verification?.level || null,
      });
    } catch {
      /* feedback is best effort */
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(a.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  }

  return (
    <div className="actions">
      {reader.available && (
        <button type="button" className="link-btn" onClick={() => reader.toggle(turn)}>
          {reader.playing === turn.id ? t.voice.stopListen : t.voice.listen}
        </button>
      )}
      <button type="button" className="link-btn" onClick={copy}>
        {copied ? t.copied : t.copy}
      </button>
      {sent ? (
        <span className="muted">{t.thanks}</span>
      ) : (
        <>
          <button type="button" className="link-btn" onClick={() => send("up")}>
            {t.helpful}
          </button>
          <button type="button" className="link-btn" onClick={() => send("down")}>
            {t.notHelpful}
          </button>
        </>
      )}
    </div>
  );
}

function Welcome({ t, lang, schemes, health, onAsk, onPick, onVoice }) {
  const voiceOn = canListen;
  return (
    <section className="welcome">
      <div className="hero">
        {voiceOn && <Orb onClick={onVoice} label={t.voice.mic} lang={langOf(lang)} />}
        <div className="hero-copy">
          <h1>{voiceOn ? t.voice.heroTitle : t.askTitle}</h1>
          <p className="lede">{voiceOn ? t.voice.heroSub : t.askSub}</p>
          {voiceOn && <p className="tap-hint">{t.voice.tap}</p>}
        </div>
      </div>
      {!voiceOn && <p className="muted small">{t.voice.unsupported}</p>}
      <ul className="examples">
        {t.examples.map((ex) => (
          <li key={ex}>
            <button type="button" onClick={() => onAsk(ex)}>
              {ex}
            </button>
          </li>
        ))}
      </ul>
      {schemes.length > 0 && (
        <div className="browse">
          <p className="muted">{t.browse}</p>
          <div className="chips">
            {schemes.map((s) => (
              <button key={s.id} type="button" className="chip" onClick={() => onPick(s.id)}>
                {s.name}
              </button>
            ))}
          </div>
        </div>
      )}
      {health?.schemes > 0 && <p className="stats">{t.voice.stats(health.schemes, health.chunks, LANGS.length)}</p>}
    </section>
  );
}

export default function Ask({ t, lang, schemes, health }) {
  const [q, setQ] = useState("");
  const [scheme, setScheme] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [turns, setTurns] = useState([]);
  const [focus, setFocus] = useState({ id: null, n: null }); // which answer's evidence is open
  const endRef = useRef(null);
  const inputRef = useRef(null);

  // Voice: speak a question, and listen to answers.
  const L = langOf(lang);
  const [sheet, setSheet] = useState(false);
  const [autoSend, setAutoSend] = useState(() => pref("pramaan-autosend", true));
  const submitRef = useRef(null);
  const autoRef = useRef(autoSend);
  autoRef.current = autoSend;
  const mic = useListen({
    bcp: L.bcp,
    onDone: (text) => {
      setSheet(false);
      if (autoRef.current) submitRef.current?.(text);
      else {
        setQ(text);
        inputRef.current?.focus();
      }
    },
  });
  const speaker = useSpeak(L.bcp);
  const [playing, setPlaying] = useState(null);
  const reader = {
    available: speaker.available,
    playing: speaker.speaking ? playing : null,
    toggle: (turn) => {
      if (speaker.speaking && playing === turn.id) return speaker.cancel();
      setPlaying(turn.id);
      speaker.speak(turn.a.answer);
    },
  };
  const openVoice = () => {
    setSheet(true);
    mic.start();
  };
  const closeVoice = () => {
    mic.cancel();
    setSheet(false);
  };
  const changeAuto = (v) => {
    setAutoSend(v);
    try {
      localStorage.setItem("pramaan-autosend", v ? "1" : "0");
    } catch {}
  };

  const last = turns[turns.length - 1];
  const shown = turns.find((x) => x.id === focus.id) || last;
  const nameOf = (id) => schemes.find((s) => s.id === id)?.name;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, busy]);

  async function submit(question) {
    const text = (question ?? q).trim();
    if (!text || busy) return;
    const history = turns.slice(-3).map((x) => x.q);
    setBusy(true);
    setError(null);
    setQ("");
    try {
      const a = await api.ask(text, lang, scheme, history);
      const id = Date.now();
      setTurns((prev) => [...prev, { id, q: text, a }]);
      setFocus({ id, n: null });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  submitRef.current = submit;
  const cite = (id, n) => setFocus((f) => (f.id === id && f.n === n ? { id, n: null } : { id, n }));

  return (
    <div className={`workspace ${turns.length > 1 ? "multi" : ""}`}>
      <div className="conversation">
        {turns.length === 0 && !busy && (
          <Welcome
            t={t}
            lang={lang}
            health={health}
            onVoice={openVoice}
            schemes={schemes}
            onAsk={submit}
            onPick={(id) => {
              setScheme(id);
              inputRef.current?.focus();
            }}
          />
        )}

        {turns.map((turn, idx) => {
          const a = turn.a;
          const isLast = idx === turns.length - 1;
          const isShown = shown?.id === turn.id;
          const topName = nameOf(a.top_scheme);
          // The web banner already says this, so do not repeat it in the notes list.
          const notes = (a.warnings || []).filter((w) => !(a.origin === "web" && w.includes("not from the verified")));
          return (
            <article key={turn.id} className={`turn ${isShown ? "selected" : ""}`} onClick={() => setFocus({ id: turn.id, n: focus.id === turn.id ? focus.n : null })}>
              <h2 className="question">
                <span className="visually-hidden">{t.you}: </span>
                {turn.q}
              </h2>
              {a.standalone_question && a.standalone_question !== turn.q && (
                <p className="muted small">
                  {t.askedAs}: {a.standalone_question}
                </p>
              )}

              {a.origin === "web" && (
                <p className="origin">
                  <strong>{t.webTag}.</strong> {t.webNote}
                </p>
              )}

              <AnswerBody
                text={a.answer}
                claims={a.translated_to ? [] : a.verification?.claims}
                activeN={focus.id === turn.id ? focus.n : null}
                onCite={(n) => cite(turn.id, n)}
              />

              <Seal verification={a.verification} answer={a.answer_en || a.answer} origin={a.origin} t={t} />

              {a.translated_to && (
                <div className="note translated">
                  <p>{t.voice.translated}</p>
                  <details>
                    <summary>{t.voice.original}</summary>
                    <AnswerBody
                      text={a.answer_en}
                      claims={a.verification?.claims}
                      activeN={focus.id === turn.id ? focus.n : null}
                      onCite={(n) => cite(turn.id, n)}
                    />
                  </details>
                  <p className="muted small">{t.voice.regionalNote}</p>
                </div>
              )}

              {notes.length > 0 && (
                <div className="note warn">
                  <strong>{t.warnings}</strong>
                  <ul>
                    {notes.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {a.sources.length > 0 && (
                <details
                  className="inline-evidence"
                  open={isShown && (focus.n !== null || a.sources.length === 0)}
                  onClick={(e) => e.stopPropagation()}
                >
                  <summary
                    onClick={(e) => {
                      e.preventDefault();
                      setFocus(
                        focus.id === turn.id && focus.n !== null
                          ? { id: turn.id, n: null }
                          : { id: turn.id, n: a.sources[0].n },
                      );
                    }}
                  >
                    {t.evidenceCount(a.sources.length)}
                  </summary>
                  <Evidence
                    sources={a.sources}
                    claims={a.verification?.claims}
                    activeN={focus.id === turn.id ? focus.n : null}
                    t={t}
                  />
                </details>
              )}

              <Feedback turn={turn} t={t} reader={reader} />

              {isLast && topName && !busy && (
                <div className="followups">
                  {t.followUps(topName).map((f) => (
                    <button key={f} type="button" className="chip" onClick={(e) => { e.stopPropagation(); submit(f); }}>
                      {f}
                    </button>
                  ))}
                </div>
              )}
            </article>
          );
        })}

        {busy && (
          <div className="turn pending" aria-live="polite">
            <p className="searching">
              {t.searching}
              <span className="dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </p>
            <div className="skeleton" />
            <div className="skeleton short" />
          </div>
        )}

        <ErrorBox error={error} t={t} />
        <div ref={endRef} />

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <select value={scheme} onChange={(e) => setScheme(e.target.value)} aria-label={t.scheme}>
            <option value="">{t.allSchemes}</option>
            {schemes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t.placeholder}
            aria-label={t.placeholder}
            maxLength={1000}
            autoComplete="off"
          />
          {canListen && (
            <button type="button" className="mic-btn" onClick={openVoice} aria-label={t.voice.mic} title={t.voice.mic}>
              <MicIcon size={22} />
            </button>
          )}
          <button type="submit" className="primary" disabled={busy || !q.trim()}>
            {t.send}
          </button>
        </form>
      </div>

      <VoiceSheet
        open={sheet}
        lang={lang}
        listening={mic.listening}
        text={mic.text}
        error={mic.error}
        autoSend={autoSend}
        onAutoSend={changeAuto}
        onStop={mic.stop}
        onCancel={closeVoice}
        onRetry={mic.start}
        t={t}
      />

      <aside className="evidence-pane" aria-label={t.evidence}>
        <h2>{shown?.a?.sources?.length ? t.evidenceCount(shown.a.sources.length) : t.evidence}</h2>
        {shown?.a?.sources?.length ? (
          <Evidence
            sources={shown.a.sources}
            claims={shown.a.verification?.claims}
            activeN={focus.id === shown.id ? focus.n : null}
            t={t}
          />
        ) : (
          <p className="muted">{t.evidenceEmpty}</p>
        )}
      </aside>
    </div>
  );
}
