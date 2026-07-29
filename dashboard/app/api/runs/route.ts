// Server-side proxy to the orchestrator (keeps it internal; no browser CORS).
const ORCH = process.env.ORCHESTRATOR_URL ?? "http://orchestrator:8080";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await fetch(`${ORCH}/runs`, { cache: "no-store" });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${ORCH}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
