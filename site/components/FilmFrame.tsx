"use client";

import { useEffect, useMemo, useState } from "react";

import { buildTimeline, clock, type Line, spokenShare } from "@/lib/timeline";
import type { Call } from "@/lib/types";

// One frame of the film at time t, drawn the same way every time so a headless browser can step
// through it: scripts/render_film.py calls window.__setFilmTime(t) and takes a screenshot.
// The film runs INTRO_S of title card, the call itself, then OUTRO_S of end card.

export const INTRO_S = 6;
export const OUTRO_S = 6;

declare global {
  interface Window {
    __setFilmTime?: (t: number) => Promise<void>;
    __filmLength?: number;
  }
}

type Props = { call: Call; numbers: { p50: number; p90: number; turns: number } | null };

// Lines scrolling off the top fade out rather than being cut through.
const FADE_TOP = "linear-gradient(to bottom, transparent 0, black 22%)";

export function FilmFrame({ call, numbers }: Props) {
  const [time, setTime] = useState(0);
  const timeline = useMemo(() => buildTimeline(call), [call]);

  useEffect(() => {
    window.__filmLength = INTRO_S + call.duration_s + OUTRO_S;
    window.__setFilmTime = (t: number) =>
      new Promise((resolve) => {
        setTime(t);
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      });
    document.documentElement.dataset.filmReady = "1";
  }, [call.duration_s]);

  const now = time - INTRO_S;
  if (now < 0) return <TitleCard call={call} fade={Math.min(1, (INTRO_S - time) / 0.4)} />;
  if (now > call.duration_s) return <EndCard numbers={numbers} />;

  const shown = timeline.lines.filter((line) => line.at <= now + 1e-6);
  // The conversation on the left; each turn's stages go in the panel on the right.
  const recent = shown.filter((line) => line.kind !== "stage").slice(-12);
  const turnLines = currentTurn(shown);

  return (
    <div className="flex h-[1080px] w-[1920px] flex-col overflow-hidden bg-tube px-16 pb-0 pt-12 text-[30px] leading-[1.45]">
      <header className="flex items-baseline justify-between">
        <span className="display text-[40px]">Tellerline</span>
        <span className="dim">a real call, recorded on a MacBook Air M5</span>
        <span className="bloom tabular">{clock(now)}</span>
      </header>
      <div className="rule mt-6" />
      <div className="mt-8 grid min-h-0 flex-1 grid-cols-[1.35fr_1fr] gap-14">
        <ol
          className="flex min-h-0 flex-col justify-end space-y-3 overflow-hidden"
          style={{ maskImage: FADE_TOP, WebkitMaskImage: FADE_TOP }}
        >
          {recent.map((line, index) => (
            <FilmLine key={`${line.kind}-${line.at}-${index}`} line={line} now={now} />
          ))}
        </ol>
        <aside className="flex flex-col gap-8 border-l border-scan pl-12">
          <Stopwatch shown={shown} now={now} />
          <div className="space-y-3">
            <p className="dim">this turn</p>
            {turnLines.map((line, index) => (
              <div key={index} className="grid grid-cols-[5.5em_1fr_4.5em] gap-x-4 text-[28px]">
                <span className="dim">{line.label}</span>
                <span className={`${line.tone === "action" ? "bloom" : "text-p1"} line-clamp-2`}>
                  {line.value}
                </span>
                <span className="after tabular text-right">{line.ms}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
      <FilmStrip call={call} now={now} gaps={timeline.gaps} />
      <div className="inverse -mx-16 mt-6 flex h-[52px] items-center gap-8 px-16 text-[26px]">
        <span>[tellerline]</span>
        <span>0:call*</span>
        <span>Gemma 4 E2B, Parakeet, Kokoro: all on the Mac</span>
      </div>
    </div>
  );
}

function FilmLine({ line, now }: { line: Line; now: number }) {
  if (line.kind === "gap") {
    const waiting = now < line.until;
    const seconds = Math.min(now, line.until) - line.at;
    return (
      <li className="tabular pl-[13.5em]">
        <span className="bloom">
          {waiting ? "waiting " : "replied after "}
          {seconds.toFixed(2)}&nbsp;s
        </span>
        {!waiting && line.callerWait !== null ? (
          <span className="dim block text-[24px]">{line.callerWait.toFixed(2)}&nbsp;s for the caller</span>
        ) : null}
      </li>
    );
  }
  if (line.kind === "stage") return null;
  const share = spokenShare(line.spans, now);
  const live = share > 0 && share < 1;
  return (
    <li className="grid grid-cols-[4.5em_9em_1fr]">
      <span className="after tabular">{clock(line.at).slice(0, 5)}</span>
      <span className={line.kind === "agent" ? "text-p1" : "dim"}>
        {line.kind === "agent" ? "TELLERLINE" : "CALLER"}
      </span>
      <span className={line.kind === "agent" ? (live ? "bloom" : "text-p1") : "dim"}>
        {line.text.slice(0, Math.round(share * line.text.length))}
        {live ? <span className="cursor" style={{ animation: "none" }} /> : null}
      </span>
    </li>
  );
}

function Stopwatch({ shown, now }: { shown: Line[]; now: number }) {
  const gap = [...shown].reverse().find((line) => line.kind === "gap");
  if (!gap || gap.kind !== "gap") {
    return <p className="dim text-[28px]">the reply gap appears when the caller stops talking</p>;
  }
  const waiting = now < gap.until;
  const seconds = Math.min(now, gap.until) - gap.at;
  const heard = !waiting && gap.callerWait !== null;
  return (
    <div>
      <p className="dim">{waiting ? "the caller has stopped" : "Tellerline answered after"}</p>
      <p className="display tabular text-[132px] leading-none">{seconds.toFixed(2)}&nbsp;s</p>
      <p className="dim mt-4 text-[26px]" style={{ visibility: heard ? "visible" : "hidden" }}>
        {gap.callerWait === null ? "" : `${gap.callerWait.toFixed(2)} s by the time the caller heard it`}
      </p>
    </div>
  );
}

function currentTurn(shown: Line[]): { label: string; value: string; ms: string; tone?: string }[] {
  const last = [...shown].reverse().find((line) => line.kind === "caller");
  if (!last || last.kind !== "caller") return [];
  return shown
    .filter((line) => line.kind === "stage" && line.turn === last.turn)
    .map((line) => {
      const stage = line as Extract<Line, { kind: "stage" }>;
      const ms = stage.ms === null ? "" : `${stage.ms < 1 ? "<1" : Math.round(stage.ms)} ms`;
      return { label: stage.label, value: stage.value, ms, tone: stage.tone };
    });
}

function FilmStrip({ call, now, gaps }: { call: Call; now: number; gaps: [number, number][] }) {
  const columns = 300;
  const hz = call.envelope_hz;
  const bars = Array.from({ length: columns }, (_, column) => {
    const from = Math.floor(((column / columns) * call.duration_s) * hz);
    const to = Math.max(from + 1, Math.floor((((column + 1) / columns) * call.duration_s) * hz));
    let up = 0;
    let down = 0;
    for (let i = from; i < to; i++) {
      up = Math.max(up, call.envelope.caller[i] ?? 0);
      down = Math.max(down, call.envelope.agent[i] ?? 0);
    }
    return { up: up / 255, down: down / 255, played: column / columns <= now / call.duration_s };
  });
  return (
    <div className="relative mt-6 h-[120px] w-full" aria-hidden="true">
      <div className="absolute inset-x-0 top-[60px] h-px bg-after" />
      <div className="flex h-full items-stretch gap-[2px]">
        {bars.map((bar, index) => (
          <div key={index} className="relative flex-1">
            <div
              className="absolute bottom-[60px] w-full"
              style={{ height: `${bar.up * 56}px`, background: bar.played ? "#23a14b" : "#0b331e" }}
            />
            <div
              className="absolute top-[61px] w-full"
              style={{ height: `${bar.down * 56}px`, background: bar.played ? "#33ff66" : "#0b331e" }}
            />
          </div>
        ))}
      </div>
      {gaps.map(([start, end]) => (
        <div
          key={start}
          className="absolute bottom-0 h-[6px] border-x border-b border-bloom"
          style={{ left: `${(start / call.duration_s) * 100}%`, width: `${((end - start) / call.duration_s) * 100}%` }}
        />
      ))}
      <div
        className="absolute top-0 h-[114px] w-[3px] bg-bloom"
        style={{ left: `${(now / call.duration_s) * 100}%`, boxShadow: "0 0 12px #b6ffb6" }}
      />
    </div>
  );
}

function TitleCard({ call, fade }: { call: Call; fade: number }) {
  return (
    <div
      className="flex h-[1080px] w-[1920px] flex-col justify-center gap-10 bg-tube px-40"
      style={{ opacity: fade }}
    >
      <p className="dim text-[34px]">[tellerline]</p>
      <h1 className="display max-w-[18ch] text-[104px]">Bank calls, answered on one MacBook Air.</h1>
      <p className="max-w-[54ch] text-[34px] leading-snug">
        A real call. {call.summary} The caller is a synthetic voice; everything Tellerline says is
        generated live on the Mac.
      </p>
    </div>
  );
}

function EndCard({ numbers }: { numbers: Props["numbers"] }) {
  return (
    <div className="flex h-[1080px] w-[1920px] flex-col justify-center gap-10 bg-tube px-40">
      <p className="display text-[96px]">Tellerline</p>
      {numbers ? (
        <p className="max-w-[56ch] text-[38px] leading-snug">
          Over {numbers.turns} measured replies, half arrived within {numbers.p50.toFixed(2)} s and nine
          in ten within {numbers.p90.toFixed(2)} s.
        </p>
      ) : null}
      <p className="bloom text-[44px]">github.com/ag2502/Tellerline</p>
    </div>
  );
}
