import { Fragment } from "react";

import { data, percent, seconds } from "@/lib/data";

import { FilmIcon, GitHubIcon } from "./icons";
import { REPO } from "./links";

// Under the stage: one sentence, the measured claims as strips, and the two ways on.
export function ProofBand({ film }: { film: boolean }) {
  return (
    <section aria-label="What was measured" className="relative z-10 px-[var(--gutter)] pb-20 pt-14">
      <div className="mx-auto grid max-w-[90rem] items-start gap-x-14 gap-y-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)]">
        <div className="flex flex-col gap-6" data-reveal-target="">
          <p className="max-w-[40ch] text-[1.2rem] leading-relaxed">
            Tellerline verifies callers and handles their banking in British English. Hearing,
            deciding and speaking all run on the Mac; nothing leaves it.
          </p>
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
        <Proof />
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
    <ul className="grid gap-2 md:grid-cols-3" aria-label="Measured on the MacBook Air M5" data-reveal-target="">
      {lines.map((line) => (
        <li key={line.command} className="holder-plain">
          <div className="strip grid h-full grid-cols-[6.25rem_1fr] items-center md:grid-cols-1 md:items-start">
            <span className="box label">{line.what}</span>
            <span className="box md:border-l-0 md:border-t md:border-rule">
              <span className="block text-[0.98rem] font-semibold">{line.result}</span>
              <code className="block text-[0.72rem] text-ink-3">
                  {`python -m ${line.command}`.split(" ").map((word, index) => (
                    <Fragment key={index}>
                      {index ? " " : ""}
                      <span className="whitespace-nowrap">{word}</span>
                    </Fragment>
                  ))}
                </code>
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
