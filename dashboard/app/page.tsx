"use client";

import { useCallback, useEffect, useState } from "react";

type Project = {
  run_id: string;
  name?: string | null;
  intent: string;
  status: string;
  phase?: string | null;
  pr_url?: string | null;
  created_at?: string;
  active?: boolean;
  queue_position?: number;
};

type Detail = Project & {
  journal?: string[];
  steps?: number;
  fix_iters?: number;
  implemented?: string[];
};

const STATUS_COLORS: Record<string, string> = {
  queued: "#8a8f98",
  running: "#3b82f6",
  done: "#22c55e",
  blocked: "#f59e0b",
  error: "#ef4444",
};

function Badge({ status }: { status: string }) {
  return (
    <span
      style={{
        background: STATUS_COLORS[status] ?? "#555",
        color: "#0b0e14",
        borderRadius: 6,
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: 0.5,
      }}
    >
      {status}
    </span>
  );
}

const card: React.CSSProperties = {
  background: "#12161f",
  border: "1px solid #1e2530",
  borderRadius: 10,
  padding: 16,
  marginBottom: 12,
};

export default function Home() {
  const [intent, setIntent] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/api/runs", { cache: "no-store" });
      const d = await r.json();
      setProjects(d.projects ?? []);
    } catch {
      /* transient */
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    try {
      const r = await fetch(`/api/runs/${id}`, { cache: "no-store" });
      if (r.ok) setDetail(await r.json());
    } catch {
      /* transient */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    loadDetail(selected);
    const t = setInterval(() => loadDetail(selected), 2000);
    return () => clearInterval(t);
  }, [selected, loadDetail]);

  async function submit() {
    if (!intent.trim()) return;
    setSubmitting(true);
    try {
      const r = await fetch("/api/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ intent: intent.trim() }),
      });
      const d = await r.json();
      setIntent("");
      await refresh();
      if (d.run_id) setSelected(d.run_id);
    } finally {
      setSubmitting(false);
    }
  }

  const running = projects.find((p) => p.status === "running");
  const queued = projects
    .filter((p) => p.status === "queued")
    .sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0));
  const history = projects.filter((p) => !["running", "queued"].includes(p.status));

  return (
    <main style={{ maxWidth: 980, margin: "0 auto", padding: "32px 20px" }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>BAX Autopilot</h1>
      <p style={{ color: "#8a8f98", marginTop: 0 }}>
        Describe an app. One project builds at a time; the rest queue.
      </p>

      {/* Intent form */}
      <div style={card}>
        <textarea
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder="e.g. a full-stack todo app with email/password auth and a tasks API"
          rows={3}
          style={{
            width: "100%",
            background: "#0b0e14",
            color: "#e6e6e6",
            border: "1px solid #1e2530",
            borderRadius: 8,
            padding: 12,
            fontSize: 14,
            resize: "vertical",
            boxSizing: "border-box",
          }}
        />
        <div style={{ marginTop: 10, display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={submit}
            disabled={submitting || !intent.trim()}
            style={{
              background: "#3b82f6",
              color: "white",
              border: 0,
              borderRadius: 8,
              padding: "10px 18px",
              fontWeight: 700,
              cursor: submitting ? "default" : "pointer",
              opacity: submitting || !intent.trim() ? 0.5 : 1,
            }}
          >
            {submitting ? "Starting…" : "Start"}
          </button>
          {running && (
            <span style={{ color: "#8a8f98", fontSize: 13 }}>
              A project is running — new intents will queue.
            </span>
          )}
        </div>
      </div>

      {/* Running */}
      {running && (
        <section>
          <h2 style={{ fontSize: 14, color: "#8a8f98", textTransform: "uppercase" }}>Running</h2>
          <ProjectCard p={running} onClick={() => setSelected(running.run_id)} />
        </section>
      )}

      {/* Queued */}
      {queued.length > 0 && (
        <section>
          <h2 style={{ fontSize: 14, color: "#8a8f98", textTransform: "uppercase" }}>
            Queued ({queued.length})
          </h2>
          {queued.map((p) => (
            <ProjectCard key={p.run_id} p={p} onClick={() => setSelected(p.run_id)} />
          ))}
        </section>
      )}

      {/* History */}
      <section>
        <h2 style={{ fontSize: 14, color: "#8a8f98", textTransform: "uppercase" }}>History</h2>
        {history.length === 0 && <p style={{ color: "#555" }}>No finished projects yet.</p>}
        {history.map((p) => (
          <ProjectCard key={p.run_id} p={p} onClick={() => setSelected(p.run_id)} />
        ))}
      </section>

      {/* Detail drawer */}
      {selected && detail && (
        <DetailPanel detail={detail} onClose={() => setSelected(null)} />
      )}
    </main>
  );
}

function ProjectCard({ p, onClick }: { p: Project; onClick: () => void }) {
  return (
    <div style={{ ...card, cursor: "pointer" }} onClick={onClick}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong>{p.name || p.intent.slice(0, 60)}</strong>
        <Badge status={p.status} />
      </div>
      <div style={{ color: "#8a8f98", fontSize: 13, marginTop: 6 }}>{p.intent}</div>
      <div style={{ color: "#5b6472", fontSize: 12, marginTop: 6 }}>
        {p.status === "queued" && p.queue_position != null
          ? `queue #${p.queue_position}`
          : p.phase
            ? `phase: ${p.phase}`
            : ""}
        {p.pr_url ? " · PR ready" : ""}
      </div>
    </div>
  );
}

function DetailPanel({ detail, onClose }: { detail: Detail; onClose: () => void }) {
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "min(520px, 92vw)",
        height: "100vh",
        background: "#0e1219",
        borderLeft: "1px solid #1e2530",
        padding: 20,
        overflowY: "auto",
        boxShadow: "-16px 0 40px rgba(0,0,0,0.5)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{detail.name || "project"}</h3>
        <button
          onClick={onClose}
          style={{ background: "none", border: 0, color: "#8a8f98", fontSize: 22, cursor: "pointer" }}
        >
          ×
        </button>
      </div>
      <div style={{ margin: "8px 0" }}>
        <Badge status={detail.status} />{" "}
        <span style={{ color: "#8a8f98", fontSize: 13 }}>
          phase {detail.phase} · steps {detail.steps ?? 0} · fixes {detail.fix_iters ?? 0}
        </span>
      </div>
      <p style={{ color: "#8a8f98", fontSize: 13 }}>{detail.intent}</p>
      {detail.pr_url && (
        <p>
          <a href={detail.pr_url} target="_blank" rel="noreferrer" style={{ color: "#3b82f6" }}>
            View pull request →
          </a>
        </p>
      )}
      <h4 style={{ color: "#8a8f98", fontSize: 13, textTransform: "uppercase" }}>Journal</h4>
      <pre
        style={{
          background: "#0b0e14",
          border: "1px solid #1e2530",
          borderRadius: 8,
          padding: 12,
          fontSize: 12,
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {(detail.journal ?? []).join("\n") || "…"}
      </pre>
    </div>
  );
}
