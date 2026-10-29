import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: "standalone",
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  async rewrites() {
    const origin = process.env.FINBOY_API_ORIGIN;
    if (!origin) return [];
    const url = new URL(origin);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
      throw new Error("FINBOY_API_ORIGIN must be an HTTPS origin");
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
