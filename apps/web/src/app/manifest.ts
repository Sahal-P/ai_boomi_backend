import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "FinBoy",
    short_name: "FinBoy",
    description: "Your personal finance companion.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#e1e3e6",
    theme_color: "#e1e3e6",
    icons: [
      { src: "/brand/finboy-icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/brand/finboy-icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/brand/finboy-icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
