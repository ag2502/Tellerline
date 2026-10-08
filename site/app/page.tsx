import { type Bay, BoardHeader } from "@/components/BoardHeader";
import { CallBoard } from "@/components/CallBoard";
import { CallProvider } from "@/components/CallContext";
import { Footer } from "@/components/Footer";
import { ProofBand } from "@/components/Hero";
import { HeroStage } from "@/components/HeroStage";
import { Marquee } from "@/components/Marquee";
import { Pointer } from "@/components/Pointer";
import { Reveals } from "@/components/Reveals";
import { FilmSection } from "@/components/sections/FilmSection";
import { LogSection } from "@/components/sections/LogSection";
import { MemorySection } from "@/components/sections/MemorySection";
import { NumbersSection } from "@/components/sections/NumbersSection";
import { PolicySection } from "@/components/sections/PolicySection";
import { RunSection } from "@/components/sections/RunSection";
import { Section } from "@/components/sections/Section";
import { TurnSection } from "@/components/sections/TurnSection";
import { SmoothScroll } from "@/components/SmoothScroll";
import type { Formation } from "@/components/stage/formations";
import { Stage } from "@/components/stage/Stage";
import { data, loadCall, percent, seconds } from "@/lib/data";

// Built once from the exported data, and refreshed hourly for the repository's latest commits.
export const revalidate = 3600;

// What the 3D scene sets in each bay, all of it from the exported runs.
function stageData(): Formation["data"] {
  const gate = data.live.gate;
  const stage = (key: string) => gate?.stages_ms[key]?.p50 ?? 0;
  const hear = stage("endpointing_wait") + stage("turn_detection") + stage("stt_ms");
  const decide = (data.router?.latency_p90_ms ?? 0) + stage("model_ms") + stage("bank_ms") + stage("speech_synthesis");
  const memory = data.memory;
  const held = (key: string) => (memory[key] ? (memory[key].weights_gb ?? memory[key].rss_peak_gb) : 0);
  return {
    histogram: gate?.histogram ?? [],
    turn: { hearEnd: hear / 1000, total: (hear + decide) / 1000, p50: gate?.latency_s?.p50 ?? 0, p90: gate?.latency_s?.p90 ?? 0 },
    memory: [
      { name: "Gemma 4 E2B", gb: held("llm-e2b"), tone: "decide" },
      { name: "Parakeet", gb: held("stt"), tone: "hear" },
      { name: "Kokoro", gb: held("tts"), tone: "speak" },
      { name: "bge-small", gb: held("router"), tone: "route" },
    ],
  };
}

export default async function Page() {
  const first = await loadCall(data.calls[0].slug);
  const film = Boolean(data.film);
  // The board's bays, in order: each one's number is the key that jumps to it.
  const bays: Bay[] = [
    { id: "call", name: "call" },
    { id: "turn", name: "turn" },
    { id: "numbers", name: "numbers" },
    { id: "policy", name: "policy" },
    { id: "memory", name: "memory" },
    { id: "log", name: "log" },
    ...(film ? [{ id: "film", name: "film" }] : []),
    { id: "run", name: "run" },
  ];
  const number = (id: string) => bays.findIndex((bay) => bay.id === id);
  const gate = data.live.gate?.latency_s;
  const held = stageData().memory.reduce((sum, model) => sum + model.gb, 0);
  const claims = [
    gate ? `nine in ten replies within ${seconds(gate.p90)}` : null,
    data.live.phone?.latency_s ? `${seconds(data.live.phone.latency_s.p90)} over a phone line` : null,
    data.accuracy.holdout ? `${percent(data.accuracy.holdout.single_turn)} of held-out turns right` : null,
    `four models in ${held.toFixed(1)} GB`,
    "nothing leaves the Mac",
  ].filter(Boolean) as string[];

  return (
    <>
      <a
        href="#call"
        className="sr-only z-50 rounded-[5px] bg-amber px-3 py-2 font-semibold text-[#16191d] focus:not-sr-only focus:fixed focus:left-4 focus:top-3"
      >
        Skip to the call
      </a>
      <SmoothScroll />
      <Reveals />
      <Pointer />
      <Stage data={stageData()} />
      <BoardHeader bays={bays} />
      <CallProvider calls={data.calls} initial={first}>
        <main>
          <HeroStage />
          <ProofBand film={film} />
          <Marquee items={claims} />
          <Section id="call" number={number("call")} title="The call, strip by strip" command="python -m tellerline.agent">
            <div className="mx-auto max-w-[72rem]">
              <CallBoard />
            </div>
          </Section>
          <TurnSection number={number("turn")} />
          <NumbersSection number={number("numbers")} />
          <PolicySection number={number("policy")} />
          <MemorySection number={number("memory")} />
          <LogSection number={number("log")} />
          {film ? <FilmSection number={number("film")} /> : null}
          <RunSection number={number("run")} />
        </main>
      </CallProvider>
      <div className="relative z-10">
        <Footer />
      </div>
    </>
  );
}
