import { data, ms, seconds } from "@/lib/data";

import { Section, Source } from "./Section";

type Stage = { name: string; what: string; value: number | null; note?: string };

const BAR_MS = 22; // one block per this many milliseconds

export function TurnSection() {
  const gate = data.live.gate;
  const stage = (key: string) => gate?.stages_ms[key]?.p50 ?? null;
  const stages: Stage[] = [
    { name: "silence", what: "Silero VAD waits for 200 ms of quiet", value: stage("endpointing_wait") },
    { name: "end of turn", what: "Smart Turn v3.2 judges the caller has finished", value: stage("turn_detection") },
    { name: "transcript", what: "Parakeet TDT 0.6B v3 transcribes the turn on the GPU", value: stage("stt_ms") },
    { name: "exact", what: "code writes digits, euro amounts and dates exactly", value: null, note: "code" },
    {
      name: "route",
      what: "bge-small picks one focused skill, on the CPU",
      value: data.router?.latency_p90_ms ?? null,
    },
    { name: "decide", what: "Gemma 4 E2B answers, or writes one ACTION line", value: stage("model_ms") },
    { name: "check", what: "code checks every value against what the caller said", value: null, note: "code" },
    { name: "bank", what: "the mock core bank runs the action", value: stage("bank_ms") },
    { name: "speak", what: "Kokoro starts the reply; fixed openings are cached", value: stage("speech_synthesis") },
  ];
  const example = data.examples.find((item) => item.case === "h-dispute-yesterday");

  return (
    <Section id="turn" title="One turn, from the caller's last word to the reply" command="python -m tellerline.agent.traces --last 1">
      <div className="grid gap-14 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div>
          <p className="dim mb-6 max-w-[62ch]">
            Medians from the agent&apos;s own record of each turn in the latest gate run
            {gate ? ` (${gate.measured} turns)` : ""}. Everything runs on the Mac; nothing leaves
            it.
          </p>
          <ol className="space-y-1" aria-label="The stages of one turn">
            <li className="dim">the caller stops talking</li>
            {stages.map((item, index) => {
              const last = index === stages.length - 1;
              const blocks = item.value === null ? 0 : Math.max(1, Math.round(item.value / BAR_MS));
              return (
                <li
                  key={item.name}
                  className="grid grid-cols-[3ch_12ch_1fr] items-baseline gap-x-[1ch] sm:grid-cols-[3ch_13ch_1fr_9ch]"
                >
                  <span className="after" aria-hidden="true">
                    {last ? "└─" : "├─"}
                  </span>
                  <span className="text-p1">{item.name}</span>
                  <span className="min-w-0">
                    <span className="dim">{item.what}</span>
                    {blocks ? (
                      <span className="block text-bloom" aria-hidden="true">
                        {"▬".repeat(blocks)}
                      </span>
                    ) : null}
                  </span>
                  <span className="tabular col-start-3 text-left sm:col-start-auto sm:text-right">
                    {item.value === null ? <span className="after">{item.note}</span> : ms(item.value)}
                  </span>
                </li>
              );
            })}
            {gate?.latency_s ? (
              <li className="pt-3">
                <span className="dim">the caller hears the reply: </span>
                <span className="bloom">
                  half within {seconds(gate.latency_s.p50)}, nine in ten within {seconds(gate.latency_s.p90)}
                </span>
                <span className="dim mt-2 block max-w-[62ch] text-[0.9em]">
                  The stages above add up to about {seconds(stageTotal(stages))}; the rest of the
                  wait is the audio&apos;s trip through WebRTC in both directions and the hand-offs
                  between stages.
                </span>
              </li>
            ) : null}
          </ol>
          <p className="mt-6 text-[0.9em]">
            {gate ? <Source file={`results/${gate.file}`}>Every turn of that run</Source> : null}
          </p>
        </div>

        {example ? (
          <figure className="space-y-5">
            <figcaption className="dim">
              One held-out turn. Speech recognition writes what it hears; code makes it exact
              before the model reads it, so Gemma never has to do the arithmetic.
            </figcaption>
            <dl className="space-y-4">
              <Row label="heard" value={`"${example.said}"`} />
              <Row label="exact" value={`"${example.understood}"`} tone="bloom" />
              <Row label="Gemma" value={example.after} tone="bloom" />
              <Row label="before" value={`${example.before}  (the cents were lost)`} tone="dim" />
              <Row label="caller hears" value={example.heard_reply} />
            </dl>
          </figure>
        ) : null}
      </div>
    </Section>
  );
}

function stageTotal(stages: Stage[]): number {
  return stages.reduce((sum, stage) => sum + (stage.value ?? 0), 0) / 1000;
}

function Row({ label, value, tone = "text-p1" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="grid grid-cols-[13ch_1fr] gap-x-[1ch]">
      <dt className="dim">{label}</dt>
      <dd className={`${tone} m-0 min-w-0 break-words`}>{value}</dd>
    </div>
  );
}
