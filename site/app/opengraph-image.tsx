import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { data, loadCall } from "@/lib/data";
import { buildBoard, clock } from "@/lib/timeline";

export const alt = "Tellerline: bank calls, answered on one MacBook Air";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The card is the board: the claim in strip print, and one real turn of a recorded call as its
// flight strip, the wait circled in pen. Static instances of Mona Sans and Martian Mono (SIL OFL
// 1.1), since the image renderer reads no variable axes.
const FONTS = [
  ["Mona Condensed", "MonaSans-CondensedExtraBold.ttf", 800],
  ["Mona Sans", "MonaSans-Regular.ttf", 400],
  ["Mona Sans", "MonaSans-SemiBold.ttf", 600],
  ["Martian Mono", "MartianMono-Medium.ttf", 500],
] as const;

const INK = "#16191d";
const INK_2 = "#46505a";
const INK_3 = "#5b646e";
const RULE = "#cdd3da";

export default async function OpenGraphImage() {
  const fonts = await Promise.all(
    FONTS.map(async ([name, file, weight]) => ({
      name,
      data: await readFile(path.join(process.cwd(), "app", "og", file)),
      weight,
      style: "normal" as const,
    })),
  );
  const call = await loadCall(data.calls[0].slug);
  const turn = call.turns.find((item) => item.action?.tool === "freeze_card") ?? call.turns[0];
  const strip = buildBoard(call).strips.find((item) => item.turn === turn.turn);
  const wait = strip?.wait ? strip.wait.until - strip.wait.from : null;
  const latency = data.live.gate?.latency_s;
  const label = { fontFamily: "Mona Sans", fontWeight: 600, fontSize: 14, letterSpacing: "0.1em", textTransform: "uppercase" as const, color: INK_3 };

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
          background: "linear-gradient(180deg, #edf0f2 0%, #e4e8ec 60%, #e7eaed 100%)",
          color: INK,
          fontFamily: "Mona Sans",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <svg width="44" height="24" viewBox="0 0 34 18">
              <rect x="0" y="0" width="17" height="18" rx="3" fill="#f2c14e" />
              <rect x="17" y="0" width="17" height="18" rx="3" fill="#2f6fd6" />
              <rect x="11" y="0" width="12" height="18" fill="#2f6fd6" />
              <rect x="11" y="0" width="6" height="18" fill="#f2c14e" />
              <rect x="5" y="3" width="24" height="12" rx="1.5" fill="#ffffff" />
              <rect x="8" y="6.5" width="9" height="2" rx="1" fill={INK} />
              <rect x="8" y="10" width="14" height="1.5" rx="0.75" fill="#9aa3ad" />
            </svg>
            <span style={{ fontFamily: "Mona Condensed", fontSize: 34, textTransform: "uppercase" }}>Tellerline</span>
          </div>
          {latency ? (
            <span style={{ fontFamily: "Martian Mono", fontSize: 21, color: INK_2 }}>
              nine in ten replies within {latency.p90.toFixed(2)} s
            </span>
          ) : null}
        </div>

        <div style={{ display: "flex", fontFamily: "Mona Condensed", fontSize: 92, lineHeight: 0.94, textTransform: "uppercase", maxWidth: 980 }}>
          Bank calls, answered on one MacBook Air.
        </div>

        {/* One turn of the recorded call, as its strip in a holder: amber for the caller, blue
            for Tellerline. */}
        <div
          style={{
            display: "flex",
            padding: "4px 14px",
            borderRadius: 8,
            background: "linear-gradient(90deg, #f2c14e 0%, #f2c14e 50%, #2f6fd6 50%, #2f6fd6 100%)",
          }}
        >
          <div style={{ display: "flex", flex: 1, background: "#ffffff", borderRadius: 4, boxShadow: "0 2px 8px rgba(22,25,29,0.14)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 118, padding: "14px 16px" }}>
              <span style={label}>turn {turn.turn}</span>
              <span style={{ fontFamily: "Martian Mono", fontSize: 24 }}>{clock(strip?.feedAt ?? turn.t).slice(0, 5)}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, padding: "14px 18px", borderLeft: `1px solid ${RULE}` }}>
              <span style={{ ...label, color: "#7a5a00" }}>caller said</span>
              <span style={{ fontSize: 22, lineHeight: 1.25 }}>{turn.said ?? turn.heard}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 300, padding: "14px 18px", borderLeft: `1px solid ${RULE}` }}>
              <span style={{ ...label, color: "#1f57b5" }}>decided</span>
              <span style={{ fontFamily: "Martian Mono", fontSize: 18, lineHeight: 1.3, color: "#1f57b5" }}>{turn.model.output.trim()}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, width: 176, padding: "14px 18px", borderLeft: `1px solid ${RULE}` }}>
              <span style={label}>wait</span>
              <div style={{ display: "flex", position: "relative", width: 124 }}>
                <span style={{ fontFamily: "Martian Mono", fontSize: 28, color: "#c2301f", whiteSpace: "nowrap" }}>{wait === null ? "" : `${wait.toFixed(2)} s`}</span>
                <svg width="146" height="58" viewBox="0 0 100 40" style={{ position: "absolute", left: -14, top: -11 }}>
                  <path
                    d="M64 4C40 1 10 5 5 17c-4 10 13 19 41 19 27 0 49-6 50-17C97 8 78 3 56 4c-6 0-11 1-15 2"
                    fill="none"
                    stroke="#d93a2b"
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
