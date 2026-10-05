"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { buildTimeline, clock, type Line, spokenShare } from "@/lib/timeline";
import type { Call, CallSummary } from "@/lib/types";

import { Waveform } from "./Waveform";

type Props = { calls: CallSummary[]; initial: Call };

const WHO = { agent: "TELLERLINE", caller: "CALLER" } as const;

export function CallReplay({ calls, initial }: Props) {
  const [call, setCall] = useState<Call>(initial);
  const [loading, setLoading] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [started, setStarted] = useState(false);
  const [now, setNow] = useState(0);
  const nowRef = useRef(0);
  const audio = useRef<HTMLAudioElement>(null);
  const cache = useRef(new Map<string, Call>([[initial.slug, initial]]));
  const transcript = useRef<HTMLOListElement>(null);
  const stick = useRef(true);
  const timeline = useMemo(() => buildTimeline(call), [call]);

  // The audio element is the clock. React redraws about sixteen times a second while it plays;
  // the waveform reads the same clock every frame.
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
    stick.current = true;
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
    stick.current = true;
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
      setCall(next);
    },
    [call.slug, failed],
  );

  // Keep the newest line in view while the call plays, unless the reader scrolled up.
  useEffect(() => {
    const element = transcript.current;
    if (element && started && stick.current) element.scrollTop = element.scrollHeight;
  }, [now, started]);

  // Space plays or pauses the call when nothing else has the keyboard.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (event.key !== " " || target.closest("button, a, input, textarea, [role=slider]")) return;
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

  const shown = started ? timeline.lines.filter((line) => line.at <= now + 1e-6) : [];
  // Before the call is run, its first exchange is shown dimmed: what each turn will print.
  const firstReply = timeline.lines.find((line) => line.kind === "agent" && line.turn !== null);
  const preview = started || !firstReply ? [] : timeline.lines.filter((line) => line.at <= firstReply.at);
  const finished = started && !playing && now >= call.duration_s - 0.05;
  const runLabel = playing ? "Pause" : finished ? "Run it again" : started ? "Resume" : "Run the call";
  const index = calls.findIndex((item) => item.slug === call.slug);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="pane-title">
        <span>replay</span>
        <span className="after">{call.call_id}</span>
      </div>

      <div role="tablist" aria-label="Recorded calls" className="flex flex-wrap gap-x-5 gap-y-2">
        {calls.map((item, number) => {
          const selected = item.slug === call.slug;
          return (
            <button
              key={item.slug}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls="replay-transcript"
              onClick={() => void choose(item.slug)}
              className={`cursor-pointer px-[0.6ch] py-0.5 text-left uppercase tracking-wide ${
                selected ? "inverse" : "hover:bg-glass"
              }`}
            >
              <span className={selected ? "" : "dim"}>{number + 1}</span> {item.title}
              {loading === item.slug ? <span className="dim"> loading</span> : null}
            </button>
          );
        })}
      </div>

      <p className="dim text-[0.9em] leading-snug">
        {call.summary} Recorded {formatDate(call.recorded_at)} on a MacBook Air M5 with 16 GB. The
        caller is a synthetic voice played into the agent over WebRTC; every word from Tellerline
        was generated live on the Mac.
      </p>

      <Waveform
        caller={call.envelope.caller}
        agent={call.envelope.agent}
        hz={call.envelope_hz}
        duration={call.duration_s}
        gaps={timeline.gaps}
        now={nowRef}
        playing={playing}
        onSeek={seek}
        label={`Position in call ${index + 1}, ${call.title}. Left and right arrows move five seconds.`}
      />

      <div className="flex items-center justify-between gap-4 text-[0.85em]">
        <span className="dim">
          <span className="text-dim">▲</span> caller &nbsp; <span className="text-p1">▼</span>{" "}
          Tellerline &nbsp; <span className="bloom">└┘</span> the wait for a reply
        </span>
      </div>

      <div className="rule" />

      <ol
        id="replay-transcript"
        ref={transcript}
        onScroll={(event) => {
          const element = event.currentTarget;
          stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 24;
        }}
        className="scroll-y min-h-[16rem] flex-1 space-y-1.5 pr-2 lg:min-h-0"
        aria-label="What was said and what the agent did, printed as the call plays"
      >
        {!started ? (
          <li className="dim pb-2">
            Press <span className="text-p1">Run the call</span> to hear it. Each turn prints what
            Parakeet heard, where the router sent it, what Gemma decided, what the bank did and
            how long the caller waited, like this first one:
          </li>
        ) : null}
        {preview.length ? (
          <li className="opacity-45" aria-hidden="true">
            <ol className="space-y-1.5">
              {preview.map((line, position) => (
                <TranscriptLine
                  key={`preview-${call.slug}-${position}`}
                  line={line}
                  now={Number.POSITIVE_INFINITY}
                  playing={false}
                  onSeek={seek}
                />
              ))}
            </ol>
          </li>
        ) : null}
        {shown.map((line, position) => (
          <TranscriptLine key={`${call.slug}-${position}`} line={line} now={now} playing={playing} onSeek={seek} />
        ))}
        {failed ? (
          <li role="alert" className="bloom">
            That call didn't load.{" "}
            <button type="button" className="underline" onClick={() => void choose(failed)}>
              Try again
            </button>
          </li>
        ) : null}
      </ol>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <button
          type="button"
          data-primary={playing ? undefined : ""}
          className="key"
          onClick={() => void toggle()}
          aria-keyshortcuts="Space"
        >
          {playing ? "Pause" : `▶ ${runLabel}`}
        </button>
        <span className="tabular dim" aria-live="off">
          {clock(now)} / {clock(call.duration_s)}
          {buffering && playing ? " loading the audio" : ""}
        </span>
        <details className="text-[0.9em]">
          <summary className="dim underline decoration-after underline-offset-4 hover:text-p1">
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

function TranscriptLine({
  line,
  now,
  playing,
  onSeek,
}: {
  line: Line;
  now: number;
  playing: boolean;
  onSeek: (seconds: number) => void;
}) {
  if (line.kind === "gap") {
    const waiting = now < line.until;
    const seconds = Math.min(now, line.until) - line.at;
    return (
      <li className="grid grid-cols-[1fr] pl-[2ch] sm:grid-cols-[8ch_11ch_1fr] sm:pl-0">
        <span className="hidden sm:block" />
        <span className="hidden sm:block" />
        <span className="bloom tabular">
          {waiting ? "waiting " : "replied after "}
          {seconds.toFixed(2)} s
        </span>
      </li>
    );
  }
  if (line.kind === "stage") {
    const tone =
      line.tone === "action" ? "bloom" : line.tone === "held" ? "text-dim" : "text-p1";
    return (
      <li className="grid grid-cols-[10ch_1fr] gap-x-[1ch] pl-[2ch] text-[0.9em] sm:grid-cols-[8ch_11ch_10ch_1fr_auto] sm:pl-0">
        <span className="hidden sm:block" />
        <span className="hidden sm:block" />
        <span className="dim">{line.label}</span>
        <span className={`${tone} min-w-0 break-words`}>{line.value}</span>
        <span className="after tabular hidden text-right sm:block">
          {line.ms === null ? "" : `${formatMs(line.ms)}`}
        </span>
      </li>
    );
  }
  const share = spokenShare(line.spans, now);
  const visible = line.text.slice(0, Math.round(share * line.text.length));
  const live = playing && share > 0 && share < 1;
  const colour = line.kind === "agent" ? (live ? "bloom" : "text-p1") : "text-dim";
  return (
    <li className="grid grid-cols-[1fr] pt-2 sm:grid-cols-[8ch_11ch_1fr]">
      <button
        type="button"
        onClick={() => onSeek(line.at)}
        className="after tabular hidden cursor-pointer self-start text-left hover:text-p1 sm:block"
        aria-label={`Play from ${clock(line.at)}`}
      >
        {clock(line.at)}
      </button>
      <span className={line.kind === "agent" ? "text-p1" : "dim"}>{WHO[line.kind]}</span>
      <span className={`${colour} min-w-0 break-words`}>
        {visible}
        {live ? <span className="cursor" aria-hidden="true" /> : null}
      </span>
    </li>
  );
}

function WholeCall({ call }: { call: Call }) {
  return (
    <ol className="mt-3 max-w-[70ch] space-y-3">
      <li>
        <span className="dim">Tellerline:</span> {call.greeting}
      </li>
      {call.turns.map((turn) => (
        <li key={turn.turn} className="space-y-1">
          <p>
            <span className="dim">Caller:</span> {turn.heard}
          </p>
          <p className="dim">
            Gemma 4: {turn.model.output.startsWith("ACTION") ? turn.model.output : "a spoken reply"}
            {turn.instead ? `, not run: ${turn.instead}` : ""}
          </p>
          <p>
            <span className="dim">Tellerline:</span> {turn.spoken}
          </p>
        </li>
      ))}
    </ol>
  );
}

function formatMs(ms: number): string {
  return ms < 1 ? "<1 ms" : `${Math.round(ms)} ms`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}
