import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { data } from "@/lib/data";

export const alt = "Tellerline: bank calls, answered on one MacBook Air";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  const font = await readFile(path.join(process.cwd(), "app", "og", "3270-Regular.ttf"));
  const latency = data.live.gate?.latency_s;
  const glow = "0 0 2px #b6ffb6, 0 0 18px rgba(51,255,102,0.55)";
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "#020805",
          color: "#33ff66",
          fontFamily: "IBM 3270",
          backgroundImage:
            "radial-gradient(ellipse at 50% 40%, rgba(7,33,15,0.9) 0%, #020805 70%)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30, color: "#23a14b" }}>
          <span>[tellerline]</span>
          <span>on-device voice banking</span>
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 92,
            lineHeight: 1.05,
            color: "#b6ffb6",
            textShadow: glow,
            textTransform: "uppercase",
            maxWidth: 1000,
          }}
        >
          Bank calls, answered on one MacBook Air.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 32 }}>
          <span style={{ color: "#23a14b" }}>$ python -m bench.caller --turns 220</span>
          {latency ? (
            <span>
              median {latency.p50.toFixed(2)} s, nine in ten within {latency.p90.toFixed(2)} s
            </span>
          ) : (
            <span>Gemma 4, Parakeet and Kokoro, all on the Mac</span>
          )}
        </div>
      </div>
    ),
    { ...size, fonts: [{ name: "IBM 3270", data: font, style: "normal", weight: 400 }] },
  );
}
