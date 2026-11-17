const DOWN = new Set(["Failed to fetch", "Internal Server Error", "Bad Gateway", "Service Unavailable", "Gateway Timeout"]);

export function errorText(err, t) {
  if (!err) return "";
  if (err.status === 429) return t.rateLimited;
  if (DOWN.has(err.message)) return t.offline;
  return `${t.error}: ${err.message}`;
}

export default function ErrorBox({ error, t }) {
  if (!error) return null;
  return (
    <div className="note bad" role="alert">
      {errorText(error, t)}
    </div>
  );
}
