import { data, ms, seconds } from "@/lib/data";
import { onScale } from "@/lib/timeline";

import { Flag, Ruler } from "../Scale";
import { FactStrip, Section, Source } from "./Section";

type Stage = { name: string; what: string; value: number | null; side: "hear" | "decide" };

export function TurnSection({ number }: { number: number }) {
  const gate = data.live.gate;
  const stage = (key: string) => gate?.stages_ms[key]?.p50 ?? null;
  const stages: Stage[] = [
    { name: "silence", what: "Silero VAD waits for 200 ms of quiet", value: stage("endpointing_wait"), side: "hear" },
    { name: "end of turn", what: "Smart Turn v3.2 judges the caller has finished", value: stage("turn_detection"), side: "hear" },
    { name: "transcript", what: "Parakeet TDT 0.6B v3 transcribes the turn on the GPU", value: stage("stt_ms"), side: "hear" },
    { name: "exact", what: "code writes digits, euro amounts and dates exactly", value: null, side: "hear" },
    { name: "route", what: "bge-small picks one focused skill, on the CPU", value: data.router?.latency_p90_ms ?? null, side: "decide" },
    { name: "decide", what: "Gemma 4 E2B answers, or writes one ACTION line", value: stage("model_ms"), side: "decide" },
    { name: "check", what: "code checks every value against what the caller said", value: null, side: "decide" },
    { name: "bank", what: "the mock core bank runs the action", value: stage("bank_ms"), side: "decide" },
    { name: "speak", what: "Kokoro starts the reply; fixed openings are cached", value: stage("speech_synthesis"), side: "decide" },
  ];
  const timed = stages.filter((item) => item.value !== null);
  const total = timed.reduce((sum, item) => sum + (item.value ?? 0), 0) / 1000;
  const example = data.examples.find((item) => item.case === "h-dispute-yesterday");
  const latency = gate?.latency_s;

  return (
    <Section id="turn" number={number} title="One turn, from the caller's last word to the reply" command="python -m tellerline.agent.traces --last 1">
      <div className="grid gap-x-14 gap-y-16 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div>
          <p className="prose-width mb-8 text-[1.05rem] leading-relaxed text-ink-2">
            Medians from the agent&apos;s own record of each turn in the latest gate run
            {gate ? ` (${gate.measured} turns)` : ""}, laid out on one scale: each box is as long as
            the stage took. Everything runs on the Mac; nothing leaves it.
          </p>

          {/* The one scale, 0 to 1.5 s, with the turn's stages as boxes of their real length. */}
          <figure aria-label={`The stages of one turn add up to about ${seconds(total)}`}>
            <div className="holder-turn">
              <div className="strip px-3 pb-2 pt-[3.75rem] sm:px-4">
                <div className="scale-ticks relative h-14 rounded-[2px] bg-[#f3f5f7]">
                  <div className="absolute inset-y-2 left-0 flex" style={{ width: `${onScale(total) * 100}%` }}>
                    {timed.map((item) => (
                      <div
                        key={item.name}
                        title={`${item.name}: ${ms(item.value ?? 0)}`}
                        className={`h-full min-w-[3px] border-r-2 border-strip first:rounded-l-[2px] last:rounded-r-[2px] last:border-r-0 ${
                          item.side === "hear" ? "bg-amber" : "bg-blue"
                        }`}
                        style={{ width: `${((item.value ?? 0) / 1000 / total) * 100}%` }}
                      />
                    ))}
                  </div>
                  {latency ? (
                    <>
                      <Flag at={latency.p50} label={`half heard it by ${seconds(latency.p50)}`} />
                      <Flag at={latency.p90} label={`nine in ten by ${seconds(latency.p90)}`} row={1} />
                    </>
                  ) : null}
                </div>
                <Ruler />
              </div>
            </div>
            <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[0.82rem] text-ink-2">
              <span className="flex items-center gap-2">
                <i className="inline-block h-3 w-3 rounded-[2px] bg-amber" aria-hidden="true" /> hearing the caller
              </span>
              <span className="flex items-center gap-2">
                <i className="inline-block h-3 w-3 rounded-[2px] bg-blue" aria-hidden="true" /> deciding and answering
              </span>
            </figcaption>
          </figure>

          <ol className="mt-8 grid gap-x-8 gap-y-3 sm:grid-cols-2" aria-label="The stages of one turn">
            {stages.map((item) => (
              <li key={item.name} className="grid grid-cols-[0.85rem_1fr_auto] items-baseline gap-x-2.5">
                <i
                  className={`inline-block h-2.5 w-2.5 translate-y-[1px] rounded-[2px] ${
                    item.value === null ? "border border-ink-3 bg-transparent" : item.side === "hear" ? "bg-amber" : "bg-blue"
                  }`}
                  aria-hidden="true"
                />
                <span>
                  <span className="font-semibold">{item.name}</span>
                  <span className="block text-[0.86rem] leading-snug text-ink-2">{item.what}</span>
                </span>
                <span className="print text-[0.85rem] text-ink-2">{item.value === null ? "code" : ms(item.value)}</span>
              </li>
            ))}
          </ol>
          {latency ? (
            <p className="prose-width mt-8 text-[0.95rem] leading-relaxed text-ink-2">
              The stages add up to about <strong className="text-ink">{seconds(total)}</strong>; the
              caller hears the reply within <strong className="text-ink">{seconds(latency.p50)}</strong> half
              the time and <strong className="text-ink">{seconds(latency.p90)}</strong> nine times in ten. The
              rest is the audio&apos;s trip through WebRTC in both directions and the hand-offs between
              stages.
            </p>
          ) : null}
          <p className="mt-5">{gate ? <Source file={`results/${gate.file}`}>Every turn of that run</Source> : null}</p>
        </div>

        {example ? (
          <figure className="flex flex-col gap-3">
            <figcaption className="prose-width mb-2 text-[1.05rem] leading-relaxed text-ink-2">
              One held-out turn. Speech recognition writes what it hears; code makes it exact before
              the model reads it, so Gemma never has to do the arithmetic.
            </figcaption>
            <FactStrip label="heard" holder="caller">
              <span>&ldquo;{example.said}&rdquo;</span>
            </FactStrip>
            <FactStrip label="exact" holder="caller">
              <span className="font-semibold">&ldquo;{example.understood}&rdquo;</span>
            </FactStrip>
            <FactStrip label="Gemma wrote" holder="agent">
              <code className="font-semibold text-blue-ink">{example.after}</code>
              <span className="mt-1.5 block text-[0.82rem] text-ink-2">
                before this phase: <s className="decoration-ink-2">{example.before}</s>, the cents lost
              </span>
            </FactStrip>
            <FactStrip label="caller hears" holder="agent">
              <span>{example.heard_reply}</span>
            </FactStrip>
          </figure>
        ) : null}
      </div>
    </Section>
  );
}
