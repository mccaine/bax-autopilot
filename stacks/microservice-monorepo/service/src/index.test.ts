import { test } from "node:test";
import assert from "node:assert";
import type { AddressInfo } from "node:net";
import { app } from "./index.ts";

test("GET /healthz returns 200", async () => {
  const server = app.listen(0);
  try {
    const { port } = server.address() as AddressInfo;
    const res = await fetch(`http://localhost:${port}/healthz`);
    assert.strictEqual(res.status, 200);
    const body = (await res.json()) as { status: string };
    assert.strictEqual(body.status, "ok");
  } finally {
    server.close();
  }
});
