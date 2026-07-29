const ORCH = process.env.ORCHESTRATOR_URL ?? "http://orchestrator:8080";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const r = await fetch(`${ORCH}/runs/${params.id}`, { cache: "no-store" });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
