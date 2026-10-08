"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { type Board, buildBoard, clock, onScale, SCALE_S, type TurnStrip } from "@/lib/timeline";
import type { Call } from "@/lib/types";

import { Ruler, Spread } from "./Scale";
import { StripMark } from "./StripMark";
import { Greeting, PenCircle, Strip } from "./Strips";
import { Waveform } from "./Waveform";

// One frame of the film at time t, drawn the same way every time so a headless browser can step
// through it: scripts/render_film.py calls window.__setFilmTime(t) and takes a screenshot.
// The film runs INTRO_S of title card, the call itself, then OUTRO_S of end card. It is the
// page's own strip board, laid out at 1422 by 800 and drawn at 1.35 times that: 1920 by 1080.

export const INTRO_S = 6;
export const OUTRO_S = 6;

const FEED_S = 0.42; // as long as a strip takes to feed in on the page
const PEN_S = 0.48; // and the pen to circle a wait
const GAP_PX = 10; // between strips in the bay

declare global {
  interface Window {
    __setFilmTime?: (t: number) => Promise<void>;
    __filmLength?: number;
  }
}

type Props = { call: Call; numbers: { p50: number; p90: number; turns: number } | null };

// Every frame is a still: nothing animates by the wall clock, only by the film's own.
const STILL = "*,*::before,*::after{transition:none!important;animation:none!important}";

export function FilmFrame({ call, numbers }: Props) {
  const [time, setTime] = useState(0);
  const board = useMemo(() => buildBoard(call), [call]);

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
  return (
    <div className="h-[800px] w-[1422px] overflow-hidden" style={{ zoom: 1.35 }}>
      <style>{STILL}</style>
      {now < 0 ? (
        <TitleCard call={call} />
      ) : now > call.duration_s ? (
        <EndCard numbers={numbers} />
      ) : (
        <FilmBoard call={call} board={board} now={now} />
      )}
    </div>
  );
}

function FilmBoard({ call, board, now }: { call: Call; board: Board; now: number }) {
  const nowRef = useRef(now);
  nowRef.current = now;
  const list = useRef<HTMLOListElement>(null);
  const fed = board.strips.filter((strip) => strip.feedAt <= now + 1e-6);
  const newest = fed[fed.length - 1];

  // A new strip feeds in at the top and the rest snap down one step, on the film's clock.
  useLayoutEffect(() => {
    const element = list.current;
    if (!element) return;
    const first = element.firstElementChild as HTMLElement | null;
    const age = newest ? now - newest.feedAt : Number.POSITIVE_INFINITY;
    if (first && age < FEED_S) {
      const step = first.offsetHeight + GAP_PX;
      element.style.transform = `translateY(${(-step * (1 - snap(age / FEED_S))).toFixed(2)}px)`;
    } else {
      element.style.transform = "";
    }
  });

  return (
    <div className="flex h-full flex-col gap-4 px-8 pb-6 pt-5">
      <header className="flex items-center justify-between gap-6">
        <span className="flex items-center gap-3">
          <StripMark className="h-[20px] w-[38px]" />
          <span className="callsign text-[1.65rem]">Tellerline</span>
        </span>
        <span className="text-[0.95rem] text-ink-2">
          A real call, recorded on a MacBook Air M5. The caller&apos;s voice is synthetic.
        </span>
        <span className="print text-[1.45rem] font-semibold">{clock(now)}</span>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)] gap-5">
        <div className="well min-h-0 overflow-hidden p-3">
          <ol ref={list} className="flex min-h-full flex-col" style={{ gap: GAP_PX }}>
            {[...fed].reverse().map((strip) => (
              <li key={strip.turn}>
                <Strip strip={strip} now={now} live={strip === newest} instant pulled={false} pen={penProgress(strip, now)} />
              </li>
            ))}
            {board.greeting && now >= board.greeting.at ? (
              <li>
                <Greeting greeting={board.greeting} now={now} instant={false} />
              </li>
            ) : null}
          </ol>
        </div>
        <Waits board={board} now={now} newest={newest} />
      </div>

      <div className="holder-agent">
        <div className="strip px-4 pb-2.5 pt-2.5">
          <div className="flex items-baseline justify-between gap-4">
            <p className="callsign text-[1.3rem]">
              {call.title}
              <span className="print ml-3 align-middle text-[0.72rem] font-normal normal-case tracking-normal text-ink-3">
                {call.call_id}
              </span>
            </p>
            <p className="flex items-center gap-4 text-[0.8rem] text-ink-2">
              <span className="flex items-center gap-1.5">
                <i className="inline-block h-3 w-1.5 rounded-[1px] bg-[#d9a21f]" /> caller
              </span>
              <span className="flex items-center gap-1.5">
                <i className="inline-block h-3 w-1.5 rounded-[1px] bg-blue" /> Tellerline
              </span>
              <span className="flex items-center gap-1.5">
                <i className="inline-block h-1.5 w-4 border-x-[1.5px] border-b-[1.5px] border-ink" /> the wait
              </span>
            </p>
          </div>
          <div className="mt-2">
            <Waveform
              caller={call.envelope.caller}
              agent={call.envelope.agent}
              hz={call.envelope_hz}
              duration={call.duration_s}
              gaps={board.gaps}
              now={nowRef}
              playing
              highlight={null}
              onSeek={() => {}}
              label={`The whole call, ${call.title}`}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// The right of the board: the live wait, large, circled in pen when Tellerline answers; under it
// every wait in the call so far on the page's one scale.
function Waits({ board, now, newest }: { board: Board; now: number; newest: TurnStrip | undefined }) {
  const timed = board.strips.filter((strip) => strip.wait && now >= strip.wait.from);
  const current = newest?.wait && now >= newest.wait.from ? newest : timed[timed.length - 1];
  const wait = current?.wait ?? null;
  const answered = wait ? now >= wait.until : false;
  const value = wait ? Math.min(now, wait.until) - wait.from : null;
  return (
    <aside className="flex min-h-0 flex-col gap-4">
      <div className="holder-turn">
        <div className="strip px-6 pb-5 pt-4">
          <p className="label">{current ? `turn ${current.turn}: the caller waited` : "the wait"}</p>
          <p className="mt-4 h-[4.25rem]">
            {value !== null ? (
              <span className={`print relative inline-block text-[4.25rem] font-semibold leading-none ${answered && current === newest ? "text-red-ink" : ""}`}>
                {value.toFixed(2)}
                <span className="text-[0.42em] font-normal"> s</span>
                {answered && current ? (
                  <PenCircle
                    settled={current !== newest}
                    instant
                    progress={(now - wait!.until) / PEN_S}
                    weight={1.4}
                    className="-left-[2.6rem] -top-4 h-[calc(100%+2rem)] w-[calc(100%+4.4rem)]"
                  />
                ) : null}
              </span>
            ) : (
              <span className="text-[1.05rem] text-ink-2">The wait is timed from the caller&apos;s last word.</span>
            )}
          </p>
          <p className="mt-4 min-h-[1.5em] text-[0.95rem] text-ink-2">
            {answered && wait?.callerWait != null ? `${wait.callerWait.toFixed(2)} s for the caller, WebRTC both ways` : " "}
          </p>
        </div>
      </div>

      <div className="holder-plain">
        <div className="strip flex flex-col px-5 pb-3 pt-4">
          <p className="label">every wait in this call, on one scale</p>
          {timed.length ? null : (
            <p className="mt-3 text-[0.95rem] text-ink-2">Each wait joins the scale as Tellerline answers.</p>
          )}
          <ol className="mt-4 flex flex-col gap-2.5">
            {timed.map((strip) => {
              const span = strip.wait!;
              const seconds = Math.min(now, span.until) - span.from;
              return (
                <li key={strip.turn} className="grid grid-cols-[3.25rem_minmax(0,1fr)_3.5rem] items-center gap-3">
                  <span className="print text-[0.8rem] text-ink-3">turn {strip.turn}</span>
                  <span className="scale-ticks relative block h-4 rounded-[1px] bg-[#f3f5f7]">
                    <span
                      className={`absolute inset-y-0.5 left-0 rounded-[1px] ${strip === current ? "bg-blue" : "bg-ink"}`}
                      style={{ width: `${onScale(seconds) * 100}%` }}
                    />
                  </span>
                  <span className="print text-right text-[0.85rem] font-semibold">{seconds.toFixed(2)} s</span>
                </li>
              );
            })}
          </ol>
          <div className="mt-1 grid grid-cols-[3.25rem_minmax(0,1fr)_3.5rem] gap-3 pt-2">
            <span />
            <Ruler />
            <span />
          </div>
        </div>
      </div>
    </aside>
  );
}

function penProgress(strip: TurnStrip, now: number): number | undefined {
  if (!strip.wait || now < strip.wait.until) return undefined;
  return (now - strip.wait.until) / PEN_S;
}

function TitleCard({ call }: { call: Call }) {
  return (
    <div className="flex h-full items-center justify-center px-16">
      <div className="holder-turn w-fit max-w-[56rem]">
        <div className="strip px-14 pb-12 pt-10">
          <p className="flex items-center gap-3">
            <StripMark className="h-[22px] w-[42px]" />
            <span className="callsign text-[1.6rem]">Tellerline</span>
          </p>
          <h1 className="callsign mt-8 text-[4.6rem]">
            Bank calls, answered
            <br />
            on one MacBook Air.
          </h1>
          <p className="mt-8 max-w-[46ch] text-[1.25rem] leading-snug text-ink-2">
            A real call. {call.summary} The caller is a synthetic voice; everything Tellerline says
            is generated live on the Mac.
          </p>
        </div>
      </div>
    </div>
  );
}

function EndCard({ numbers }: { numbers: Props["numbers"] }) {
  return (
    <div className="flex h-full items-center justify-center px-16">
      <div className="holder-agent w-[52rem]">
        <div className="strip px-14 pb-12 pt-10">
          <p className="callsign text-[4rem]">Tellerline</p>
          {numbers ? (
            <>
              <p className="mt-6 max-w-[44ch] text-[1.45rem] leading-snug">
                Over {numbers.turns} measured replies, half arrived within {numbers.p50.toFixed(2)} s and
                nine in ten within {numbers.p90.toFixed(2)} s, on the {SCALE_S} s target.
              </p>
              <div className="mt-8">
                <Spread p50={numbers.p50} p90={numbers.p90} />
                <Ruler />
              </div>
            </>
          ) : null}
          <p className="key mt-8 w-fit text-[1.35rem]" data-primary="">
            github.com/ag2502/Tellerline
          </p>
        </div>
      </div>
    </div>
  );
}

// The page's snap, cubic-bezier(0.3, 1.45, 0.55, 1), solved for a given share of its time.
function snap(x: number): number {
  const [x1, y1, x2, y2] = [0.3, 1.45, 0.55, 1];
  const curve = (t: number, a: number, b: number) => 3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3;
  const slope = (t: number, a: number, b: number) => 3 * a * (1 - t) ** 2 + 6 * (b - a) * (1 - t) * t + 3 * (1 - b) * t ** 2;
  const share = Math.min(1, Math.max(0, x));
  let t = share;
  for (let i = 0; i < 10; i++) {
    const error = curve(t, x1, x2) - share;
    const d = slope(t, x1, x2);
    if (Math.abs(error) < 1e-6 || Math.abs(d) < 1e-6) break;
    t = Math.min(1, Math.max(0, t - error / d));
  }
  return curve(t, y1, y2);
}
