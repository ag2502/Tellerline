import { data } from "@/lib/data";

import { Section, Source } from "./Section";

const TOTAL_GB = 16;

const MODELS = [
  { key: "llm-e2b", name: "Gemma 4 E2B", role: "decides", where: "GPU", licence: "Apache-2.0" },
  { key: "stt", name: "Parakeet TDT 0.6B v3", role: "hears", where: "GPU", licence: "CC-BY-4.0" },
  { key: "tts", name: "Kokoro-82M", role: "speaks", where: "GPU", licence: "Apache-2.0" },
  { key: "router", name: "bge-small-en-v1.5", role: "routes", where: "CPU", licence: "MIT" },
] as const;

export function MemorySection({ number }: { number: number }) {
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
    <Section id="memory" number={number} title="Four models, one 16 GB laptop" command="python -m bench.memory">
      <div className="grid gap-x-14 gap-y-10 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <div className="flex flex-col gap-5">
          <p className="prose-width text-[1.15rem] leading-relaxed">
            Each model loaded on its own, the way the agent loads it. Together they hold{" "}
            <strong>{total.toFixed(1)} GB</strong> of the Mac&apos;s {TOTAL_GB} GB, shared with macOS
            and everything else that&apos;s open.
          </p>
          <p className="prose-width text-[0.95rem] leading-relaxed text-ink-2">
            The models on the GPU are measured by MLX; the router runs on ONNX Runtime and is
            measured as the process&apos;s resident memory. Parakeet is converted to bfloat16 as it
            loads, which halves it.
            {pressure?.compressed_gb != null
              ? ` The latest gate ran on the same Mac in everyday use, with ${pressure.compressed_gb.toFixed(1)} GB of memory compressed and ${(pressure.swap_used_gb ?? 0).toFixed(1)} GB of swap in use as it started.`
              : ""}
          </p>
          {memory.file ? <Source file={`results/${memory.file}`}>The memory run</Source> : null}
        </div>

        <div className="flex flex-col gap-2">
          {/* The whole 16 GB as one strip, the four models laid end to end in it. */}
          <figure className="holder-agent mb-4" aria-label={`The four models hold ${total.toFixed(1)} of ${TOTAL_GB} GB`}>
            <div className="strip px-4 pb-3 pt-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span className="label">the Mac&apos;s {TOTAL_GB} GB</span>
                <span className="print whitespace-nowrap text-[0.95rem] font-semibold">
                  {total.toFixed(1)} GB <span className="font-normal text-ink-3">held by the four</span>
                </span>
              </div>
              <div className="gb-ticks mt-2.5 flex h-8 overflow-hidden rounded-[2px] bg-[#f3f5f7]" aria-hidden="true">
                {rows.map((model) => (
                  <span
                    key={model.key}
                    className="h-full border-r-2 border-strip bg-ink first:rounded-l-[2px]"
                    style={{ width: `${(resident(model.key) / TOTAL_GB) * 100}%` }}
                    title={`${model.name}: ${resident(model.key).toFixed(2)} GB`}
                  />
                ))}
              </div>
              <div className="print mt-1.5 flex justify-between text-[0.68rem] text-ink-3" aria-hidden="true">
                {[0, 4, 8, 12, 16].map((value) => (
                  <span key={value}>{value === TOTAL_GB ? `${value} GB` : value}</span>
                ))}
              </div>
            </div>
          </figure>

          <ol className="flex flex-col gap-2">
            {rows.map((model) => {
              const gb = resident(model.key);
              return (
                <li key={model.key} className="holder-plain">
                  <dl className="strip grid grid-cols-3 sm:grid-cols-[minmax(0,1.5fr)_5.5rem_6rem_6rem_minmax(0,1.2fr)]">
                    <div className="box col-span-3 border-b border-rule sm:col-span-1 sm:border-b-0">
                      <dt className="sr-only">model</dt>
                      <dd className="m-0 font-semibold leading-tight">{model.name}</dd>
                      <dd className="m-0 text-[0.74rem] text-ink-3">{model.licence}</dd>
                    </div>
                    <Cell label="job" first>
                      {model.role}
                    </Cell>
                    <Cell label="runs on">{model.where}</Cell>
                    <Cell label="held">
                      <span className="print font-semibold">{gb.toFixed(2)} GB</span>
                    </Cell>
                    <div className="box col-span-3 flex items-center border-l-0 border-t border-rule sm:col-span-1 sm:border-l sm:border-t-0" aria-hidden="true">
                      <span className="gb-ticks relative block h-3 w-full rounded-[1px] bg-[#f3f5f7]">
                        <span className="absolute inset-y-0 left-0 rounded-[1px] bg-ink" style={{ width: `${(gb / TOTAL_GB) * 100}%` }} />
                      </span>
                    </div>
                  </dl>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </Section>
  );
}

function Cell({ label, first = false, children }: { label: string; first?: boolean; children: React.ReactNode }) {
  return (
    <div className={`box ${first ? "border-l-0 sm:border-l" : ""}`}>
      <dt className="label">{label}</dt>
      <dd className="m-0 text-[0.95rem]">{children}</dd>
    </div>
  );
}
