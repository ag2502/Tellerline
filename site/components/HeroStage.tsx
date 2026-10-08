"use client";

import { useEffect, useRef } from "react";

import { clock, spokenShare, type Board } from "@/lib/timeline";

import { useCall } from "./CallContext";
import { PauseIcon, PlayIcon, ReplayIcon } from "./icons";
import { PenCircle } from "./Strips";

const LINES = ["Bank calls, answered", "on one MacBook Air."];

// The first viewport: the claim in type that fills the screen, the recorded call between its two
// lines as the 3D stage, and a deck that plays it, says who is speaking, and times each wait.
export function HeroStage() {
  return (
    <section id="top" aria-label="Tellerline, and a recorded call you can play" className="relative flex min-h-[calc(100svh-var(--header-h))] flex-col overflow-x-clip px-[var(--gutter)] pb-5 pt-[clamp(1.25rem,3vw,2.5rem)]">
      <Title />
      <Sculpture />
      <Deck />
    </section>
  );
}

// Each letter rises into place once; then, as the page scrolls, the two lines drift apart.
function Title() {
  const lines = useRef<(HTMLSpanElement | null)[]>([]);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const update = () => {
      const y = Math.min(window.scrollY, window.innerHeight * 1.2);
      lines.current.forEach((line, index) => {
        if (line) line.style.transform = `translate3d(${(index ? 1 : -1) * y * 0.22}px, 0, 0)`;
      });
      frame = 0;
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);
  let index = 0;
  return (
    <h1 className="callsign relative z-10 text-[clamp(2.4rem,9.4vw,11.5rem)] leading-[0.86]">
      {LINES.map((line, number) => (
        <span
          key={line}
          ref={(element) => {
            lines.current[number] = element;
          }}
          className={`block whitespace-nowrap will-change-transform ${number ? "text-right" : ""}`}
        >
          <span className="sr-only">{line}</span>
          <span aria-hidden="true" className="inline-block overflow-hidden pb-[0.04em] align-bottom">
            {[...line].map((letter) => (
              <span key={index} className="rise inline-block" style={{ "--i": index++ } as React.CSSProperties}>
                {letter === " " ? " " : letter}
              </span>
            ))}
          </span>
        </span>
      ))}
    </h1>
  );
}

// The stage's slot: the scene draws the call here; a click plays it from that moment. The strip
// board's waveform below is the keyboard way to do the same.
function Sculpture() {
  const { call, seek, toggle, playing } = useCall();
  return (
    <div
      data-stage-slot="hero"
      title="Play from here"
      className="relative -mt-[7vw] min-h-[32svh] flex-1 cursor-pointer sm:-mt-[5.5vw] sm:min-h-[38svh]"
      onClick={(event) => {
        const box = event.currentTarget.getBoundingClientRect();
        const span = box.width * 0.96;
        const share = (event.clientX - (box.left + (box.width - span) / 2)) / span;
        seek(Math.min(1, Math.max(0, share)) * call.duration_s);
        if (!playing) void toggle();
      }}
    />
  );
}

function Deck() {
  const { calls, call, board, now, playing, started, finished, loading, toggle, choose } = useCall();
  const label = playing ? "Pause" : finished ? "Play it again" : started ? "Resume" : "Play the call";
  return (
    <div className="relative z-10 grid items-end gap-x-8 gap-y-5 border-t-2 border-ink pt-4 lg:grid-cols-[auto_minmax(0,1fr)_auto]">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" data-primary="" className="key min-h-[3.4rem] w-[15.5rem] justify-start px-6 text-[1.05rem]" onClick={() => void toggle()} aria-keyshortcuts="Space">
          {playing ? <PauseIcon /> : finished ? <ReplayIcon /> : <PlayIcon />}
          {label}
          {!started ? <span className="text-[0.78rem] font-medium text-[#c3cad2]">with sound</span> : null}
        </button>
        <div role="group" aria-label="Recorded calls" className="flex gap-1.5">
          {calls.map((item, number) => {
            const selected = item.slug === call.slug;
            return (
              <button
                key={item.slug}
                type="button"
                aria-pressed={selected}
                aria-label={`Call ${number + 1}: ${item.title}`}
                title={item.title}
                onClick={() => void choose(item.slug)}
                className={`print grid h-[3.4rem] w-11 cursor-pointer place-items-center rounded-[6px] text-[1rem] font-semibold transition-colors duration-150 ${
                  selected ? "bg-amber text-ink" : "bg-strip text-ink-2 shadow-[var(--lift)] hover:bg-well"
                } ${loading === item.slug ? "animate-pulse" : ""}`}
              >
                {number + 1}
              </button>
            );
          })}
        </div>
      </div>
      <Caption board={board} now={now} started={started} summary={call.summary} title={call.title} />
      <div className="flex items-end justify-between gap-6 lg:flex-col lg:items-end lg:gap-2">
        <Wait board={board} now={now} playing={playing} />
        <span className="print whitespace-nowrap text-[0.9rem] font-medium" aria-hidden="true">
          {clock(now)}
          <span className="text-ink-3"> / {clock(call.duration_s)}</span>
        </span>
      </div>
      <p className="sr-only" aria-live="polite">
        {playing ? `Playing ${call.title}` : ""}
      </p>
    </div>
  );
}

// Who is speaking now, printed in step with their voice.
function Caption({ board, now, started, summary, title }: { board: Board; now: number; started: boolean; summary: string; title: string }) {
  let who: "caller" | "agent" | null = null;
  let text = "";
  if (started) {
    const lines: { who: "caller" | "agent"; spans: [number, number][]; text: string }[] = [];
    if (board.greeting) lines.push({ who: "agent", spans: board.greeting.spans, text: board.greeting.text });
    for (const strip of board.strips) {
      lines.push({ who: "caller", spans: strip.caller.spans, text: strip.caller.text });
      if (strip.reply) lines.push({ who: "agent", spans: strip.reply.spans, text: strip.reply.text });
    }
    const current = [...lines].reverse().find((line) => line.spans.length && now >= line.spans[0][0] - 0.05);
    if (current) {
      who = current.who;
      text = current.text.slice(0, Math.round(spokenShare(current.spans, now) * current.text.length));
    }
  }
  return (
    <div className="min-h-[5.2rem] min-w-0" aria-hidden={started ? "true" : undefined}>
      {who ? (
        <>
          <span className={`label block ${who === "caller" ? "text-amber-ink" : "text-blue-ink"}`}>{who === "caller" ? "the caller" : "Tellerline"}</span>
          <p className="mt-1 line-clamp-2 text-[clamp(1.05rem,0.9rem+0.6vw,1.45rem)] font-medium leading-snug">{text}</p>
        </>
      ) : (
        <>
          <span className="label block">call: {title}</span>
          <p className="mt-1 max-w-[60ch] text-[1.02rem] leading-snug text-ink-2">
            {summary} A synthetic caller, and every word from Tellerline generated live on the Mac.
          </p>
        </>
      )}
    </div>
  );
}

// The wait the project measures: counting while the caller waits, circled in red as the reply
// starts, in ink once the next turn begins.
function Wait({ board, now, playing }: { board: Board; now: number; playing: boolean }) {
  const reached = [...board.strips].reverse().find((item) => item.wait && now >= item.wait.from);
  const first = board.strips.find((item) => item.wait);
  // At rest, the first reply's wait, measured, in grey until the call is played.
  const resting = !reached;
  const strip = reached ?? first;
  const wait = strip?.wait ?? null;
  const answered = wait ? resting || now >= wait.until : false;
  const next = strip ? board.strips.find((item) => item.turn === strip.turn + 1) : undefined;
  const live = !resting && playing && answered && (!next || now < next.feedAt);
  const value = wait ? (resting ? wait.until - wait.from : Math.min(now, wait.until) - wait.from) : null;
  return (
    <div className="flex min-w-[10.5rem] flex-col items-start pl-4 lg:items-end lg:pl-0">
      <span className="label whitespace-nowrap">{strip ? `turn ${strip.turn} waited` : "the wait"}</span>
      <span className={`print relative mr-5 mt-1 text-[2.2rem] font-semibold leading-none sm:text-[2.6rem] ${live ? "text-red-ink" : resting ? "text-ink-3" : ""}`}>
        {value === null ? "" : value.toFixed(2)}
        <span className="text-[0.45em] font-normal">&nbsp;s</span>
        {answered ? <PenCircle settled={!live} instant={false} key={strip?.turn} /> : null}
      </span>
    </div>
  );
}
