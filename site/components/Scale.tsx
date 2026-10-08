import { onScale, SCALE_S } from "@/lib/timeline";

import { ArrowIcon } from "./icons";

// The page's one scale: every timing sits on the same ruled 0 to 1.5 s, the target at its end.

const TICKS = [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5];

// The scale's printed figures. Where the scale is short the quarter marks drop out.
export function Ruler({ className = "" }: { className?: string }) {
  return (
    <div className={`print @container relative h-8 text-[0.68rem] leading-none text-ink-3 ${className}`} aria-hidden="true">
      {TICKS.map((value) => {
        const end = value === SCALE_S;
        return (
          <span
            key={value}
            className={`absolute top-1.5 whitespace-nowrap ${value === 0 ? "" : end ? "-translate-x-full" : "-translate-x-1/2"} ${
              value % 0.5 ? "hidden @min-[24rem]:inline" : ""
            }`}
            style={{ left: `${onScale(value) * 100}%` }}
          >
            {end ? (
              <span className="flex flex-col items-end gap-1">
                <span>{SCALE_S} s</span>
                <span>target</span>
              </span>
            ) : (
              value
            )}
          </span>
        );
      })}
    </div>
  );
}

// A flag on the scale: a hairline at the value, its label printed to the left of it. Two rows
// keep neighbouring flags apart.
export function Flag({ at, label, row = 0 }: { at: number; label: string; row?: 0 | 1 }) {
  return (
    <span
      className={`pointer-events-none absolute bottom-0 w-0 ${row ? "-top-11" : "-top-6"}`}
      style={{ left: `${onScale(at) * 100}%` }}
      aria-hidden="true"
    >
      <span className="print absolute right-2 top-0 whitespace-nowrap text-[0.7rem] leading-none text-ink">{label}</span>
      <span className="absolute bottom-0 left-[-1px] top-0 w-[2px] bg-ink" />
    </span>
  );
}

// A run's spread on the scale: solid to the median, hatched on to nine in ten, and an arrow when
// nine in ten runs past the end.
export function Spread({ p50, p90 }: { p50: number; p90: number }) {
  const over = p90 > SCALE_S;
  return (
    <span className="scale-ticks relative block h-6 rounded-[2px] bg-well" aria-hidden="true">
      <span className="absolute inset-y-1.5 left-0 rounded-l-[2px] bg-blue" style={{ width: `${onScale(p50) * 100}%` }} />
      <span
        className="hatch absolute inset-y-1.5"
        style={{ left: `${onScale(p50) * 100}%`, width: `${(onScale(p90) - onScale(p50)) * 100}%` }}
      />
      {over ? (
        <ArrowIcon className="absolute -right-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink" />
      ) : (
        <span className="absolute inset-y-0.5 w-[2px] bg-ink" style={{ left: `calc(${onScale(p90) * 100}% - 1px)` }} />
      )}
    </span>
  );
}

// What the two marks of a spread mean, said once above the strips that use them.
export function SpreadKey() {
  return (
    <p className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[0.82rem] text-ink-2" aria-hidden="true">
      <span className="flex items-center gap-2">
        <i className="inline-block h-3 w-6 rounded-[1px] bg-blue" /> half the replies within
      </span>
      <span className="flex items-center gap-2">
        <i className="hatch inline-block h-3 w-6 rounded-[1px]" /> nine in ten within
      </span>
      <span className="flex items-center gap-2">
        <ArrowIcon className="h-3.5 w-3.5 text-ink" /> past the end of the scale
      </span>
    </p>
  );
}
