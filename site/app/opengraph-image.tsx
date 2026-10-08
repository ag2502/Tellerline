import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { data, loadCall } from "@/lib/data";
import { buildBoard, clock } from "@/lib/timeline";

export const alt = "Tellerline: bank calls, answered on one MacBook Air";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The card is the page: the claim in lit type, and one real turn of a recorded call
// as a card, the wait circled. Static instances of Bricolage Grotesque, Geist and Geist Mono (SIL
// OFL 1.1), since the image renderer reads no variable axes.
const FONTS = [
  ["Bricolage", "Bricolage-Bold.woff", 700, "normal"],
  ["Geist", "Geist-Regular.ttf", 400, "normal"],
  ["Geist", "Geist-SemiBold.ttf", 600, "normal"],
  ["Geist Mono", "GeistMono-Medium.ttf", 500, "normal"],
] as const;

const INK = "#f4f1ff";
const INK_2 = "#b9b4d0";
const INK_3 = "#948fb2";
const RULE = "#27233b";
const ACCENT = "#ff6b8b";
const ACCENT_INK = "#ff8fa8";
const TEAL = "#4fe3c8";

export default async function OpenGraphImage() {
  const fonts = await Promise.all(
    FONTS.map(async ([name, file, weight, style]) => ({
      name,
      data: await readFile(path.join(process.cwd(), "app", "og", file)),
      weight,
      style,
    })),
  );
  const call = await loadCall(data.calls[0].slug);
  const turn = call.turns.find((item) => item.action?.tool === "freeze_card") ?? call.turns[0];
  const strip = buildBoard(call).strips.find((item) => item.turn === turn.turn);
  const wait = strip?.wait ? strip.wait.until - strip.wait.from : null;
  const latency = data.live.gate?.latency_s;
  const label = { fontFamily: "Geist Mono", fontWeight: 500, fontSize: 13, letterSpacing: "0.06em", textTransform: "uppercase" as const, color: INK_3 };

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "52px 64px 56px",
          background: "radial-gradient(900px 500px at 50% -10%, rgba(120,82,255,0.35), #07060d 70%)",
          color: INK,
          fontFamily: "Geist",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <svg width="44" height="24" viewBox="0 0 34 18">
              <rect x="1" y="5" width="6" height="8" rx="3" fill="#4fe3c8" />
              <rect x="10" y="1" width="6" height="16" rx="3" fill="#4fe3c8" />
              <rect x="19" y="3" width="6" height="12" rx="3" fill="#ff6b8b" />
              <rect x="28" y="6.5" width="5" height="5" rx="2.5" fill="#ff6b8b" />
            </svg>
            <span style={{ fontFamily: "Bricolage", fontWeight: 700, fontSize: 34, letterSpacing: "-0.04em" }}>Tellerline</span>
          </div>
          {latency ? (
            <span style={{ fontFamily: "Geist Mono", fontSize: 21, color: INK_2 }}>
              nine in ten replies within {latency.p90.toFixed(2)} s
            </span>
          ) : null}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", fontFamily: "Bricolage", fontWeight: 700, fontSize: 108, lineHeight: 0.98, letterSpacing: "-0.04em", maxWidth: 1060 }}>
          <span style={{ marginRight: 26 }}>Bank calls, answered on one</span>
          <span style={{ color: ACCENT_INK }}>MacBook Air.</span>
        </div>

        {/* One turn of the recorded call, as its strip in a holder: amber for the caller, blue
            for Tellerline. */}
        <div
          style={{
            display: "flex",
            padding: 0,
            borderRadius: 18,
            background: "#131020",
            border: `1px solid ${RULE}`,
          }}
        >
          <div style={{ display: "flex", flex: 1, background: "#131020", borderRadius: 18, borderLeft: `4px solid ${ACCENT}` }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 118, padding: "14px 16px" }}>
              <span style={label}>turn {turn.turn}</span>
              <span style={{ fontFamily: "Geist Mono", fontSize: 24 }}>{clock(strip?.feedAt ?? turn.t).slice(0, 5)}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, padding: "14px 18px", borderLeft: `1px solid ${RULE}` }}>
              <span style={{ ...label, color: TEAL }}>caller said</span>
              <span style={{ fontSize: 22, lineHeight: 1.25 }}>{turn.said ?? turn.heard}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 300, padding: "14px 18px", borderLeft: `1px solid ${RULE}` }}>
              <span style={{ ...label, color: ACCENT_INK }}>decided</span>
              <span style={{ fontFamily: "Geist Mono", fontSize: 18, lineHeight: 1.3, color: ACCENT_INK }}>{turn.model.output.trim()}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 176, padding: "14px 18px", borderLeft: `1px solid ${RULE}` }}>
              <span style={label}>wait</span>
              <div style={{ display: "flex", position: "relative", width: 124 }}>
                <span style={{ fontFamily: "Geist Mono", fontSize: 28, color: ACCENT_INK, whiteSpace: "nowrap" }}>{wait === null ? "" : `${wait.toFixed(2)} s`}</span>
                <svg width="146" height="58" viewBox="0 0 100 40" style={{ position: "absolute", left: -14, top: -11 }}>
                  <path
                    d="M64 4C40 1 10 5 5 17c-4 10 13 19 41 19 27 0 49-6 50-17C97 8 78 3 56 4c-6 0-11 1-15 2"
                    fill="none"
                    stroke={ACCENT}
                    strokeWidth="2.6"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size, fonts },
  );
}
