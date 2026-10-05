import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { FilmSection } from "@/components/sections/FilmSection";
import { LogSection } from "@/components/sections/LogSection";
import { MemorySection } from "@/components/sections/MemorySection";
import { NumbersSection } from "@/components/sections/NumbersSection";
import { PolicySection } from "@/components/sections/PolicySection";
import { RunSection } from "@/components/sections/RunSection";
import { TurnSection } from "@/components/sections/TurnSection";
import { StatusBar, type StatusWindow } from "@/components/StatusBar";
import { data, loadCall } from "@/lib/data";

// Built once from the exported data, and refreshed hourly for the repository's latest commits.
export const revalidate = 3600;

export default async function Page() {
  const first = await loadCall(data.calls[0].slug);
  const film = Boolean(data.film);
  const windows: StatusWindow[] = [
    { id: "call", name: "call" },
    { id: "turn", name: "turn" },
    { id: "numbers", name: "numbers" },
    { id: "policy", name: "policy" },
    { id: "memory", name: "memory" },
    { id: "log", name: "log" },
    ...(film ? [{ id: "film", name: "film" }] : []),
    { id: "run", name: "run" },
  ];

  return (
    <>
      <a
        href="#turn"
        className="inverse sr-only z-50 px-3 py-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip the call
      </a>
      <main>
        <Hero calls={data.calls} call={first} film={film} />
        <TurnSection />
        <NumbersSection />
        <PolicySection />
        <MemorySection />
        <LogSection />
        <FilmSection />
        <RunSection />
      </main>
      <Footer />
      <StatusBar windows={windows} />
    </>
  );
}
