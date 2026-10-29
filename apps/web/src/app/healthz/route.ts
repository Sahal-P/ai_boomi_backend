export const dynamic = "force-dynamic";

export function GET() {
  const revision = process.env.FINBOY_RELEASE_SHA;
  if (!revision || !/^[a-f0-9]{40}$/.test(revision)) {
    return Response.json({ status: "unavailable", revision: null }, {
      status: 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
  return Response.json({ status: "ok", revision }, {
    headers: { "Cache-Control": "no-store" },
  });
}
