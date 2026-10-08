"use client";

import { clock, spokenShare, type Board } from "@/lib/timeline";

import { useCall } from "./CallContext";
import { PauseIcon, PlayIcon, ReplayIcon } from "./icons";
import { PenCircle } from "./Strips";
import { Waveform } from "./Waveform";

const LINES = [["Bank", "calls,", "answered"], ["on", "one", "MacBook", "Air."]];

// The first viewport: the claim in type that fills the width, and under it the recorded call
// as a player that says who is speaking and times each wait.
export function HeroStage() {
  return (
    <section id="top" aria-label="Tellerline, and a recorded call you can play" className="relative px-[var(--gutter)] pb-10 pt-[clamp(2rem,4vw,3.5rem)]">
      <div className="mx-auto max-w-[90rem]">
        <p className="label inline-flex items-center gap-2 rounded-full border border-rail bg-strip px-3 py-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-blue" aria-hidden="true" />
          Every word on one MacBook Air M5, nothing sent to a cloud
        </p>
        <Title />
        <Player />
      </div>
    </section>
  );
}

// Each word rises into place once, a beat apart; the last two take the italic and the accent.
function Title() {
  let index = 0;
  return (
    <h1 className="callsign mt-6 text-[clamp(2.9rem,8.6vw,9rem)]">
      <span className="sr-only">Bank calls, answered on one MacBook Air.</span>
      <span aria-hidden="true" className="block">
        {LINES.map((line, row) => (
          <span key={row} className="block">
            {line.map((word) => {
              const accent = row === 1 && (word === "MacBook" || word === "Air.");
              return (
                <span key={word + index} className="mr-[0.22em] inline-block overflow-hidden pb-[0.08em] align-bottom last:mr-0">
                  <span
                    className={`rise inline-block ${accent ? "serif pr-[0.06em] text-blue-ink" : ""}`}
                    style={{ "--i": index++ } as React.CSSProperties}
                  >
                    {word}
                  </span>
                </span>
              );
            })}
          </span>
        ))}
      </span>
    </h1>
  );
}

// The recorded call as a card: its trace to click or step through, then the deck beneath.
function Player() {
  const { call, board, seek, nowRef, playing } = useCall();
  return (
    <div className="mt-8 rounded-[28px] bg-strip p-4 shadow-[var(--lift-high)] sm:p-7">
      <Waveform
        caller={call.envelope.caller}
        agent={call.envelope.agent}
        hz={call.envelope_hz}
        duration={call.duration_s}
        gaps={board.gaps}
        now={nowRef}
        playing={playing}
        highlight={null}
        onSeek={seek}
        className="h-36 sm:h-52"
        label={`Position in the call, ${call.title}. Left and right arrows move five seconds.`}
      />
      <Deck />
    </div>
  );
}

function Deck() {
  const { calls, call, board, now, playing, started, finished, loading, toggle, choose } = useCall();
  const label = playing ? "Pause" : finished ? "Play it again" : started ? "Resume" : "Play the call";
  return (
    <div className="mt-6 grid items-end gap-x-8 gap-y-5 border-t border-rule pt-6 lg:grid-cols-[auto_minmax(0,1fr)_auto]">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" data-primary="" className="key min-h-[3.4rem] w-[15rem] justify-start px-7 text-[1.05rem]" onClick={() => void toggle()} aria-keyshortcuts="Space">
          {playing ? <PauseIcon /> : finished ? <ReplayIcon /> : <PlayIcon />}
          {label}
          {!started ? <span className="text-[0.78rem] font-normal opacity-60">with sound</span> : null}
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
                className={`print grid h-[3.4rem] w-[3.4rem] cursor-pointer place-items-center rounded-full text-[1rem] font-medium transition-colors duration-150 ${
                  selected ? "bg-ink text-board" : "bg-board text-ink-2 hover:bg-well"
                } ${loading === item.slug ? "animate-pulse" : ""}`}
              >
                {number + 1}
              </button>
            );
          })}
        </div>
      </div>
      <Caption board={board} now={now} started={started} summary={call.summary} title={call.title} />
      <div className="flex flex-row-reverse items-end justify-between gap-6 lg:flex-col lg:items-end lg:gap-2">
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
          <span className={`label block ${who === "caller" ? "text-ink-2" : "text-blue-ink"}`}>{who === "caller" ? "the caller" : "Tellerline"}</span>
          <p className="mt-1 line-clamp-2 text-[clamp(1.05rem,0.9rem+0.6vw,1.45rem)] font-medium leading-snug tracking-[-0.01em]">{text}</p>
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
    <div className="flex min-w-[10.5rem] flex-col items-end">
      <span className="label whitespace-nowrap">{strip ? `turn ${strip.turn} waited` : "the wait"}</span>
      <span className={`print relative mr-5 mt-1 text-[2.2rem] font-semibold leading-none sm:text-[2.6rem] ${live ? "text-red-ink" : resting ? "text-ink-3" : ""}`}>
        {value === null ? "" : value.toFixed(2)}
        <span className="text-[0.45em] font-normal">&nbsp;s</span>
        {answered ? <PenCircle settled={!live} instant={false} key={strip?.turn} /> : null}
      </span>
    </div>
  );
}
