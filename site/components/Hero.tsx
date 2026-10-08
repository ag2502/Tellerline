import { data, percent, seconds } from "@/lib/data";

import { CountUp } from "./CountUp";

import { FilmIcon, GitHubIcon } from "./icons";
import { REPO } from "./links";

// Under the stage: one sentence, the measured claims as strips, and the two ways on.
export function ProofBand({ film }: { film: boolean }) {
  return (
    <section aria-label="What was measured" className="relative z-10 px-[var(--gutter)] pb-24 pt-10">
      <div className="mx-auto grid max-w-[90rem] gap-x-14 gap-y-10">
        <div className="flex flex-col gap-6" data-reveal-target="">
          <p className="max-w-[34ch] text-[clamp(1.4rem,1.1rem+1.2vw,2.2rem)] font-medium leading-[1.2] tracking-[-0.025em]">
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

// The page's claims, each a number set large: what was measured, and the command that measured it.
function Proof() {
  const gate = data.live.gate?.latency_s;
  const phone = data.live.phone?.latency_s;
  const heldOut = data.accuracy.holdout;
  const lines = [
    gate && { value: seconds(gate.p90), what: "nine in ten replies, over WebRTC", command: "bench.caller --turns 220" },
    phone && { value: seconds(phone.p90), what: "nine in ten replies, by phone", command: "bench.phone --turns 40" },
    heldOut && { value: percent(heldOut.single_turn), what: "of held-out turns handled right", command: "bench.dialogues --split holdout" },
  ].filter(Boolean) as { value: string; what: string; command: string }[];
  if (!lines.length) return null;
  return (
    <ul className="grid gap-3 md:grid-cols-3" aria-label="Measured on the MacBook Air M5" data-reveal-target="">
      {lines.map((line) => (
        <li key={line.command} className="strip flex flex-col justify-between gap-8 p-6">
          <CountUp value={line.value} className="callsign voice-text text-[clamp(2.8rem,2rem+3vw,4.8rem)]" />
          <span>
            <span className="block text-[1rem] font-medium leading-snug">{line.what}</span>
            <code className="mt-1 block text-[0.72rem] text-ink-3 [overflow-wrap:anywhere]">{`python -m ${line.command}`}</code>
          </span>
        </li>
      ))}
    </ul>
  );
}
