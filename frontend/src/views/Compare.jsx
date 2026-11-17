import { useState } from "react";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";

export default function Compare({ t, schemes }) {
  const [picked, setPicked] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const nameOf = (id) => schemes.find((s) => s.id === id)?.name || id;

  const toggle = (id) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 3 ? [...p, id] : p));

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.compare(picked));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <h1>{t.tabs.compare}</h1>
      <p className="lede">{t.comparePick}</p>
      <div className="chips picker">
        {schemes.map((s) => (
          <label key={s.id} className={`chip pick ${picked.includes(s.id) ? "on" : ""}`}>
            <input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s.id)} />
            {s.name}
          </label>
        ))}
      </div>
      <button type="button" className="primary" onClick={run} disabled={picked.length < 2 || busy}>
        {t.compareBtn}
      </button>
      <ErrorBox error={error} t={t} />

      {result && (
        <div className="table-wrap">
          <table className="compare">
            <thead>
              <tr>
                <td />
                {result.schemes.map((s) => (
                  <th key={s.scheme} scope="col">
                    {nameOf(s.scheme)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.aspects.map((a) => (
                <tr key={a}>
                  <th scope="row">{t.aspects[a]}</th>
                  {result.schemes.map((s) => {
                    const cell = s.aspects[a];
                    return (
                      <td key={s.scheme}>
                        {cell ? (
                          <>
                            <p>{cell.text}</p>
                            {cell.url ? (
                              <a href={cell.url} target="_blank" rel="noreferrer noopener" className="slip-link">
                                {cell.title}
                              </a>
                            ) : (
                              <span className="muted small">{cell.title}</span>
                            )}
                          </>
                        ) : (
                          <span className="muted">{t.notFound}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
