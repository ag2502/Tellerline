"use client";

import { useEffect, useRef, useState } from "react";

import { PlayIcon, ReplayIcon } from "../icons";

export type LabStage = { name: string; what: string; ms: number | null; side: "hear" | "decide" };

// A turn in slow motion: the caller's last word enters on the left and each stage lights as the
// work reaches it, for as long as the stage really takes, slowed down by the speed you pick. The
// clock under it counts the real milliseconds. Stages that are code and not a model take no
// measurable time, so they flash through.
const SPEEDS = [
  { label: "×1", factor: 1 },
  { label: "×4", factor: 4 },
  { label: "×10", factor: 10 },
] as const;
const CODE_MS = 40; // how long a code stage shows for, in real time

export function PipelineLab({ stages, p50, p90 }: { stages: LabStage[]; p50: number | null; p90: number | null }) {
  const [speed, setSpeed] = useState(1);
  const [run, setRun] = useState(0); // 0 = never run; each press starts a fresh run
  const [picked, setPicked] = useState(5);
  const clock = useRef<HTMLSpanElement>(null);
  const factor = SPEEDS[speed].factor;

  const lengths = stages.map((stage) => stage.ms ?? CODE_MS);
  const starts = lengths.reduce<number[]>((all, length, index) => [...all, index ? all[index - 1] + lengths[index - 1] : 0], []);
  const total = lengths.reduce((sum, length) => sum + length, 0);
  const measured = stages.reduce((sum, stage) => sum + (stage.ms ?? 0), 0);

  // The counter reads the real milliseconds elapsed while the stages play out.
  useEffect(() => {
    const element = clock.current;
    if (!element || !run) return;
    let frame = 0;
    const begin = performance.now();
    const tick = (now: number) => {
      const real = Math.min(total, (now - begin) / factor);
      let counted = 0;
      for (let i = 0; i < stages.length; i++) {
        const done = Math.max(0, Math.min(lengths[i], real - starts[i]));
        if (stages[i].ms !== null) counted += done;
      }
      element.textContent = `${Math.round(counted)} ms`;
      if (real < total) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [run, factor, total]); // eslint-disable-line react-hooks/exhaustive-deps

  const chosen = stages[picked];
  return (
    <div className="strip p-4 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" data-primary="" className="key" onClick={() => setRun((count) => count + 1)}>
            {run ? <ReplayIcon /> : <PlayIcon />}
            {run ? "Run it again" : "Run a turn"}
          </button>
          <div role="group" aria-label="Playback speed" className="flex gap-1 rounded-full border border-rail bg-white/5 p-1">
            {SPEEDS.map((item, index) => (
              <button
                key={item.label}
                type="button"
                aria-pressed={speed === index}
                onClick={() => {
                  setSpeed(index);
                  if (run) setRun((count) => count + 1);
                }}
                className={`print cursor-pointer rounded-full px-3 py-1.5 text-[0.8rem] transition-colors ${
                  speed === index ? "bg-ink text-board" : "text-ink-2 hover:text-ink"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <p className="print text-[0.8rem] text-ink-3 sm:text-right">
          <span className="text-[1.6rem] font-semibold leading-none text-ink">
            <span ref={clock}>{run ? "0 ms" : `${Math.round(measured)} ms`}</span>
          </span>
          <span className="block">{run ? "of the Mac's own work, counted live" : "the Mac's own work, median"}</span>
        </p>
      </div>

      {/* The line the work travels along, one cell per stage. */}
      <ol key={run} className="mt-8 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-9 lg:gap-1.5" aria-label="The stages of one turn">
        {stages.map((stage, index) => {
          const side = stage.side === "hear" ? "var(--color-amber)" : "var(--color-blue)";
          const delay = starts[index] * factor;
          const length = lengths[index] * factor;
          const width = stage.ms === null ? 0 : stage.ms;
          return (
            <li key={stage.name}>
              <button
                type="button"
                onClick={() => setPicked(index)}
                aria-pressed={picked === index}
                style={{ "--side": side } as React.CSSProperties}
                className={`group relative flex h-full min-h-[7.5rem] w-full cursor-pointer flex-col justify-between overflow-hidden rounded-2xl border p-3 text-left transition-colors ${
                  picked === index ? "border-[var(--side)] bg-white/[0.07]" : "border-rail bg-white/[0.03] hover:bg-white/[0.06]"
                }`}
              >
                {run ? (
                  <span
                    aria-hidden="true"
                    className="lab-fill absolute inset-0 origin-left bg-[var(--side)]"
                    style={{ animationDelay: `${delay}ms`, animationDuration: `${Math.max(length, 140)}ms` }}
                  />
                ) : null}
                <span className="relative flex items-center gap-1.5">
                  <i className="h-2 w-2 rounded-full bg-[var(--side)]" aria-hidden="true" />
                  <span className="label">{String(index + 1).padStart(2, "0")}</span>
                </span>
                <span className="relative">
                  <span className="block text-[1rem] font-semibold leading-tight">{stage.name}</span>
                  <span className="print mt-1 block text-[0.78rem] text-ink-2">{stage.ms === null ? "code" : `${Math.round(stage.ms)} ms`}</span>
                  {stage.ms !== null ? (
                    <span aria-hidden="true" className="mt-2 block h-1 rounded-full bg-[var(--side)] opacity-70" style={{ width: `${Math.max(8, Math.min(100, (width / 380) * 100))}%` }} />
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <div className="mt-6 grid items-start gap-x-8 gap-y-4 border-t border-rule pt-6 md:grid-cols-[1fr_auto]">
        <p className="min-h-[3.2rem] max-w-[60ch] text-[1rem] leading-relaxed text-ink-2" aria-live="polite">
          <strong className="font-semibold text-ink">{chosen.name}.</strong> {chosen.what}
          {chosen.ms === null ? ". It is code, so it takes no time worth timing." : `, in about ${Math.round(chosen.ms)} ms.`}
        </p>
        {p50 !== null && p90 !== null ? (
          <p className="print text-[0.82rem] leading-snug text-ink-3 md:text-right">
            The caller hears the reply within <span className="text-ink">{p50.toFixed(2)} s</span> half the time,{" "}
            <span className="text-ink">{p90.toFixed(2)} s</span> nine in ten.
            <br />
            The rest is the audio&apos;s trip through WebRTC.
          </p>
        ) : null}
      </div>
    </div>
  );
}
