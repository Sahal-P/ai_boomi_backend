/**
 * TEST-ONLY wrapper around the fake API for manual browser checks of UI states (loopback only;
 * synthetic data only). FINBOY_API_ORIGIN must be HTTPS, so pass a temporary private certificate
 * (MOCK_TLS_CERT/MOCK_TLS_KEY) and trust it only in Next's Node process via NODE_EXTRA_CA_CERTS —
 * see e2e/README.md.
 */
import { readFileSync } from "node:fs";
import { createServer as createHttpServer, type RequestListener } from "node:http";
import { createServer as createHttpsServer } from "node:https";
import { FakeFinBoyApi, type Scenario } from "./fake-api.ts";

const port = Number(process.env.MOCK_API_PORT ?? 8032);
const appOrigin = process.env.MOCK_APP_ORIGIN ?? "http://127.0.0.1:3032";
const scenario: Scenario = { authRequired: process.env.MOCK_AUTH === "required", signedIn: process.env.MOCK_AUTH !== "required", bulk: Number(process.env.MOCK_BULK ?? 0) };
let api = new FakeFinBoyApi(scenario);

const handler: RequestListener = (request, response) => {
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
};

const tls = process.env.MOCK_TLS_CERT && process.env.MOCK_TLS_KEY
  ? { cert: readFileSync(process.env.MOCK_TLS_CERT), key: readFileSync(process.env.MOCK_TLS_KEY) }
  : null;
(tls ? createHttpsServer(tls, handler) : createHttpServer(handler)).listen(port, "127.0.0.1", () => {
  console.log(`TEST-ONLY fake FinBoy API on ${tls ? "https" : "http"}://127.0.0.1:${port} (synthetic data)`);
});
