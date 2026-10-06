import { data } from "@/lib/data";

import { Section, Source } from "./Section";

const TOTAL_GB = 16;
const BAR_WIDTH = 40; // blocks for the whole 16 GB

const MODELS = [
  { key: "llm-e2b", name: "Gemma 4 E2B", role: "decides", where: "GPU", licence: "Apache-2.0" },
  { key: "stt", name: "Parakeet TDT 0.6B v3", role: "hears", where: "GPU", licence: "CC-BY-4.0" },
  { key: "tts", name: "Kokoro-82M", role: "speaks", where: "GPU", licence: "Apache-2.0" },
  { key: "router", name: "bge-small-en-v1.5", role: "routes", where: "CPU", licence: "MIT" },
] as const;

export function MemorySection() {
  const memory = data.memory;
  const gate = data.live.gate;
  const rows = MODELS.filter((model) => memory[model.key]);
  const resident = (key: string) => {
    const entry = memory[key];
    return entry.weights_gb ?? entry.rss_peak_gb;
  };
  const total = rows.reduce((sum, model) => sum + resident(model.key), 0);
  const pressure = gate?.machine.memory;

  return (
    <Section id="memory" title="Four models, one 16 GB laptop" command="python -m bench.memory">
      <div className="max-w-[68rem]">
        <p className="mb-8 max-w-[64ch] text-[1.05em] leading-relaxed">
          Each model loaded on its own, the way the agent loads it. Together they hold{" "}
          <span className="bloom">{total.toFixed(1)} GB</span> of the Mac&apos;s {TOTAL_GB} GB,
          shared with macOS and everything else that&apos;s open.
        </p>
        <table className="w-full border-collapse text-[0.92em]">
          <thead>
            <tr className="dim text-left">
              <th scope="col" className="pb-2 font-normal">model</th>
              <th scope="col" className="pb-2 font-normal">job</th>
              <th scope="col" className="hidden pb-2 font-normal sm:table-cell">runs on</th>
              <th scope="col" className="pb-2 font-normal">held</th>
              <th scope="col" className="hidden pb-2 font-normal md:table-cell">
                share of {TOTAL_GB} GB
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((model) => {
              const gb = resident(model.key);
              return (
                <tr key={model.key} className="border-t border-scan">
                  <td className="py-2 pr-[1ch]">
                    {model.name}
                    <span className="faint block text-[0.8em]">{model.licence}</span>
                  </td>
                  <td className="dim">{model.role}</td>
                  <td className="dim hidden sm:table-cell">{model.where}</td>
                  <td className="tabular">{gb.toFixed(2)} GB</td>
                  <td className="hidden whitespace-nowrap md:table-cell" aria-hidden="true">
                    <span className="bloom">{"▬".repeat(Math.max(1, Math.round((gb / TOTAL_GB) * BAR_WIDTH)))}</span>
                    <span className="after">
                      {"▬".repeat(BAR_WIDTH - Math.max(1, Math.round((gb / TOTAL_GB) * BAR_WIDTH)))}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="dim mt-6 max-w-[64ch] text-[0.95em]">
          The models on the GPU are measured by MLX; the router runs on ONNX Runtime and is
          measured as the process&apos;s resident memory. Parakeet is converted to bfloat16 as it
          loads, which halves it.
          {pressure?.compressed_gb != null
            ? ` The latest gate ran on the same Mac in everyday use, with ${pressure.compressed_gb.toFixed(1)} GB of memory compressed and ${(pressure.swap_used_gb ?? 0).toFixed(1)} GB of swap in use as it started.`
            : ""}
        </p>
        {memory.file ? (
          <p className="mt-4">
            <Source file={`results/${memory.file}`}>The memory run</Source>
          </p>
        ) : null}
      </div>
    </Section>
  );
}
