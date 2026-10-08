import { data } from "@/lib/data";

import { type LabStage, PipelineLab } from "./PipelineLab";
import { Section } from "./Section";

// The turn's stages from the same medians as the turn bay, set up to be run.
export function LabSection({ number }: { number: number }) {
  const gate = data.live.gate;
  const stage = (key: string) => gate?.stages_ms[key]?.p50 ?? null;
  const stages: LabStage[] = [
    { name: "silence", what: "Silero VAD waits for 200 ms of quiet", ms: stage("endpointing_wait"), side: "hear" },
    { name: "end of turn", what: "Smart Turn v3.2 judges the caller has finished", ms: stage("turn_detection"), side: "hear" },
    { name: "transcript", what: "Parakeet TDT 0.6B v3 transcribes the turn on the GPU", ms: stage("stt_ms"), side: "hear" },
    { name: "exact", what: "Code writes digits, euro amounts and dates exactly", ms: null, side: "hear" },
    { name: "route", what: "bge-small picks one focused skill, on the CPU", ms: data.router?.latency_p90_ms ?? null, side: "decide" },
    { name: "decide", what: "Gemma 4 E2B answers, or writes one ACTION line", ms: stage("model_ms"), side: "decide" },
    { name: "check", what: "Code checks every value against what the caller said", ms: null, side: "decide" },
    { name: "bank", what: "The mock core bank runs the action", ms: stage("bank_ms"), side: "decide" },
    { name: "speak", what: "Kokoro starts the reply; fixed openings are cached", ms: stage("speech_synthesis"), side: "decide" },
  ];
  const latency = gate?.latency_s;
  return (
    <Section id="lab" number={number} title="Run one turn in slow motion" command="python -m tellerline.agent.traces --last 1">
      <div className="mx-auto max-w-[72rem]">
        <p className="prose-width mb-8 text-[1.05rem] leading-relaxed text-ink-2">
          Nine stages between the caller&apos;s last word and the first sound of the reply, each as long
          as it really takes on the Mac. Run it, slow it down, and press any stage to see what it does.
        </p>
        <PipelineLab stages={stages} p50={latency?.p50 ?? null} p90={latency?.p90 ?? null} />
      </div>
    </Section>
  );
}
