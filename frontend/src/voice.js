import { useCallback, useEffect, useRef, useState } from "react";

const Recognition = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;
export const canListen = Boolean(Recognition);
export const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

const ERRORS = {
  "not-allowed": "denied",
  "service-not-allowed": "denied",
  "no-speech": "noSpeech",
  "audio-capture": "noMic",
  network: "network",
  "language-not-supported": "langUnsupported",
};

/**
 * Speech to text using the browser's own engine (Chrome, Edge, Samsung Internet).
 * onDone(text) is called once when listening ends with some text.
 */
export function useListen({ bcp, onDone }) {
  const [listening, setListening] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState(null);
  const rec = useRef(null);
  const latest = useRef("");
  const done = useRef(onDone);
  done.current = onDone;

  const stop = useCallback(() => rec.current?.stop(), []);
  // Throw away what was heard: clear it first so onend does not submit it.
  const cancel = useCallback(() => {
    latest.current = "";
    setText("");
    try {
      rec.current?.abort();
    } catch {}
  }, []);

  const start = useCallback(() => {
    if (!Recognition) {
      setError("unsupported");
      return;
    }
    try {
      rec.current?.abort();
    } catch {}
    setError(null);
    setText("");
    latest.current = "";
    const r = new Recognition();
    r.lang = bcp;
    r.interimResults = true;
    r.continuous = !/Android/i.test(navigator.userAgent); // Android Chrome repeats words in continuous mode
    r.maxAlternatives = 1;
    r.onresult = (e) => {
      let s = "";
      for (let i = 0; i < e.results.length; i++) s += e.results[i][0].transcript;
      latest.current = s.trim();
      setText(latest.current);
    };
    r.onerror = (e) => {
      if (e.error !== "aborted") setError(ERRORS[e.error] || "failed");
    };
    r.onend = () => {
      setListening(false);
      rec.current = null;
      if (latest.current) done.current?.(latest.current);
    };
    rec.current = r;
    try {
      r.start();
      setListening(true);
    } catch {
      setError("failed");
    }
  }, [bcp]);

  useEffect(() => () => {
    try {
      rec.current?.abort();
    } catch {}
  }, []);

  return { listening, text, error, start, stop, cancel, setError };
}

const speakable = (s) =>
  s
    .replace(/\[\d+\]/g, "")
    .replace(/[*_#`]/g, "")
    .replace(/\s+/g, " ")
    .trim();

/** Read-aloud. Only offered when the device has a voice for the language. */
export function useSpeak(bcp) {
  const [voices, setVoices] = useState(() => (canSpeak ? window.speechSynthesis.getVoices() : []));
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    if (!canSpeak) return undefined;
    const update = () => setVoices(window.speechSynthesis.getVoices());
    update();
    window.speechSynthesis.addEventListener("voiceschanged", update);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", update);
  }, []);

  const prefix = bcp.split("-")[0].toLowerCase();
  const voice = voices.find((v) => v.lang.toLowerCase().replace("_", "-") === bcp.toLowerCase())
    || voices.find((v) => v.lang.toLowerCase().startsWith(prefix));

  const speak = useCallback(
    (text) => {
      if (!canSpeak) return;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(speakable(text));
      u.lang = bcp;
      if (voice) u.voice = voice;
      u.rate = 0.95;
      u.onend = u.onerror = () => setSpeaking(false);
      setSpeaking(true);
      window.speechSynthesis.speak(u);
    },
    [bcp, voice],
  );
  const cancel = useCallback(() => {
    if (canSpeak) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  useEffect(() => cancel, [cancel]);
  return { available: canSpeak && Boolean(voice), speaking, speak, cancel };
}
