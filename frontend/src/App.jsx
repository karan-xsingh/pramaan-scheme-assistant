import { useEffect, useState } from "react";
import { api } from "./api";
import { T } from "./i18n";
import { LANGS, hasUiText, langOf } from "./langs";
import SkinPicker from "./components/SkinPicker";
import ErrorBox from "./components/ErrorBox";
import Ask from "./views/Ask";
import Compare from "./views/Compare";
import Eligibility from "./views/Eligibility";
import Evaluation from "./views/Evaluation";

// Browser storage can be blocked, so every access is guarded.
const load = (key, fallback) => {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
};
const save = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch {}
};

export default function App() {
  const [lang, setLang] = useState(() => {
    const v = load("pramaan-lang", "en");
    return LANGS.some((l) => l.code === v) ? v : "en";
  });
  const [theme, setTheme] = useState(() => load("pramaan-theme", "auto"));
  const [tab, setTab] = useState("ask");
  const [schemes, setSchemes] = useState([]);
  const [health, setHealth] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const t = hasUiText(lang) ? T[lang] : T.en;

  useEffect(() => {
    document.documentElement.lang = lang;
    // Regional scripts need their own line height; the CSS keys off this.
    save("pramaan-lang", lang);
  }, [lang]);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    save("pramaan-theme", theme);
  }, [theme]);

  useEffect(() => {
    Promise.all([api.schemes(), api.health()])
      .then(([s, h]) => {
        setSchemes(s);
        setHealth(h);
      })
      .catch(setLoadError);
  }, []);

  return (
    <div className="shell">
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 40 40" width="34" height="34">
              <circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="2.5" strokeDasharray="2 3.2" />
              <circle cx="20" cy="20" r="12.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
              <path d="M13.5 20.5l4.8 4.8 8.4-10" fill="none" stroke="var(--ok)" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div>
            <span className="brand-name">{t.brand}</span>
            <span className="brand-alt" lang={lang === "en" ? "hi" : "en"}>
              {t.brandHindi}
            </span>
            <p className="tagline">{t.tagline}</p>
          </div>
        </div>

        <div className="controls">
          <label className="lang-pick">
            <span className="visually-hidden">{t.language}</span>
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M12 3a9 9 0 100 18 9 9 0 000-18zm0 0c2.4 2.4 3.6 5.4 3.6 9s-1.2 6.6-3.6 9m0-18C9.6 5.4 8.4 8.4 8.4 12s1.2 6.6 3.6 9M3.5 9h17M3.5 15h17" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <select value={lang} onChange={(e) => setLang(e.target.value)} lang={langOf(lang).code}>
              {LANGS.map((l) => (
                <option key={l.code} value={l.code} lang={l.code}>
                  {l.native}
                </option>
              ))}
            </select>
          </label>
          <SkinPicker value={theme} onChange={setTheme} t={t} />
        </div>
      </header>

      <nav className="tabs" role="tablist" aria-label="Sections">
        {Object.keys(t.tabs).map((k) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            className={tab === k ? "on" : ""}
            onClick={() => setTab(k)}
          >
            {t.tabs[k]}
          </button>
        ))}
      </nav>

      <div className="banner">
        <p>{t.notice}</p>
        {health && !health.llm_enabled && <p className="muted small">{t.noLlm}</p>}
      </div>
      <ErrorBox error={loadError} t={t} />

      <main>
        {tab === "ask" && <Ask t={t} lang={lang} schemes={schemes} health={health} />}
        {tab === "compare" && <Compare t={t} schemes={schemes} />}
        {tab === "eligibility" && <Eligibility t={t} schemes={schemes} />}
        {tab === "evaluation" && <Evaluation t={t} />}
      </main>

      <footer className="foot">{t.footer}</footer>
    </div>
  );
}
