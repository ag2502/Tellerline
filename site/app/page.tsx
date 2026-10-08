import { type Bay, BoardHeader } from "@/components/BoardHeader";
import { CallBoard } from "@/components/CallBoard";
import { CallProvider } from "@/components/CallContext";
import { Footer } from "@/components/Footer";
import { ProofBand } from "@/components/Hero";
import { HeroStage } from "@/components/HeroStage";
import { Reveals } from "@/components/Reveals";
import { FilmSection } from "@/components/sections/FilmSection";
import { LogSection } from "@/components/sections/LogSection";
import { MemorySection } from "@/components/sections/MemorySection";
import { NumbersSection } from "@/components/sections/NumbersSection";
import { PolicySection } from "@/components/sections/PolicySection";
import { RunSection } from "@/components/sections/RunSection";
import { Section } from "@/components/sections/Section";
import { TurnSection } from "@/components/sections/TurnSection";
import { data, loadCall } from "@/lib/data";

// Built once from the exported data, and refreshed hourly for the repository's latest commits.
export const revalidate = 3600;

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

  return (
    <>
      <a
        href="#call"
        className="sr-only z-50 rounded-[5px] bg-ink px-3 py-2 font-semibold text-board focus:not-sr-only focus:fixed focus:left-4 focus:top-3"
      >
        Skip to the call
      </a>
      <Reveals />
      <BoardHeader bays={bays} />
      <CallProvider calls={data.calls} initial={first}>
        <main>
          <HeroStage />
          <ProofBand film={film} />
          <Section id="call" number={number("call")} title="The call, turn by turn" command="python -m tellerline.agent">
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
