import { data, percent, seconds } from "@/lib/data";
import type { Call, CallSummary } from "@/lib/types";

import { CallReplay } from "./CallReplay";
import { REPO } from "./links";

// The first viewport is a split terminal: the pitch on the right, and on the left a real
// recorded call waiting to be run.
export function Hero({ calls, call, film }: { calls: CallSummary[]; call: Call; film: boolean }) {
  return (
    <section
      id="call"
      aria-label="Tellerline, and a recorded call you can play"
      className="grid min-h-[calc(100dvh-var(--status-h))] grid-cols-1 gap-x-10 gap-y-12 px-[var(--gutter)] pb-12 pt-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:pb-10 lg:pt-10"
    >
      <div className="order-2 flex min-h-0 flex-col lg:order-1 lg:h-[calc(100dvh-var(--status-h)-5rem)] lg:border-r lg:border-scan lg:pr-10">
        <CallReplay calls={calls} initial={call} />
      </div>

      <div className="order-1 flex flex-col justify-center gap-8 lg:order-2">
        <div className="pane-title">
          <span>tellerline</span>
        </div>
        <h1 className="display max-w-[20ch] text-[clamp(2.25rem,1.2rem+3.3vw,3.9rem)]">
          Bank calls, answered on one MacBook Air.
        </h1>
        <p className="max-w-[44ch] text-[1.05em] leading-relaxed text-p1">
          Tellerline verifies callers and handles their banking in British English. Hearing,
          deciding and speaking all run on the Mac.
        </p>
        <Proof />
        <div className="flex flex-wrap gap-4">
          <a className="key" data-primary="" href={REPO}>
            View the code
          </a>
          {film ? (
            <a className="key" href="#film">
              Watch the film
            </a>
          ) : (
            <a className="key" href="#numbers">
              See the numbers
            </a>
          )}
        </div>
        <span className="cursor" aria-hidden="true" />
      </div>
    </section>
  );
}

// The page's claims, as the commands that measured them and what they printed.
function Proof() {
  const gate = data.live.gate?.latency_s;
  const phone = data.live.phone?.latency_s;
  const heldOut = data.accuracy.holdout;
  const lines = [
    gate && ["bench.caller --turns 220", `nine in ten replies within ${seconds(gate.p90)}`],
    phone && ["bench.phone --turns 40", `by phone, nine in ten within ${seconds(phone.p90)}`],
    heldOut && ["bench.dialogues --split holdout", `${percent(heldOut.single_turn)} of held-out turns right`],
  ].filter(Boolean) as [string, string][];
  if (!lines.length) return null;
  return (
    <dl className="space-y-2.5 text-[0.95em]" aria-label="Measured on the MacBook Air M5">
      {lines.map(([command, result]) => (
        <div key={command}>
          <dt className="dim">
            <span aria-hidden="true">$ </span>python -m {command}
          </dt>
          <dd className="bloom m-0 pl-[2ch]">{result}</dd>
        </div>
      ))}
    </dl>
  );
}
