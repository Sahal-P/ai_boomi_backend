import type { MetadataRoute } from "next";
import { CONTENT_UPDATED_AT, features, guides } from "@/lib/seo/content";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: "https://finboy.io", lastModified: "2026-11-15" },
    { url: "https://finboy.io/ml", lastModified: "2026-11-23" },
    ...["/about", "/pricing", "/contact", "/privacy-policy", "/terms", "/refund-policy"].map((path) => ({ url: `https://finboy.io${path}` })),
    { url: "https://finboy.io/press", lastModified: "2026-11-15" },
    { url: "https://finboy.io/guides", lastModified: "2026-11-15" },
    { url: "https://finboy.io/tools/cash-upi-expense-diary", lastModified: "2026-11-15" },
    ...Object.entries(features).map(([slug, item]) => ({ url: `https://finboy.io/features/${slug}`, lastModified: item.updatedAt ?? CONTENT_UPDATED_AT })),
    ...Object.entries(guides).map(([slug, item]) => ({ url: `https://finboy.io/guides/${slug}`, lastModified: item.updatedAt ?? CONTENT_UPDATED_AT })),
  ];
}
