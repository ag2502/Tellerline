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
