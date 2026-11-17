import { useEffect, useRef, useState } from "react";

// Swatches show each skin's paper, surface and accent so the choice is visible before it is made.
export const SKINS = [
  { id: "auto", swatch: ["#f2f5fa", "#161d36", "#1c2a5a"] },
  { id: "light", swatch: ["#f2f5fa", "#ffffff", "#1c2a5a"] },
  { id: "dark", swatch: ["#0e1324", "#161d36", "#9db0ff"] },
  { id: "tiranga", swatch: ["#ff9933", "#ffffff", "#138808"] },
  { id: "midnight", swatch: ["#05070f", "#0d1222", "#4cd7ff"] },
  { id: "aurora", swatch: ["#2a1f5c", "#0f3d4a", "#7cf0d0"] },
  { id: "contrast", swatch: ["#000000", "#ffffff", "#ffe600"] },
];

export default function SkinPicker({ value, onChange, t }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const current = SKINS.find((s) => s.id === value) || SKINS[0];

  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => !box.current?.contains(e.target) && setOpen(false);
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div className="skin-pick" ref={box}>
      <button
        type="button"
        className="ghost skin-btn"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Swatch colors={current.swatch} />
        <span>{t.themeLabel}</span>
      </button>
      {open && (
        <ul className="skin-menu" role="menu">
          {SKINS.map((s) => (
            <li key={s.id} role="none">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={value === s.id}
                className={value === s.id ? "on" : ""}
                onClick={() => {
                  onChange(s.id);
                  setOpen(false);
                }}
              >
                <Swatch colors={s.swatch} />
                <span>{t.themes[s.id]}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Swatch({ colors }) {
  return (
    <span className="swatch" aria-hidden="true">
      <i style={{ background: colors[0] }} />
      <i style={{ background: colors[1] }} />
      <i style={{ background: colors[2] }} />
    </span>
  );
}
