import type { MetadataRoute } from "next";
import { CONTENT_UPDATED_AT, features, guides } from "@/lib/seo/content";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/about", "/press", "/pricing", "/contact", "/privacy-policy", "/terms", "/refund-policy", "/guides", ...Object.keys(features).map((slug) => `/features/${slug}`), ...Object.keys(guides).map((slug) => `/guides/${slug}`)].map(
    (path) => ({ url: `https://finboy.io${path}`, ...((path === "" || path.startsWith("/features/") || path.startsWith("/guides")) ? { lastModified: CONTENT_UPDATED_AT } : {}) }),
  );
}
