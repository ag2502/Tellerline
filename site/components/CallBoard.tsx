"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { type Board, buildBoard, clock, type Span } from "@/lib/timeline";
import type { Call, CallSummary } from "@/lib/types";

import { PauseIcon, PlayIcon, ReplayIcon } from "./icons";
import { REPO } from "./links";
import { Greeting, Strip } from "./Strips";
import { Waveform } from "./Waveform";

type Props = { calls: CallSummary[]; initial: Call };

const SECTIONS = ["call", "turn", "numbers", "policy", "memory", "log", "film", "run"];
const HELP = "run [call] · pause · calls · goto <bay> · clone · github · clear";
const FEED_MS = 420;
const SNAP = "cubic-bezier(0.3, 1.45, 0.55, 1)";

// With reduced motion, strips and lines print whole the moment they're reached, and nothing moves.
function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

export function CallBoard({ calls, initial }: Props) {
  const reducedMotion = useReducedMotion();
  const [call, setCall] = useState<Call>(initial);
  const [loading, setLoading] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [started, setStarted] = useState(false);
  const [now, setNow] = useState(0);
  const [pulled, setPulled] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const nowRef = useRef(0);
  const audio = useRef<HTMLAudioElement>(null);
  const cache = useRef(new Map<string, Call>([[initial.slug, initial]]));
  const bay = useRef<HTMLOListElement>(null);
  const board = useMemo(() => buildBoard(call), [call]);

  // The audio element is the board's one clock. React redraws about sixteen times a second while
  // it plays; the waveform reads the same clock every frame. Pause it and every strip freezes.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last = 0;
    const tick = (time: number) => {
      if (audio.current) nowRef.current = audio.current.currentTime;
      if (time - last > 60) {
        last = time;
        setNow(nowRef.current);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  const toggle = useCallback(async () => {
    const element = audio.current;
    if (!element) return;
    if (!element.paused) {
      element.pause();
      return;
    }
    if (element.ended || element.currentTime >= call.duration_s - 0.05) {
      element.currentTime = 0;
      nowRef.current = 0;
      setNow(0);
    }
    setStarted(true);
    try {
      await element.play();
    } catch {
      setPlaying(false);
    }
  }, [call.duration_s]);

  const seek = useCallback((seconds: number) => {
    const element = audio.current;
    if (!element) return;
    element.currentTime = seconds;
    nowRef.current = seconds;
    setNow(seconds);
    setStarted(true);
  }, []);

  const choose = useCallback(
    async (slug: string) => {
      if (slug === call.slug && !failed) return;
      audio.current?.pause();
      setFailed(null);
      let next = cache.current.get(slug);
      if (!next) {
        setLoading(slug);
        try {
          const response = await fetch(`/calls/${slug}.json`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          next = (await response.json()) as Call;
          cache.current.set(slug, next);
        } catch {
          setFailed(slug);
          setLoading(null);
          return;
        }
        setLoading(null);
      }
      nowRef.current = 0;
      setNow(0);
      setStarted(false);
      setPlaying(false);
      setPulled(null);
      setCall(next);
    },
    [call.slug, failed],
  );

  // `run 2` (or `run dispute`) picks a call; it starts playing once that call has loaded.
  const pendingPlay = useRef(false);
  useEffect(() => {
    if (pendingPlay.current) {
      pendingPlay.current = false;
      void toggle();
    }
  }, [call, toggle]);

  const execute = useCallback(
    async (input: string): Promise<string> => {
      const [verb = "", ...rest] = input.trim().toLowerCase().split(/\s+/);
      const argument = rest.join(" ");
      const section = (name: string) => {
        const id = SECTIONS.find((item) => item === name);
        if (!id || !document.getElementById(id)) return `no bay called ${name}. Bays: ${SECTIONS.join(" ")}`;
        document.getElementById(id)?.scrollIntoView({ block: "start" });
        return `to ${id}`;
      };
      switch (verb) {
        case "help":
        case "?":
          return HELP;
        case "calls":
        case "ls":
          return calls.map((item, number) => `${number + 1} ${item.title}`).join(" · ");
        case "run":
        case "play": {
          if (!argument) {
            if (audio.current?.paused) await toggle();
            return `playing ${call.title}`;
          }
          const number = Number(argument);
          const target = Number.isInteger(number)
            ? calls[number - 1]
            : calls.find((item) => item.slug === argument || item.title === argument || item.slug.startsWith(argument));
          if (!target) return `no call called ${argument}. Try calls.`;
          if (target.slug === call.slug) {
            if (audio.current?.paused) await toggle();
          } else {
            pendingPlay.current = true;
            await choose(target.slug);
          }
          return `playing ${target.title}`;
        }
        case "pause":
        case "stop":
          audio.current?.pause();
          return "paused";
        case "goto":
        case "cd":
          return section(argument);
        case "clone":
          try {
            await navigator.clipboard.writeText(`git clone ${REPO}.git`);
            return `copied: git clone ${REPO}.git`;
          } catch {
            return `git clone ${REPO}.git`;
          }
        case "github":
        case "open":
          window.open(REPO, "_blank", "noopener");
          return "opening github.com/ag2502/Tellerline";
        case "clear":
          return "";
        default:
          return SECTIONS.includes(verb) ? section(verb) : `command not found: ${verb}. Try help.`;
      }
    },
    [call.slug, call.title, calls, choose, toggle],
  );

  // Space plays or pauses the call when nothing else has the keyboard and the board is in view.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (event.key !== " " || target.closest("button, a, input, textarea, summary, [role=slider]")) return;
      const pane = document.getElementById("call");
      if (!pane) return;
      const rect = pane.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) return;
      event.preventDefault();
      void toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  // Strips in the bay, newest at the top: those whose caller has started speaking.
  const fed = started ? board.strips.filter((strip) => strip.feedAt <= now + 1e-6) : [];
  const visible = [...fed].reverse();
  const live = playing && fed.length ? fed[fed.length - 1].turn : null;
  const finished = started && !playing && now >= call.duration_s - 0.05;
  const index = calls.findIndex((item) => item.slug === call.slug);

  // Nothing glides: when a strip feeds in at the top, the strips below snap down one step.
  const items = useRef(new Map<number, HTMLLIElement>());
  const tops = useRef(new Map<number, number>());
  useLayoutEffect(() => {
    for (const [key, element] of items.current) {
      const top = element.offsetTop;
      const before = tops.current.get(key);
      if (!reducedMotion && before !== undefined && Math.abs(before - top) > 1) {
        element.animate([{ transform: `translateY(${before - top}px)` }, { transform: "translateY(0)" }], {
          duration: FEED_MS,
          easing: SNAP,
        });
      }
      tops.current.set(key, top);
    }
  }, [fed.length, pulled, reducedMotion]);

  // A new strip feeds in at the top of the bay: keep the top in view unless the reader scrolled.
  const stuck = useRef(true);
  useEffect(() => {
    if (bay.current && stuck.current) bay.current.scrollTop = 0;
  }, [fed.length]);

  const highlight: Span | null = useMemo(() => {
    const strip = board.strips.find((item) => item.turn === (hovered ?? pulled));
    if (!strip) return null;
    return [strip.feedAt, strip.reply ? strip.reply.spans[strip.reply.spans.length - 1][1] : strip.caller.end];
  }, [board, hovered, pulled]);

  const playLabel = playing ? "Pause" : finished ? "Play it again" : started ? "Resume" : "Play the call";

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div role="tablist" aria-label="Recorded calls" className="flex flex-wrap gap-2">
        {calls.map((item, number) => {
          const selected = item.slug === call.slug;
          return (
            <button
              key={item.slug}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls="call-bay"
              onClick={() => void choose(item.slug)}
              className={`flex cursor-pointer items-center gap-2 rounded-[5px] py-1.5 pl-1.5 pr-3 text-[0.82rem] font-semibold uppercase tracking-[0.06em] transition-colors duration-150 ${
                selected
                  ? "bg-ink text-strip shadow-[0_2px_0_#000]"
                  : "bg-strip text-ink shadow-[var(--lift)] hover:bg-[#f5f6f7]"
              }`}
            >
              <span
                className={`print grid h-6 w-6 place-items-center rounded-[3px] text-[0.78rem] ${
                  selected ? "bg-amber text-ink" : "bg-well text-ink-2"
                }`}
              >
                {number + 1}
              </span>
              {item.title}
              {loading === item.slug ? <span className="text-ink-3 normal-case tracking-normal"> loading</span> : null}
            </button>
          );
        })}
      </div>

      {/* The call's own strip: who, how, when, and the whole call as a printed trace. */}
      <div className="holder-agent">
        <div className="strip px-4 pb-3 pt-3 sm:px-5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p className="callsign text-[1.35rem] sm:text-[1.6rem]">
              {call.title}
              <span className="print ml-3 align-middle text-[0.72rem] font-normal normal-case tracking-normal text-ink-3">
                {call.call_id}
              </span>
            </p>
            <p className="print text-[1.05rem] font-medium tabular" aria-live="off">
              {clock(now)}
              <span className="text-ink-3"> / {clock(call.duration_s)}</span>
            </p>
          </div>
          <p className="mt-1 text-[0.92rem] leading-snug text-ink-2">
            {call.summary}{" "}
            <span className="text-ink-3">
              Recorded {formatDate(call.recorded_at)} on a MacBook Air M5 with 16 GB: a synthetic caller
              over WebRTC, and every word from Tellerline generated live.
            </span>
          </p>
          <div className="mt-3">
            <Waveform
              caller={call.envelope.caller}
              agent={call.envelope.agent}
              hz={call.envelope_hz}
              duration={call.duration_s}
              gaps={board.gaps}
              now={nowRef}
              playing={playing}
              highlight={highlight}
              onSeek={seek}
              label={`Position in call ${index + 1}, ${call.title}. Left and right arrows move five seconds.`}
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-3">
            <button
              type="button"
              data-primary=""
              className="key min-w-[11.5rem]"
              onClick={() => void toggle()}
              aria-keyshortcuts="Space"
            >
              {playing ? <PauseIcon /> : finished ? <ReplayIcon /> : <PlayIcon />}
              {playLabel}
            </button>
            <Legend />
            {buffering && playing ? <span className="text-[0.85rem] text-ink-3">loading the audio</span> : null}
          </div>
        </div>
      </div>

      <ol
        id="call-bay"
        ref={bay}
        onScroll={(event) => {
          stuck.current = event.currentTarget.scrollTop < 24;
        }}
        className="well relative flex flex-col gap-2.5 p-2.5 [scrollbar-width:thin] sm:max-h-[31rem] sm:overflow-y-auto sm:p-3"
        aria-label="The call as strips, newest at the top: what the caller said, what the agent heard, routed, decided and did, and how long the caller waited"
      >
        {!started ? <Waiting board={board} onPlay={() => void toggle()} /> : null}
        {visible.map((strip) => (
          <li
            key={`${call.slug}-${strip.turn}`}
            ref={(element) => {
              if (element) items.current.set(strip.turn, element);
              else items.current.delete(strip.turn);
            }}
            className={reducedMotion ? "" : "feed"}
          >
            <Strip
              strip={strip}
              now={now}
              live={live === strip.turn}
              instant={reducedMotion}
              pulled={pulled === strip.turn}
              onPull={() => setPulled((current) => (current === strip.turn ? null : strip.turn))}
              onSeek={seek}
              onHover={(on) => setHovered(on ? strip.turn : null)}
            />
          </li>
        ))}
        {board.greeting && (started ? now >= board.greeting.at : true) ? (
          <li>
            <Greeting greeting={board.greeting} now={started ? now : Number.POSITIVE_INFINITY} instant={reducedMotion} />
          </li>
        ) : null}
        {failed ? (
          <li role="alert" className="strip px-4 py-3 font-semibold text-ink">
            That call didn&apos;t load.{" "}
            <button type="button" className="font-semibold underline" onClick={() => void choose(failed)}>
              Try again
            </button>
          </li>
        ) : null}
      </ol>

      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <CommandLine execute={execute} />
        <details className="text-[0.9rem]">
          <summary className="font-medium text-ink-2 underline decoration-rail underline-offset-4 hover:text-ink">
            Read the whole call
          </summary>
          <WholeCall call={call} />
        </details>
      </div>

      <audio
        ref={audio}
        src={call.audio}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          nowRef.current = call.duration_s;
          setNow(call.duration_s);
        }}
        onWaiting={() => setBuffering(true)}
        onPlaying={() => setBuffering(false)}
      />
    </div>
  );
}

function Legend() {
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.8rem] text-ink-2" aria-hidden="true">
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
  );
}

// Before the call is played: the greeting is printed, and the first turn shows, muted, what each
// strip will print.
function Waiting({ board, onPlay }: { board: Board; onPlay: () => void }) {
  const first = board.strips[0];
  return (
    <>
      <li className="px-1 pb-1 pt-0.5 text-[0.92rem] text-ink-2">
        <button type="button" onClick={onPlay} className="font-semibold text-ink underline decoration-rail underline-offset-4 hover:decoration-ink">
          Play the call
        </button>{" "}
        and each turn feeds a strip in here as it happens: what the caller said, what the agent
        heard, where it routed, what it decided, what the bank did, and how long the caller waited,
        timed at the agent, with the caller&apos;s own timing, WebRTC both ways, beneath it. The first
        one looks like this:
      </li>
      {first ? (
        <li className="opacity-55" aria-hidden="true">
          <Strip strip={first} now={Number.POSITIVE_INFINITY} live={false} instant pulled={false} preview />
        </li>
      ) : null}
    </>
  );
}

// A prompt that takes real commands: play a call, jump to a bay, copy the clone command.
function CommandLine({ execute }: { execute: (input: string) => Promise<string> }) {
  const [value, setValue] = useState("");
  const [history, setHistory] = useState<{ input: string; output: string }[]>([]);
  return (
    <form
      className="min-w-0 flex-1 basis-[18rem] text-[0.88rem]"
      onSubmit={async (event) => {
        event.preventDefault();
        const input = value.trim();
        if (!input) return;
        setValue("");
        const output = await execute(input);
        setHistory((lines) => (input.toLowerCase() === "clear" ? [] : [...lines, { input, output }].slice(-2)));
      }}
    >
      <ol aria-live="polite" className="mb-1.5 space-y-0.5">
        {history.map((line, index) => (
          <li key={index} className="print text-[0.8rem]">
            <span className="text-ink-3">› {line.input}</span>
            {line.output ? <span className="block pl-[1.6ch] text-ink-2">{line.output}</span> : null}
          </li>
        ))}
      </ol>
      <label htmlFor="replay-prompt" className="label mb-1 block">
        Type a command
      </label>
      <div className="flex items-center gap-2 rounded-[6px] bg-strip px-3 shadow-[var(--lift)] focus-within:shadow-[0_0_0_2px_var(--color-blue)]">
        <span className="print text-ink-3" aria-hidden="true">
          ›
        </span>
        <input
          id="replay-prompt"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="help · run 3 · goto numbers"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="print min-h-[2.5rem] min-w-0 flex-1 bg-transparent text-[0.86rem] placeholder:text-ink-3 focus:outline-none"
        />
      </div>
    </form>
  );
}

function WholeCall({ call }: { call: Call }) {
  return (
    <ol className="mt-3 max-w-[66ch] space-y-3 text-[0.92rem]">
      <li>
        <span className="font-semibold text-blue-ink">Tellerline:</span> {call.greeting}
      </li>
      {call.turns.map((turn) => (
        <li key={turn.turn} className="space-y-1">
          <p>
            <span className="font-semibold text-amber-ink">Caller:</span> {turn.said ?? turn.heard}
          </p>
          {turn.said && turn.said !== turn.heard ? <p className="text-ink-2">Parakeet heard: {turn.heard}</p> : null}
          <p className="text-ink-2">
            Gemma 4: {turn.model.output.startsWith("ACTION") ? turn.model.output : "a spoken reply"}
            {turn.instead ? `, not run: ${turn.instead}` : ""}
          </p>
          <p>
            <span className="font-semibold text-blue-ink">Tellerline:</span> {turn.spoken}
          </p>
        </li>
      ))}
    </ol>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}
