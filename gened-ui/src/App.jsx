import { useEffect, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function Badge({ text }) {
  return (
    <span style={{
      fontSize: 12, padding: "4px 10px",
      border: "1px solid #ddd", borderRadius: 999, background: "#fafafa"
    }}>
      {text}
    </span>
  );
}

export default function App() {
  const [q, setQ] = useState("i series");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function runSearch(query) {
    setLoading(true); setErr("");
    try {
      const url = new URL(`${API_BASE}/search`);
      url.searchParams.set("q", query);
      url.searchParams.set("top_k", "10");
      url.searchParams.set("alpha", "0.6");

      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setErr(e?.message || String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { runSearch(q); }, []);

  return (
    <div style={{ maxWidth: 950, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1 style={{ marginBottom: 6 }}>GenEd Search</h1>
      <div style={{ opacity: 0.7, marginBottom: 18 }}>
        Search GenEds and see GPA + ease.
      </div>

      <form onSubmit={(e) => { e.preventDefault(); runSearch(q); }}
            style={{ display: "flex", gap: 10, marginBottom: 18 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Try: i series, humanities, easy gen ed..."
          style={{ flex: 1, padding: 12, borderRadius: 10, border: "1px solid #ddd" }}
        />
        <button type="submit" disabled={loading}
                style={{ padding: "12px 16px", borderRadius: 10, border: "1px solid #ddd",
                         cursor: loading ? "not-allowed" : "pointer", background: "white" }}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {err && (
        <div style={{ padding: 12, border: "1px solid #f3c", borderRadius: 10 }}>
          <b>Error:</b> {err}
          <div style={{ marginTop: 6, fontSize: 12, opacity: 0.7 }}>
            Backend should be running at {API_BASE}
          </div>
        </div>
      )}

      {data && (
        <div style={{ display: "grid", gap: 12 }}>
          {data.results.map((r) => {
            const m = r.meta || {};
            const gpa = m.avg_gpa != null ? Number(m.avg_gpa).toFixed(2) : null;
            const ease = m.ease_score != null ? Number(m.ease_score).toFixed(2) : null;

            return (
              <div key={r.doc_id}
                   style={{ border: "1px solid #eee", borderRadius: 14, padding: 14, background: "white",color: "#111", }}>
                <div style={{ fontWeight: 750 }}>{r.title || r.doc_id}</div>
                {r.snippet && <div style={{ marginTop: 6, color: "#333", opacity: 0.85 }}>{r.snippet}</div>}

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                  {m.geneds && <Badge text={m.geneds} />}
                  {m.credits != null && <Badge text={`${m.credits} cr`} />}
                  {gpa && <Badge text={`GPA ${gpa}`} />}
                  {ease && <Badge text={`Ease ${ease}`} />}
                </div>

                <div style={{ marginTop: 8, fontSize: 12, opacity: 0.6 }}>
                  score: {Number(r.score).toFixed(3)} • kind: {r.kind}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
