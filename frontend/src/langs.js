// Languages for speaking and for answers. `bcp` is what the browser's speech engines expect.
// The screen text is translated for English and Hindi only; the other languages get answers and voice.
export const LANGS = [
  { code: "en", native: "English", bcp: "en-IN", listening: "Listening…" },
  { code: "hi", native: "हिन्दी", bcp: "hi-IN", listening: "सुन रहा हूँ…" },
  { code: "mr", native: "मराठी", bcp: "mr-IN", listening: "ऐकत आहे…" },
  { code: "bn", native: "বাংলা", bcp: "bn-IN", listening: "শুনছি…" },
  { code: "ta", native: "தமிழ்", bcp: "ta-IN", listening: "கேட்கிறேன்…" },
  { code: "te", native: "తెలుగు", bcp: "te-IN", listening: "వింటున్నాను…" },
  { code: "gu", native: "ગુજરાતી", bcp: "gu-IN", listening: "સાંભળી રહ્યો છું…" },
  { code: "pa", native: "ਪੰਜਾਬੀ", bcp: "pa-IN", listening: "ਸੁਣ ਰਿਹਾ ਹਾਂ…" },
];
export const langOf = (code) => LANGS.find((l) => l.code === code) || LANGS[0];
export const hasUiText = (code) => code === "en" || code === "hi";
