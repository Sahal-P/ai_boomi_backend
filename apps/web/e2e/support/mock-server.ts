/**
 * TEST-ONLY HTTP wrapper around the fake API for manual browser checks of UI states.
 * Run: node apps/web/e2e/support/mock-server.ts  (loopback only; synthetic data only).
 * Pair it with `NEXT_PUBLIC_API_URL=/ FINBOY_API_ORIGIN=http://127.0.0.1:8032 next dev --port 3032`
 * so the browser exercises the production same-origin proxy shape.
 */
import { createServer } from "node:http";
import { FakeFinBoyApi, type Scenario } from "./fake-api.ts";

const port = Number(process.env.MOCK_API_PORT ?? 8032);
const appOrigin = process.env.MOCK_APP_ORIGIN ?? "http://127.0.0.1:3032";
const scenario: Scenario = { authRequired: process.env.MOCK_AUTH === "required", signedIn: process.env.MOCK_AUTH !== "required", bulk: Number(process.env.MOCK_BULK ?? 0) };
let api = new FakeFinBoyApi(scenario);

createServer((request, response) => {
  const chunks: Buffer[] = [];
  request.on("data", (chunk: Buffer) => chunks.push(chunk));
  request.on("end", async () => {
    const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);
    if (url.pathname === "/__reset") {
      api = new FakeFinBoyApi(scenario);
      response.writeHead(204).end();
      return;
    }
    const text = Buffer.concat(chunks).toString("utf8");
    let body: unknown = null;
    if ((request.headers["content-type"] ?? "").includes("application/json") && text) body = JSON.parse(text);
    const origin = typeof request.headers.origin === "string" ? request.headers.origin : null;
    const result = await api.handle({ method: request.method ?? "GET", path: url.pathname, query: url.searchParams, body, origin }, appOrigin);
    response.writeHead(result.status, { "content-type": "application/json", "cache-control": "no-store", ...result.headers });
    response.end(result.raw ?? (result.body === undefined ? "" : JSON.stringify(result.body)));
  });
}).listen(port, "127.0.0.1", () => {
  console.log(`TEST-ONLY fake FinBoy API on http://127.0.0.1:${port} (synthetic data)`);
});
