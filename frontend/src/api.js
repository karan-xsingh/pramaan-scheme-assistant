// In dev, Vite proxies /api to the FastAPI server. In production set VITE_API_URL
// (e.g. https://your-backend.onrender.com) at build time.
const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    const err = new Error(typeof detail === "string" ? detail : "Request failed");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request("/api/health"),
  schemes: () => request("/api/schemes"),
  ask: (question, lang, scheme, history = []) =>
    post("/api/ask", { question, lang, scheme: scheme || null, history }),
  compare: (schemes) => post("/api/compare", { schemes }),
  eligibility: (scheme, profile) => post("/api/eligibility", { scheme, profile }),
  feedback: (payload) => post("/api/feedback", payload),
  evaluation: () => request("/api/evaluation"),
};
