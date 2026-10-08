"use client";

import { clock, spokenShare, type Board } from "@/lib/timeline";

import { useCall } from "./CallContext";
import { PauseIcon, PlayIcon, ReplayIcon } from "./icons";
import { PenCircle } from "./Strips";
import { Orb } from "./Orb";

const LINES = [["Bank", "calls,", "answered"], ["on", "one", "MacBook", "Air."]];

// The first viewport: pick up. The claim, the call as a ring of light that moves with the
// recorded voices, and the deck that plays it, says who is speaking and times each wait.
export function HeroStage() {
  return (
    <section id="top" aria-label="Tellerline, and a recorded call you can play" className="relative overflow-x-clip px-[var(--gutter)] pb-12 pt-[clamp(1.25rem,2.4vw,2.25rem)]">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="drift-a absolute -left-[10vw] top-[8%] h-[38rem] w-[38rem] rounded-full bg-[radial-gradient(closest-side,rgb(79_227_200/0.16),transparent)]" />
        <div className="drift-b absolute -right-[8vw] top-[28%] h-[40rem] w-[40rem] rounded-full bg-[radial-gradient(closest-side,rgb(255_107_139/0.16),transparent)]" />
      </div>
      <div className="mx-auto flex max-w-[90rem] flex-col items-center text-center">
        <p className="label inline-flex items-center gap-2 rounded-full border border-rail bg-white/5 px-3.5 py-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-amber shadow-[0_0_10px_var(--color-amber)]" aria-hidden="true" />
          Incoming call · answered on one MacBook Air M5
        </p>
        <Title />
        <Stage />
        <div className="-mt-[clamp(0.5rem,2vw,1.5rem)] w-full">
          <Deck />
        </div>
      </div>
    </section>
  );
}

// The orb is a button too, for anyone with a pointer: press it to play or pause the call.
function Stage() {
  const { toggle, playing, started } = useCall();
  return (
    <div className="relative mt-1 w-[clamp(14rem,min(40svh,80vw),28rem)]" onClick={() => void toggle()} title={playing ? "Pause" : "Play the call"}>
      <Orb />
      {!started ? (
        <span className="label pointer-events-none absolute inset-x-0 -top-5 text-center opacity-80" aria-hidden="true">
          press the orb, or space
        </span>
      ) : null}
    </div>
  );
}

// Each word rises into place once, a beat apart; the last two take the voices' light.
function Title() {
  let index = 0;
  return (
    <h1 className="callsign mt-7 text-[clamp(2.5rem,6.6vw,6.6rem)]">
      <span className="sr-only">Bank calls, answered on one MacBook Air.</span>
      <span aria-hidden="true" className="block">
        {LINES.map((line, row) => (
          <span key={row} className="block">
            {line.map((word) => {
              const lit = row === 1 && (word === "MacBook" || word === "Air.");
              return (
                <span key={word + index} className="mr-[0.22em] inline-block overflow-hidden pb-[0.1em] align-bottom last:mr-0">
                  <span className={`rise inline-block ${lit ? "voice-text" : ""}`} style={{ "--i": index++ } as React.CSSProperties}>
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

function Deck() {
  const { calls, call, board, now, playing, started, finished, loading, toggle, choose } = useCall();
  const label = playing ? "Pause" : finished ? "Play it again" : started ? "Resume" : "Play the call";
  return (
    <div className="mx-auto flex max-w-[44rem] flex-col items-center gap-6">
      <div className="flex flex-wrap items-center justify-center gap-3">
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
                  selected ? "bg-ink text-board" : "border border-rail bg-white/5 text-ink-2 hover:bg-white/10"
                } ${loading === item.slug ? "animate-pulse" : ""}`}
              >
                {number + 1}
              </button>
            );
          })}
        </div>
      </div>
      <Caption board={board} now={now} started={started} summary={call.summary} title={call.title} />
      <div className="flex flex-col items-center gap-2">
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
    <div className="min-h-[6.2rem] w-full min-w-0" aria-hidden={started ? "true" : undefined}>
      {who ? (
        <>
          <span className={`label block ${who === "caller" ? "text-amber-ink" : "text-blue-ink"}`}>{who === "caller" ? "the caller" : "Tellerline"}</span>
          <p className="mt-1 mx-auto line-clamp-3 max-w-[40ch] text-[clamp(1.2rem,1rem+0.8vw,1.7rem)] font-medium leading-snug tracking-[-0.01em]">{text}</p>
        </>
      ) : (
        <>
          <span className="label block">call: {title}</span>
          <p className="mx-auto mt-2 max-w-[56ch] text-[1.02rem] leading-snug text-ink-2">
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
    <div className="flex min-w-[10.5rem] flex-col items-center">
      <span className="label whitespace-nowrap">{strip ? `turn ${strip.turn} waited` : "the wait"}</span>
      <span className={`print relative mr-5 mt-1 text-[2.2rem] font-semibold leading-none sm:text-[2.6rem] ${live ? "text-red-ink" : resting ? "text-ink-3" : ""}`}>
        {value === null ? "" : value.toFixed(2)}
        <span className="text-[0.45em] font-normal">&nbsp;s</span>
        {answered ? <PenCircle settled={!live} instant={false} key={strip?.turn} /> : null}
      </span>
    </div>
  );
}
