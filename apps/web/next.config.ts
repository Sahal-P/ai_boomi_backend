import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    const origin = process.env.FINBOY_API_ORIGIN;
    if (!origin) return [];
    const url = new URL(origin);
    // Plain HTTP is accepted only for a loopback API, so the production proxy shape can be
    // exercised locally; any remote origin must be HTTPS.
    const loopback = url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
    if (
      (url.protocol !== "https:" && !loopback) ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    ) {
      throw new Error("FINBOY_API_ORIGIN must be an HTTPS origin (or a loopback HTTP API)");
    }
    return [{ source: "/api/v1/:path*", destination: `${url.origin}/api/v1/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
