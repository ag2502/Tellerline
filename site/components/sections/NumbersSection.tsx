import { Fragment } from "react";

import { data, percent, seconds } from "@/lib/data";
import type { CallerRun } from "@/lib/types";

import { Section, Source } from "./Section";

const TARGET_S = 1.5;
const HISTOGRAM_CAP_S = 2.0; // longer replies share the last row
const BAR_WIDTH = 34; // blocks in the longest bar
const BAR_WIDTH_NARROW = 14; // on a phone

export function NumbersSection() {
  const gate = data.live.gate;
  if (!gate?.latency_s) return null;
  const { p50, p90, p95 } = gate.latency_s;
  const within = p90 <= TARGET_S;

  return (
    <Section id="numbers" title="Measured by phoning it, not projected" command="python -m bench.caller --turns 220">
      <div className="grid gap-16 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-8">
          <p className="max-w-[60ch] text-[1.1em] leading-relaxed">
            An automated caller rang the agent over WebRTC {gate.calls} times, spoke{" "}
            {gate.turns} turns and timed each reply from its own last word to Tellerline&apos;s
            first sound. Half of the {gate.measured} replies arrived within{" "}
            <span className="bloom">{seconds(p50)}</span>, nine in ten within{" "}
            <span className="bloom">{seconds(p90)}</span>.
          </p>
          <p className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
            <span className="inverse px-[1ch] py-0.5 uppercase tracking-wide">
              {within ? "within target" : "over target"}
            </span>
            <span className="dim">
              The target is nine in ten within {TARGET_S} s
              {within ? "" : `; this run missed it by ${Math.round((p90 - TARGET_S) * 1000)} ms`}.
            </span>
          </p>
          <Histogram run={gate} />
          <p className="dim max-w-[62ch] text-[0.95em]">
            In {gate.overlaps} more turns Tellerline started talking before the caller had finished
            (it answered at a pause mid-sentence). They are counted apart rather than as fast
            replies; earlier runs of this benchmark counted them as replies of 20 to 200 ms.
            {gate.without_reply ? ` ${gate.without_reply} turns got no reply.` : ""} p95{" "}
            {seconds(p95)}.
          </p>
          <Source file={`results/${gate.file}`}>Every turn of this run, with the agent&apos;s own trace</Source>
        </div>

        <div className="space-y-14">
          <Capacity runs={data.live.capacity} />
          {data.live.phone?.latency_s ? <Phone run={data.live.phone} /> : null}
          <Accuracy />
          {data.live.noisy?.latency_s ? <Noisy run={data.live.noisy} /> : null}
        </div>
      </div>
    </Section>
  );
}

function Histogram({ run }: { run: CallerRun }) {
  const rows: { label: string; from: number; count: number }[] = [];
  let over = 0;
  for (const bin of run.histogram) {
    if (bin.from >= HISTOGRAM_CAP_S) over += bin.count;
    else rows.push({ label: `${bin.from.toFixed(1)} s`, from: bin.from, count: bin.count });
  }
  if (over) rows.push({ label: `${HISTOGRAM_CAP_S.toFixed(1)} s+`, from: HISTOGRAM_CAP_S, count: over });
  const most = Math.max(...rows.map((row) => row.count));
  const { p50, p90 } = run.latency_s!;
  const marks = (from: number) => {
    const found = [];
    if (p50 >= from && p50 < from + 0.1) found.push("median");
    if (p90 >= from && p90 < from + 0.1) found.push("9 in 10");
    return found.join(", ");
  };

  return (
    <table className="w-full border-collapse text-[0.92em]">
      <caption className="dim mb-3 text-left">
        Replies by how long the caller waited, in tenths of a second
      </caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Wait</th>
          <th scope="col">Replies</th>
          <th scope="col">Marker</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <Fragment key={row.label}>
            {Math.abs(row.from - TARGET_S) < 1e-9 ? (
              <tr aria-hidden="true">
                <td colSpan={3} className="py-1">
                  <span className="after">──── </span>
                  <span className="dim">target {TARGET_S.toFixed(1)} s</span>
                  <span className="after"> ────</span>
                </td>
              </tr>
            ) : null}
            <tr>
              <th
                scope="row"
                className="dim w-[7ch] whitespace-nowrap pr-[1ch] text-left font-normal tabular"
              >
                {row.label}
              </th>
              <td className="whitespace-nowrap">
                <span className={row.from + 0.1 <= TARGET_S + 1e-9 ? "text-p1" : "bloom"} aria-hidden="true">
                  <span className="hidden sm:inline">{bar(row.count, most, BAR_WIDTH)}</span>
                  <span className="sm:hidden">{bar(row.count, most, BAR_WIDTH_NARROW)}</span>
                </span>
                <span className="dim tabular"> {row.count}</span>
              </td>
              <td className="bloom whitespace-nowrap pl-[1ch] text-right">{marks(row.from)}</td>
            </tr>
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

function bar(count: number, most: number, width: number): string {
  return "▬".repeat(Math.max(count ? 1 : 0, Math.round((count / most) * width)));
}

function Capacity({ runs }: { runs: CallerRun[] }) {
  const measured = runs.filter((run) => run.latency_s);
  if (measured.length < 2) return null;
  return (
    <div>
      <h3 className="bloom mb-2">Calls at once</h3>
      <p className="dim mb-4 max-w-[58ch] text-[0.95em]">
        One Mac, several automated callers at the same time, each run timed the same way. The
        callers themselves run on the same Mac.
      </p>
      <table className="w-full border-collapse text-[0.92em] tabular">
        <thead>
          <tr className="dim text-left">
            <th scope="col" className="pb-2 font-normal">calls</th>
            <th scope="col" className="pb-2 font-normal">median</th>
            <th scope="col" className="pb-2 font-normal">9 in 10</th>
            <th scope="col" className="pb-2 font-normal">replies</th>
            <th scope="col" className="pb-2 font-normal">overlaps</th>
          </tr>
        </thead>
        <tbody>
          {measured.map((run) => (
            <tr key={run.file} className="border-t border-scan">
              <td className="py-1.5">{run.concurrency}</td>
              <td>{seconds(run.latency_s!.p50)}</td>
              <td className={run.latency_s!.p90 <= TARGET_S ? "" : "bloom"}>
                {seconds(run.latency_s!.p90)}
              </td>
              <td>{run.measured}</td>
              <td>{run.overlaps}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Accuracy() {
  const { holdout, holdout_before, test, dev, counts } = data.accuracy;
  const rows = [
    { name: "held-out, before this phase", run: holdout_before, split: "holdout" },
    { name: "held-out, now", run: holdout, split: "holdout" },
    { name: "Phase 0 test set, now", run: test, split: "test" },
    { name: "dev set (tuning only)", run: dev, split: "dev" },
  ].filter((row) => row.run);
  return (
    <div>
      <h3 className="bloom mb-2">Getting the action right</h3>
      <p className="dim mb-4 max-w-[58ch] text-[0.95em]">
        Gemma 4 E2B with the router, on caller turns written before any tuning. A turn counts only
        if the right action ran with the right values, or nothing ran when nothing should.
      </p>
      <table className="w-full border-collapse text-[0.92em] tabular">
        <thead>
          <tr className="dim text-left">
            <th scope="col" className="pb-2 font-normal">set</th>
            <th scope="col" className="pb-2 font-normal">single turns</th>
            <th scope="col" className="pb-2 font-normal">dialogue turns</th>
            <th scope="col" className="pb-2 font-normal">whole dialogues</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ name, run, split }) => (
            <tr key={name} className="border-t border-scan">
              <td className="py-1.5 pr-[1ch]">
                {name}
                <span className="dim block text-[0.85em]">
                  {counts[split]?.cases} cases, {counts[split]?.dialogues} dialogues
                </span>
              </td>
              <td>{percent(run!.single_turn)}</td>
              <td>{percent(run!.dialogue_turns)}</td>
              <td>{percent(run!.dialogues)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {holdout ? (
        <p className="mt-3">
          <Source file={`results/${holdout.file}`}>The held-out run, turn by turn</Source>
        </p>
      ) : null}
    </div>
  );
}

function Phone({ run }: { run: CallerRun }) {
  const { p50, p90 } = run.latency_s!;
  return (
    <div>
      <h3 className="bloom mb-2">Over a phone line</h3>
      <p className="max-w-[58ch] text-[0.95em] leading-relaxed">
        The same caller dialled in through Asterisk on G.711, the 8 kHz audio of an ordinary phone
        call, and Tellerline answered over Asterisk&apos;s WebSocket channel. Half of{" "}
        {run.measured} replies arrived within <span className="bloom">{seconds(p50)}</span>, nine
        in ten within <span className="bloom">{seconds(p90)}</span>
        {run.overlaps ? `, with ${run.overlaps} overlaps counted apart` : ""}.
      </p>
      <p className="mt-3">
        <Source file={`results/${run.file}`}>The phone-line run</Source>
      </p>
    </div>
  );
}

function Noisy({ run }: { run: CallerRun }) {
  return (
    <div>
      <h3 className="bloom mb-2">Not solved yet: a noisy room</h3>
      <p className="max-w-[58ch] text-[0.95em] leading-relaxed">
        With a busy room played under the caller at {run.background_db}&nbsp;dB, only{" "}
        {run.measured} of {run.turns} turns got a measured reply, and those took a median of{" "}
        {seconds(run.latency_s!.p50)}. Quiet-room numbers don&apos;t carry over to noise; making
        turn detection hold up in a noisy room is the next piece of work.
      </p>
      <p className="mt-3">
        <Source file={`results/${run.file}`}>The noisy-room run</Source>
      </p>
    </div>
  );
}

