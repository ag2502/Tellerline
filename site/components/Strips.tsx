"use client";

import { clock, onScale, SCALE_S, spokenShare, type Board, type TurnStrip } from "@/lib/timeline";

import { ArrowIcon } from "./icons";

// The strips the board is made of, shared by the replay and the film: a turn's strip with its
// boxes, the wait circled in pen, and the trace a pulled strip shows.

export function Greeting({ greeting, now, instant }: { greeting: NonNullable<Board["greeting"]>; now: number; instant: boolean }) {
  const share = spokenShare(greeting.spans, now);
  const shown = instant && share > 0 ? 1 : share;
  return (
    <div className="holder-agent">
      <div className="strip grid grid-cols-[4.75rem_1fr] sm:grid-cols-[5.5rem_1fr]">
        <div className="box">
          <span className="label block">greeting</span>
          <span className="print text-[1.05rem]">{clock(greeting.at).slice(0, 5)}</span>
        </div>
        <div className="box">
          <span className="label block text-blue-ink">Tellerline</span>
          <span>{greeting.text.slice(0, Math.round(shown * greeting.text.length))}</span>
        </div>
      </div>
    </div>
  );
}

export type StripProps = {
  strip: TurnStrip;
  now: number;
  live: boolean;
  instant: boolean;
  pulled: boolean;
  preview?: boolean;
  onPull?: () => void;
  onSeek?: (seconds: number) => void;
  onHover?: (on: boolean) => void;
  // The film draws the pen by its own clock rather than by a CSS animation: 0 to 1.
  pen?: number;
};

// One turn, as a flight strip: when, what the caller said, the stages as they printed, what
// Tellerline said, and the wait, circled in red pen while it's the live turn.
export function Strip({ strip, now, live, instant, pulled, preview = false, onPull, onSeek, onHover, pen }: StripProps) {
  const callerShare = spokenShare(strip.caller.spans, now);
  const callerShown = instant && callerShare > 0 ? 1 : callerShare;
  const callerText = strip.caller.text.slice(0, Math.round(callerShown * strip.caller.text.length));
  const printed = strip.stages.filter((stage) => stage.at <= now + 1e-6);
  const byKey = new Map(printed.map((stage) => [stage.key, stage]));
  const replyShare = strip.reply ? spokenShare(strip.reply.spans, now) : 0;
  const replyShown = instant && replyShare > 0 ? 1 : replyShare;
  const replyText = strip.reply ? strip.reply.text.slice(0, Math.round(replyShown * strip.reply.text.length)) : "";
  const answered = strip.wait ? now >= strip.wait.until : false;
  const waiting = strip.wait && now >= strip.wait.from && !answered;
  const waitSeconds = strip.wait ? Math.min(now, strip.wait.until) - strip.wait.from : 0;
  const decided = byKey.get("decided");
  const held = byKey.get("held");
  const bank = byKey.get("bank");

  return (
    <div
      className={`holder-turn transition-[transform,box-shadow] duration-200 ${pulled ? "-translate-y-0.5 shadow-[var(--lift-high)]" : ""}`}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
    >
      <div className="strip grid grid-cols-[4.75rem_1fr] grid-rows-[auto_auto] sm:grid-cols-[5.5rem_1fr_9.75rem] sm:grid-rows-1">
        {/* When: click to play the call from this turn. */}
        <div className="box flex flex-col gap-0.5 border-b border-rule sm:border-b-0">
          <span className="label">turn {strip.turn}</span>
          {preview || !onSeek ? (
            <span className="print text-[1.05rem]">{clock(strip.feedAt).slice(0, 5)}</span>
          ) : (
            <button
              type="button"
              onClick={() => onSeek(strip.feedAt)}
              className="print w-fit cursor-pointer text-left text-[1.05rem] underline decoration-rail decoration-1 underline-offset-[5px] hover:decoration-ink"
              aria-label={`Play from ${clock(strip.feedAt)}`}
            >
              {clock(strip.feedAt).slice(0, 5)}
            </button>
          )}
        </div>

        {/* The wait, on the board's one scale. On phones it sits beside the time. */}
        <div className="box col-start-2 row-start-1 border-b border-rule sm:col-start-3 sm:border-b-0">
          <WaitBox strip={strip} now={now} answered={answered} waiting={Boolean(waiting)} seconds={waitSeconds} live={live} instant={instant} pen={pen} />
        </div>

        <div className="col-span-2 min-w-0 sm:col-span-1 sm:col-start-2 sm:row-start-1 sm:border-l sm:border-rule">
          <div className="relative px-3 pb-2 pt-2 sm:px-4">
            <span className="label block text-amber-ink">caller said</span>
            <p className="min-h-[1.55em] text-[0.98rem] leading-snug">{callerText}</p>
            {strip.carriedOn && byKey.has("carried") ? (
              <span className="absolute right-3 top-2 -rotate-2 rounded-[3px] border-[1.5px] border-current px-1.5 text-[0.68rem] font-bold uppercase tracking-[0.08em] text-ink-2">
                one turn
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-2 border-t border-rule sm:grid-cols-[1.1fr_0.9fr_1.5fr_0.8fr]">
            <StageBox label="heard" stage={byKey.get("heard")} value={(stage) => `“${stage.value}”`} />
            <StageBox label="routed" stage={byKey.get("routed")} value={(stage) => stage.value.split(",")[0]} />
            <StageBox
              label="decided"
              stage={decided}
              value={(stage) => stage.value}
              action={decided?.tone === "action"}
              className="border-t border-rule sm:border-t-0"
            />
            {held ? (
              <StageBox label="held back" stage={held} value={(stage) => stage.value} className="border-t border-rule sm:border-t-0" />
            ) : (
              <StageBox label="bank" stage={bank} value={(stage) => stage.value} empty={printed.length > 2 && !strip.raw.bank} className="border-t border-rule sm:border-t-0" />
            )}
          </div>
          <div className="border-t border-rule px-3 pb-2.5 pt-2 sm:px-4">
            <span className="label block text-blue-ink">Tellerline said</span>
            <p className="min-h-[1.55em] text-[0.98rem] leading-snug">{replyText}</p>
          </div>
          {pulled ? <Trace strip={strip} /> : null}
          {onPull && !preview ? (
            <div className="flex justify-end border-t border-rule">
              <button
                type="button"
                onClick={onPull}
                aria-expanded={pulled}
                className="flex cursor-pointer items-center gap-1.5 px-3 py-1.5 text-[0.78rem] font-semibold uppercase tracking-[0.08em] text-ink-2 hover:text-ink"
              >
                {pulled ? "Put back" : "Pull the trace"}
                <ArrowIcon className={`h-3.5 w-3.5 transition-transform duration-200 ${pulled ? "-rotate-90" : "rotate-90"}`} />
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function StageBox({
  label,
  stage,
  value,
  action = false,
  empty = false,
  className = "",
}: {
  label: string;
  stage: TurnStrip["stages"][number] | undefined;
  value: (stage: TurnStrip["stages"][number]) => string;
  action?: boolean;
  empty?: boolean;
  className?: string;
}) {
  return (
    <div className={`box min-h-[3.4rem] [&:nth-child(odd)]:border-l-0 sm:[&:nth-child(odd)]:border-l sm:first:border-l-0 ${className}`}>
      <span className="flex items-baseline justify-between gap-2">
        <span className="label">{label}</span>
        {stage?.ms != null ? <span className="print text-[0.7rem] text-ink-3">{formatMs(stage.ms)}</span> : null}
      </span>
      {stage ? (
        <span
          className={`print-in block truncate text-[0.84rem] ${action ? "print font-semibold text-blue-ink" : ""}`}
          title={value(stage)}
        >
          {value(stage)}
        </span>
      ) : (
        <span className="block text-[0.84rem] text-ink-3" aria-hidden="true">
          {empty ? "none" : " "}
        </span>
      )}
    </div>
  );
}

// The wait box: counting while the caller waits, then circled in red pen when Tellerline answers.
function WaitBox({
  strip,
  now,
  answered,
  waiting,
  seconds,
  live,
  instant,
  pen,
}: {
  strip: TurnStrip;
  now: number;
  answered: boolean;
  waiting: boolean;
  seconds: number;
  live: boolean;
  instant: boolean;
  pen?: number;
}) {
  if (!strip.wait) {
    const overlap = strip.reply && now >= strip.reply.at;
    return (
      <div className="flex h-full flex-col justify-between gap-1">
        <span className="label">wait</span>
        <span className="text-[0.82rem] leading-snug text-ink-2">
          {overlap ? "answered over the caller's pause" : " "}
        </span>
      </div>
    );
  }
  const total = strip.wait.until - strip.wait.from;
  return (
    <div className="flex h-full flex-col gap-1">
      <span className="label">wait</span>
      <span className="relative w-fit">
        <span className={`print text-[1.35rem] font-semibold leading-none sm:text-[1.5rem] ${live && answered ? "text-red-ink" : ""}`}>
          {answered ? total.toFixed(2) : waiting ? seconds.toFixed(2) : "  "}
          <span className="text-[0.7em] font-normal">{answered || waiting ? " s" : ""}</span>
        </span>
        {answered ? <PenCircle settled={!live} instant={instant} progress={pen} /> : null}
      </span>
      {answered && strip.wait.callerWait !== null ? (
        <span className="text-[0.74rem] leading-tight text-ink-2">
          {strip.wait.callerWait.toFixed(2)} s for the caller
        </span>
      ) : null}
      <MiniScale wait={answered ? total : waiting ? seconds : 0} callerWait={answered ? strip.wait.callerWait : null} />
    </div>
  );
}

// The board's one scale, 0 to 1.5 s: the wait at the agent in blue, the caller's own timing ticked.
function MiniScale({ wait, callerWait }: { wait: number; callerWait: number | null }) {
  return (
    <span className="mt-auto block pt-1" aria-hidden="true">
      <span className="relative block h-2 rounded-[1px] bg-well">
        <span className="absolute inset-y-0 left-0 rounded-[1px] bg-blue" style={{ width: `${onScale(wait) * 100}%` }} />
        {callerWait !== null ? (
          <span className="absolute -inset-y-0.5 w-[2px] bg-ink" style={{ left: `calc(${onScale(callerWait) * 100}% - 1px)` }} />
        ) : null}
      </span>
      <span className="print mt-0.5 flex justify-between text-[0.62rem] text-ink-3">
        <span>0</span>
        <span>{SCALE_S} s</span>
      </span>
    </span>
  );
}

// A loop of red pen round a figure, drawn once, then left; ink once the turn is no longer live.
export function PenCircle({
  settled,
  instant,
  progress,
  weight = 2.25,
}: {
  settled: boolean;
  instant: boolean;
  progress?: number;
  weight?: number;
}) {
  return (
    <svg
      className="pointer-events-none absolute -inset-x-2.5 -inset-y-2 h-[calc(100%+1rem)] w-[calc(100%+1.25rem)] overflow-visible"
      viewBox="0 0 100 40"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        className="pen"
        data-settled={settled ? "" : undefined}
        data-draw={instant ? undefined : ""}
        pathLength={100}
        style={
          progress === undefined
            ? ({ "--length": 100, strokeWidth: weight } as React.CSSProperties)
            : { strokeWidth: weight, strokeDasharray: 100, strokeDashoffset: 100 * (1 - Math.min(1, Math.max(0, progress))) }
        }
        d="M64 4C40 1 10 5 5 17c-4 10 13 19 41 19 27 0 49-6 50-17C97 8 78 3 56 4c-6 0-11 1-15 2"
      />
    </svg>
  );
}

// Pulled off the board: everything the agent recorded for this turn.
function Trace({ strip }: { strip: TurnStrip }) {
  const turn = strip.raw;
  const rows: [string, string][] = [
    ["caller said", strip.caller.text],
    ["Parakeet heard", turn.heard],
  ];
  if (turn.understood && turn.understood !== turn.heard) rows.push(["made exact", turn.understood]);
  rows.push(["routed", `${turn.route.skill} skill: ${turn.route.reason}${turn.route.score === null ? "" : `, score ${turn.route.score.toFixed(2)}`} (${formatMs(turn.route.ms)})`]);
  rows.push(["Gemma 4 wrote", `${turn.model.output.trim()} (first token ${turn.model.first_token_ms === null ? "–" : formatMs(turn.model.first_token_ms)}, ${formatMs(turn.model.ms)} in all)`]);
  if (turn.instead) rows.push(["held back", turn.instead]);
  if (turn.bank) rows.push(["bank", `${turn.bank.outcome} (${formatMs(turn.bank.ms)})`]);
  if (strip.carriedOn) rows.push(["one turn", "The caller carried on after a pause before a reply began; the agent dropped that reply unheard and answered both parts together."]);
  if (turn.reply_s != null) rows.push(["reply at the agent", `${turn.reply_s.toFixed(2)} s from the caller's last word to Tellerline's first sound`]);
  return (
    <dl className="grid gap-x-4 gap-y-2 border-t border-rule bg-[#fbfbfc] px-3 py-3 text-[0.86rem] sm:grid-cols-[9rem_1fr] sm:px-4">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="label pt-0.5">{label}</dt>
          <dd className={`m-0 min-w-0 break-words ${label === "Gemma 4 wrote" ? "print" : ""}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function formatMs(ms: number): string {
  return ms < 1 ? "<1 ms" : `${Math.round(ms)} ms`;
}
