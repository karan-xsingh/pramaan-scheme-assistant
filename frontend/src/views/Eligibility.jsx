import { useEffect, useState } from "react";
import { api } from "../api";
import ErrorBox from "../components/ErrorBox";

const TRI_FIELDS = [
  "owns_land",
  "pays_income_tax",
  "govt_employee",
  "has_pucca_house",
  "has_lpg",
  "bpl",
  "has_bank_account",
  "in_secc_list",
];

export default function Eligibility({ t, schemes }) {
  const checklist = schemes.filter((s) => s.has_checklist);
  const [scheme, setScheme] = useState("");
  const [form, setForm] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!scheme && checklist.length) setScheme(checklist[0].id);
  }, [checklist.length]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function run(e) {
    e.preventDefault();
    setError(null);
    const profile = {};
    if (form.age) profile.age = Number(form.age);
    if (form.gender) profile.gender = form.gender;
    if (form.area) profile.area = form.area;
    TRI_FIELDS.forEach((k) => {
      if (form[k] === "yes") profile[k] = true;
      if (form[k] === "no") profile[k] = false;
    });
    try {
      setResult(await api.eligibility(scheme, profile));
    } catch (err) {
      setError(err);
    }
  }

  const matched = result ? result.rows.filter((r) => r.status === "appears_to_match").length : 0;

  return (
    <section className="page">
      <h1>{t.tabs.eligibility}</h1>
      <p className="lede">{t.eligIntro}</p>
      <form onSubmit={run}>
        <div className="form-grid">
          <label>
            {t.scheme}
            <select
              value={scheme}
              onChange={(e) => {
                setScheme(e.target.value);
                setResult(null);
              }}
            >
              {checklist.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t.age}
            <input type="number" min="0" max="120" value={form.age || ""} onChange={(e) => set("age", e.target.value)} />
          </label>
          <label>
            {t.fields.gender}
            <select value={form.gender || ""} onChange={(e) => set("gender", e.target.value)}>
              <option value="">{t.unsure}</option>
              <option value="female">{t.female}</option>
              <option value="male">{t.male}</option>
              <option value="other">{t.other}</option>
            </select>
          </label>
          <label>
            {t.fields.area}
            <select value={form.area || ""} onChange={(e) => set("area", e.target.value)}>
              <option value="">{t.unsure}</option>
              <option value="rural">{t.rural}</option>
              <option value="urban">{t.urban}</option>
            </select>
          </label>
          {TRI_FIELDS.map((k) => (
            <label key={k}>
              {t.fields[k]}
              <select value={form[k] || ""} onChange={(e) => set(k, e.target.value)}>
                <option value="">{t.unsure}</option>
                <option value="yes">{t.yes}</option>
                <option value="no">{t.no}</option>
              </select>
            </label>
          ))}
        </div>
        <button type="submit" className="primary" disabled={!scheme}>
          {t.check}
        </button>
      </form>
      <ErrorBox error={error} t={t} />

      {result && (
        <div className="result">
          <h2>{result.name}</h2>
          <ul className="checklist">
            {result.rows.map((r) => (
              <li key={r.id} className={r.status}>
                <span className="status">{t.status[r.status]}</span>
                {r.criterion}
              </li>
            ))}
          </ul>
          <p>
            <strong>{t.matchCount(matched, result.rows.length)}</strong>
          </p>
          <div className="note warn">{result.disclaimer}</div>
        </div>
      )}
    </section>
  );
}
