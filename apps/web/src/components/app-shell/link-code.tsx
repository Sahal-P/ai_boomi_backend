"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

/** Shown size in CSS pixels: big enough for a phone camera held at arm's length. */
const QR_SIZE = 256;

/**
 * The scannable twin of a WhatsApp link, for people on a computer. Drawn locally as a data URL —
 * nothing is fetched — and the QR library itself loads only when a code is shown.
 */
export function LinkCode({
  link,
  size = QR_SIZE,
  alt = "QR code that opens FinBoy's WhatsApp chat",
}: {
  link: string;
  size?: number;
  alt?: string;
}) {
  const [image, setImage] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    // Drawn at twice the shown size so the modules stay sharp on high-density screens.
    import("qrcode")
      .then(({ toDataURL }) => toDataURL(link, { margin: 1, width: size * 2, errorCorrectionLevel: "M" }))
      .then(
        (url) => {
          if (current) setImage(url);
        },
        () => undefined,
      );
    return () => {
      current = false;
    };
  }, [link, size]);
  if (!image) {
    return <div style={{ width: size, height: size }} className="rounded-2xl bg-white/60" aria-hidden="true" />;
  }
  return (
    <Image src={image} unoptimized width={size} height={size} alt={alt} className="rounded-2xl bg-white p-3" />
  );
}
