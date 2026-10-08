import { data, percent, seconds } from "@/lib/data";
import type { Call, CallSummary } from "@/lib/types";

import { CallBoard } from "./CallBoard";
import { FilmIcon, GitHubIcon } from "./icons";
import { REPO } from "./links";

// The first viewport: the claim on the left, and the call's strip board filling the rest,
// waiting on Play.
export function Hero({ calls, call, film }: { calls: CallSummary[]; call: Call; film: boolean }) {
  return (
    <section id="call" aria-label="Tellerline, and a recorded call you can play" className="px-[var(--gutter)] pb-20 pt-8 lg:pb-24 lg:pt-12">
      <div className="mx-auto grid max-w-[90rem] gap-x-14 gap-y-12 lg:grid-cols-[minmax(0,0.82fr)_minmax(0,1.55fr)]">
        <div className="flex flex-col gap-7 lg:pt-4">
          <h1 className="callsign text-[clamp(2.5rem,1.2rem+4.5vw,4.5rem)] lg:text-[clamp(2.2rem,4vw-0.4rem,3.2rem)]">
            Bank calls, answered
            <br />
            on one MacBook&nbsp;Air.
          </h1>
          <p className="max-w-[40ch] text-[1.12rem] leading-relaxed text-ink-2">
            Tellerline verifies callers and handles their banking in British English. Hearing,
            deciding and speaking all run on the Mac. Play a real call and watch each turn print.
          </p>
          <Proof />
          <div className="flex flex-wrap gap-3">
            <a className="key" data-primary="" href={REPO}>
              <GitHubIcon />
              View the code
            </a>
            {film ? (
              <a className="key" href="#film">
                <FilmIcon />
                Watch the film
              </a>
            ) : (
              <a className="key" href="#numbers">
                See the numbers
              </a>
            )}
          </div>
        </div>

        <CallBoard calls={calls} initial={call} />
      </div>
    </section>
  );
}

// The page's claims, each as a strip: what was measured, the command that measured it, and what
// it printed.
function Proof() {
  const gate = data.live.gate?.latency_s;
  const phone = data.live.phone?.latency_s;
  const heldOut = data.accuracy.holdout;
  const lines = [
    gate && { what: "over WebRTC", command: "bench.caller --turns 220", result: `nine in ten replies within ${seconds(gate.p90)}` },
    phone && { what: "by phone", command: "bench.phone --turns 40", result: `nine in ten within ${seconds(phone.p90)}` },
    heldOut && {
      what: "held-out turns",
      command: "bench.dialogues --split holdout",
      result: `${percent(heldOut.single_turn)} handled right`,
    },
  ].filter(Boolean) as { what: string; command: string; result: string }[];
  if (!lines.length) return null;
  return (
    <ul className="flex flex-col gap-2" aria-label="Measured on the MacBook Air M5">
      {lines.map((line) => (
        <li key={line.command} className="holder-plain">
          <div className="strip grid grid-cols-[6.25rem_1fr] items-center">
            <span className="box label">{line.what}</span>
            <span className="box">
              <span className="block text-[0.98rem] font-semibold">{line.result}</span>
              <code className="block truncate text-[0.72rem] text-ink-3">python -m {line.command}</code>
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
