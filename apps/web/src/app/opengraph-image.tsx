import { ImageResponse } from "next/og";

export const alt = "FinBoy — your money, made easier to track";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%", height: "100%", background: "#fed234", color: "#141821", padding: "70px 80px", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", fontSize: 46, fontWeight: 700 }}>FinBoy</div>
      <div style={{ display: "flex", fontSize: 86, fontWeight: 700, letterSpacing: -4, maxWidth: 950 }}>Your money, made easier to track.</div>
      <div style={{ display: "flex", fontSize: 28 }}>WhatsApp · Voice · UPI expenses · finboy.io</div>
    </div>, size,
  );
}
