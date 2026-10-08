"use client";

import { useState } from "react";

import { seconds } from "@/lib/format";
import { onScale, SCALE_S } from "@/lib/timeline";
import type { CallerRun } from "@/lib/types";

import { Flag, Ruler } from "../Scale";

const BIN_S = 0.1;

type Column = { key: string; from: number; count: number; label: string };

// Every timed reply of the gate as one mark, stacked by how long the caller waited, on the page's
// one scale. Replies past the target share the column beyond its end.
export function Histogram({ run }: { run: CallerRun }) {
  const [active, setActive] = useState<string | null>(null);
  const spread = run.latency_s!;
  const columns: Column[] = run.histogram
    .filter((bin) => bin.from < SCALE_S - 1e-9 && bin.count)
    .map((bin) => ({
      key: bin.from.toFixed(1),
      from: bin.from,
      count: bin.count,
      label: `${bin.from.toFixed(1)} to ${(bin.from + BIN_S).toFixed(1)} s`,
    }));
  const over = run.histogram.filter((bin) => bin.from >= SCALE_S - 1e-9).reduce((sum, bin) => sum + bin.count, 0);
  const tallest = Math.max(over, ...columns.map((column) => column.count));
  const shown = columns.find((column) => column.key === active);
  const readout = shown
    ? `${shown.label}: ${shown.count} ${shown.count === 1 ? "reply" : "replies"}`
    : active === "over"
      ? `past ${SCALE_S} s: ${over} ${over === 1 ? "reply" : "replies"}, the longest ${seconds(spread.max)}`
      : `${run.measured} replies, one mark each. Point at a column to read it.`;

  return (
    <figure className="holder-plain">
      <div className="strip px-4 pb-4 pt-3.5 sm:px-5">
        <figcaption className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <span className="label">replies by the caller&apos;s wait</span>
          <span className="print min-h-[1.2em] text-[0.78rem] text-ink-2" aria-hidden="true">
            {readout}
          </span>
        </figcaption>

        <div className="mt-14 flex items-stretch" onMouseLeave={() => setActive(null)} aria-hidden="true">
          <div className="relative flex-1" style={{ height: `${tallest * 4 + 4}px` }}>
            {columns.map((column) => (
              <Marks
                key={column.key}
                count={column.count}
                left={onScale(column.from)}
                width={BIN_S / SCALE_S}
                active={active === column.key}
                onEnter={() => setActive(column.key)}
              />
            ))}
            <Flag at={spread.p50} label={`half by ${seconds(spread.p50)}`} />
            <Flag at={spread.p90} label={`nine in ten by ${seconds(spread.p90)}`} row={1} />
          </div>
          {/* The target: the end of the scale. What waited longer sits beyond it. */}
          <div className="relative w-11 border-l-2 border-dashed border-ink sm:w-14">
            {over ? <Marks count={over} left={0} width={1} active={active === "over"} onEnter={() => setActive("over")} muted /> : null}
          </div>
        </div>
        <div className="flex">
          <Ruler className="flex-1" />
          <span className="print w-11 pl-2 pt-1.5 text-[0.68rem] leading-none text-ink-3 sm:w-14" aria-hidden="true">
            longer
          </span>
        </div>

        <Counts run={run} />
      </div>
    </figure>
  );
}

// One column of marks, a mark per reply, with a hit area the full height of the chart.
function Marks({
  count,
  left,
  width,
  active,
  muted = false,
  onEnter,
}: {
  count: number;
  left: number;
  width: number;
  active: boolean;
  muted?: boolean;
  onEnter: () => void;
}) {
  return (
    <span
      className={`absolute inset-y-0 flex flex-col-reverse gap-px px-[2px] ${active ? "bg-well" : ""}`}
      style={{ left: `${left * 100}%`, width: `${width * 100}%` }}
      onMouseEnter={onEnter}
    >
      {Array.from({ length: count }, (_, index) => (
        <i
          key={index}
          className={`block h-[3px] shrink-0 rounded-[1px] ${muted ? "bg-ink-3" : active ? "bg-blue-ink" : "bg-blue"}`}
        />
      ))}
    </span>
  );
}

// The gate's replies by wait, tenth by tenth, behind a disclosure.
export function Counts({ run }: { run: CallerRun }) {
  const columns = run.histogram
    .filter((bin) => bin.from < SCALE_S - 1e-9 && bin.count)
    .map((bin) => ({ key: bin.from.toFixed(1), count: bin.count, label: `${bin.from.toFixed(1)} to ${(bin.from + BIN_S).toFixed(1)} s` }));
  const over = run.histogram.filter((bin) => bin.from >= SCALE_S - 1e-9).reduce((sum, bin) => sum + bin.count, 0);
  return (
    <details className="mt-3 text-[0.85rem]">
      <summary className="w-fit font-medium text-ink-2 underline decoration-rail underline-offset-4 hover:text-ink">
        The counts
      </summary>
      <table className="print mt-2 w-full max-w-[22rem] border-collapse text-[0.8rem]">
        <caption className="sr-only">Replies by the caller&apos;s wait, in tenths of a second</caption>
        <thead>
          <tr className="text-left text-ink-3">
            <th scope="col" className="pb-1 font-normal">wait</th>
            <th scope="col" className="pb-1 text-right font-normal">replies</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((column) => (
            <tr key={column.key} className="border-t border-rule">
              <th scope="row" className="py-0.5 text-left font-normal">
                {column.label}
              </th>
              <td className="text-right">{column.count}</td>
            </tr>
          ))}
          <tr className="border-t border-rule">
            <th scope="row" className="py-0.5 text-left font-normal">
              past {SCALE_S} s
            </th>
            <td className="text-right">{over}</td>
          </tr>
        </tbody>
      </table>
    </details>
  );
}
