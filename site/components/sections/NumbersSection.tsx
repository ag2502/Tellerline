import { data, percent, seconds } from "@/lib/data";
import { SCALE_S } from "@/lib/timeline";
import type { Accuracy, CallerRun } from "@/lib/types";

import { Cross, Tick } from "../icons";
import { Ruler, Spread, SpreadKey } from "../Scale";
import { Histogram } from "./Histogram";
import { Section, Source } from "./Section";

type Row = { key: string; label: string; note: string; run: CallerRun; muted?: boolean };

export function NumbersSection({ number }: { number: number }) {
  const gate = data.live.gate;
  if (!gate?.latency_s) return null;
  const { p50, p90, p95 } = gate.latency_s;
  const within = p90 <= SCALE_S;
  const phone = data.live.phone;
  const before = data.live.before;
  const rows: Row[] = [
    ...data.live.capacity
      .filter((run) => run.latency_s)
      .map((run) => ({
        key: run.file,
        label: run.concurrency === 1 ? "one call" : `${run.concurrency} calls at once`,
        note: `${run.calls} calls, ${run.measured} replies${run.overlaps ? `, ${run.overlaps} overlaps` : ""}`,
        run,
      })),
    ...(phone?.latency_s
      ? [{ key: "phone", label: "by phone", note: `Asterisk, 8 kHz G.711, ${phone.measured} replies`, run: phone }]
      : []),
    ...(before?.latency_s
      ? [{ key: "before", label: "before this phase", note: `a ${before.turns}-turn pilot, ${before.measured} replies`, run: before, muted: true }]
      : []),
  ];

  return (
    <Section id="numbers" number={number} title="Measured by phoning it, not projected" command="python -m bench.caller --turns 220">
      <div className="grid items-start gap-x-14 gap-y-12 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <div className="flex flex-col gap-6">
          <p className="prose-width text-[1.15rem] leading-relaxed">
            An automated caller rang the agent over WebRTC {gate.calls} times, spoke {gate.turns}{" "}
            turns and timed each reply from its own last word to Tellerline&apos;s first sound. Half
            of the {gate.measured} replies arrived within <strong>{seconds(p50)}</strong>, nine in ten
            within <strong>{seconds(p90)}</strong>.
          </p>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[0.95rem] text-ink-2">
            <span className="flex items-center gap-1.5 font-semibold text-ink">
              {within ? <Tick className="h-5 w-5" /> : <Cross className="h-5 w-5" />}
              {within ? "within target" : "over target"}
            </span>
            The target is nine in ten within {SCALE_S} s
            {within ? "" : `; this run missed it by ${Math.round((p90 - SCALE_S) * 1000)} ms`}.
          </p>
          <p className="prose-width text-[0.95rem] leading-relaxed text-ink-2">
            In {gate.overlaps} more turns Tellerline&apos;s voice started before the caller had
            finished: they carried on after a pause just as a reply began. It stopped within about
            0.4&nbsp;s and answered the whole sentence. These turns are counted apart rather than as
            fast replies.
            {gate.without_reply ? ` ${gate.without_reply} turns got no reply.` : " Every turn got a reply."} The
            slowest one in twenty took longer than {seconds(p95)}.
          </p>
          <Source file={`results/${gate.file}`}>Every turn of this run, with the agent&apos;s own trace</Source>
        </div>

        <Histogram run={gate} />
      </div>

      <div className="mt-20 grid gap-x-14 gap-y-8 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <div>
          <h3 className="headline text-[1.6rem]">Every run, on the same scale</h3>
          <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
            Several automated callers at once on one Mac, the callers themselves running on it
            too; then the same caller dialling in through Asterisk on G.711, the 8 kHz audio of an
            ordinary phone call, answered over Asterisk&apos;s WebSocket channel.
          </p>
          {phone ? (
            <p className="mt-4">
              <Source file={`results/${phone.file}`}>The phone-line run</Source>
            </p>
          ) : null}
        </div>
        <ScaleRows rows={rows} label="Reply times of each run: half within, and nine in ten within" />
      </div>

      <div className="mt-20 grid gap-x-14 gap-y-16 xl:grid-cols-2">
        <AccuracyStrips />
        {data.live.noisy.length ? <Noisy runs={data.live.noisy} /> : null}
      </div>
    </Section>
  );
}

// Runs as parallel strips on one ruler: label, the spread on the scale, the two figures.
function ScaleRows({ rows, label }: { rows: Row[]; label: string }) {
  return (
    <figure aria-label={label} className="flex flex-col gap-3">
      <SpreadKey />
      <ol className="flex flex-col gap-2">
        {rows.map((row) => {
          const spread = row.run.latency_s!;
          return (
            <li key={row.key} className="holder-plain">
              <div className="strip grid grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[9.5rem_minmax(0,1fr)_7.5rem]">
                <div className="box">
                  <span className={`block font-semibold leading-tight ${row.muted ? "text-ink-2" : ""}`}>{row.label}</span>
                  <span className="block text-[0.74rem] leading-snug text-ink-3">{row.note}</span>
                </div>
                <div className="box col-span-2 row-start-2 flex items-center border-l-0 border-t border-rule px-[0.7rem] py-2.5 sm:col-span-1 sm:col-start-2 sm:row-start-1 sm:border-l sm:border-t-0 sm:px-[0.9rem]">
                  <span className="block w-full">
                    <Spread p50={spread.p50} p90={spread.p90} />
                  </span>
                </div>
                <div className="box flex flex-col items-end justify-center text-right">
                  <span className="print text-[0.8rem] text-ink-2">
                    <span className="sr-only">half within </span>
                    {seconds(spread.p50)}
                  </span>
                  <span className={`print text-[0.98rem] font-semibold ${row.muted ? "text-ink-2" : ""}`}>
                    <span className="sr-only">, nine in ten within </span>
                    {seconds(spread.p90)}
                  </span>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      <Ruler className="ml-[calc(10px+0.7rem)] mr-[calc(3px+0.7rem)] sm:ml-[calc(10px+9.5rem+1px+0.9rem)] sm:mr-[calc(3px+7.5rem+0.9rem)]" />
    </figure>
  );
}

function AccuracyStrips() {
  const { holdout, holdout_before, test, dev, counts } = data.accuracy;
  const rows = [
    { name: "held-out, before this phase", run: holdout_before, split: "holdout", muted: true },
    { name: "held-out, now", run: holdout, split: "holdout" },
    { name: "Phase 0 test set, now", run: test, split: "test" },
    { name: "dev set, for tuning only", run: dev, split: "dev" },
  ].filter((row): row is { name: string; run: Accuracy; split: string; muted?: boolean } => Boolean(row.run));
  return (
    <div>
      <h3 className="headline text-[1.6rem]">Getting the action right</h3>
      <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
        Gemma 4 E2B with the router, on caller turns written before any tuning. A turn counts only
        if the right action ran with the right values, or nothing ran when nothing should.
      </p>
      <ol className="mt-6 flex flex-col gap-2">
        {rows.map(({ name, run, split, muted }) => (
          <li key={name} className={muted ? "holder-plain" : "holder-agent"}>
            <dl className="strip grid grid-cols-3 sm:grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(0,1fr))]">
              <div className="box col-span-3 border-b border-rule sm:col-span-1 sm:border-b-0">
                <dt className={`font-semibold leading-tight ${muted ? "text-ink-2" : ""}`}>{name}</dt>
                <dd className="m-0 text-[0.74rem] leading-snug text-ink-3">
                  {counts[split]?.cases} turns, {counts[split]?.dialogues} dialogues
                </dd>
              </div>
              <Figure label="single turns" value={percent(run.single_turn)} muted={muted} />
              <Figure label="dialogue turns" value={percent(run.dialogue_turns)} muted={muted} />
              <Figure label="whole dialogues" value={percent(run.dialogues)} muted={muted} />
            </dl>
          </li>
        ))}
      </ol>
      {holdout ? (
        <p className="mt-5">
          <Source file={`results/${holdout.file}`}>The held-out run, turn by turn</Source>
        </p>
      ) : null}
    </div>
  );
}

function Figure({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="box flex flex-col justify-between gap-1 [&:nth-child(2)]:border-l-0 sm:[&:nth-child(2)]:border-l">
      <dt className="label">{label}</dt>
      <dd className={`print m-0 text-[1.25rem] font-semibold leading-tight ${muted ? "text-ink-2" : ""}`}>{value}</dd>
    </div>
  );
}

function Noisy({ runs }: { runs: CallerRun[] }) {
  return (
    <div>
      <h3 className="headline text-[1.6rem]">Not solved yet: other people talking</h3>
      <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
        The same calls with a conversation and room noise underneath, set against the
        caller&apos;s own speech level. Tellerline listens for the caller&apos;s level, so the room
        no longer holds their turn open, but the other voices still get into what it hears.
        Separating the caller&apos;s voice is the next piece of work.
      </p>
      <ol className="mt-6 flex flex-col gap-2">
        {runs.map((run) => (
          <li key={run.file} className="holder-plain">
            <div className="strip grid grid-cols-[minmax(0,1fr)_auto]">
              <div className="box">
                <span className="block font-semibold leading-tight">
                  room {Math.abs(run.background_db ?? 0)} dB below the caller
                </span>
                <span className="block text-[0.8rem] leading-snug text-ink-2">
                  {run.measured} of {run.turns} turns timed
                  {run.without_reply ? `, ${run.without_reply} unanswered` : ""}
                  {run.overlaps ? `, ${run.overlaps} overlaps` : ""}.{" "}
                  <Source file={`results/${run.file}`}>Run</Source>
                </span>
              </div>
              <div className="box flex flex-col items-end justify-center text-right">
                <span className="label">nine in ten</span>
                <span className="print text-[0.98rem] font-semibold">
                  {run.latency_s ? seconds(run.latency_s.p90) : "not timed"}
                </span>
              </div>
              {run.latency_s ? (
                <div className="col-span-2 border-t border-rule px-[0.7rem] py-2.5">
                  <Spread p50={run.latency_s.p50} p90={run.latency_s.p90} />
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      <Ruler className="ml-[calc(10px+0.7rem)] mr-[calc(3px+0.7rem)] mt-1" />
    </div>
  );
}
