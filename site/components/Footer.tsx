import { GitHubIcon } from "./icons";
import { REPO } from "./links";
import { StripMark } from "./StripMark";

const CREDITS = [
  ["Gemma 4 E2B", "Google DeepMind", "Apache-2.0", "https://huggingface.co/google/gemma-4-E2B-it"],
  ["Parakeet TDT 0.6B v3", "NVIDIA", "CC-BY-4.0", "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3"],
  ["Kokoro-82M", "hexgrad", "Apache-2.0", "https://huggingface.co/hexgrad/Kokoro-82M"],
  ["bge-small-en-v1.5", "BAAI", "MIT", "https://huggingface.co/BAAI/bge-small-en-v1.5"],
  ["Silero VAD", "Silero", "MIT", "https://github.com/snakers4/silero-vad"],
  ["Smart Turn v3.2", "Pipecat", "BSD-2-Clause", "https://github.com/pipecat-ai/smart-turn"],
  ["Pipecat", "Daily", "BSD-2-Clause", "https://github.com/pipecat-ai/pipecat"],
  ["MLX", "Apple", "MIT", "https://github.com/ml-explore/mlx"],
  ["RNNoise", "Xiph.Org", "BSD-3-Clause", "https://github.com/xiph/rnnoise"],
  ["Asterisk", "Sangoma", "GPL-2.0, run as a separate program", "https://www.asterisk.org/"],
  ["Geist and Geist Mono", "Vercel", "SIL OFL 1.1", "https://github.com/vercel/geist-font"],
  ["Bricolage Grotesque", "Mathieu Triay", "SIL OFL 1.1", "https://github.com/ateliertriay/bricolage"],
] as const;

export function Footer() {
  return (
    <footer className="border-t border-rail bg-well px-[var(--gutter)] pb-14 pt-20 sm:pt-28">
      <div className="mx-auto grid max-w-[90rem] gap-x-14 gap-y-12 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <div className="flex flex-col gap-5">
          <p className="flex items-center gap-3">
            <StripMark className="h-[26px] w-[50px] text-ink" />
            <span className="callsign text-[2.6rem]">Tellerline</span>
          </p>
          <p className="max-w-[46ch] leading-relaxed">
            An on-device voice banking agent, built and measured on one MacBook Air by{" "}
            <a href="https://github.com/ag2502">Amogh Gaikwad</a>.
          </p>
          <p className="max-w-[46ch] text-[0.95rem] leading-relaxed text-ink-2">
            Tellerline Bank is fictional and imitates no real bank. Every customer, card and payment
            is synthetic, and so are the callers&apos; voices in the recordings. The code is MIT
            licensed.
          </p>
          <p>
            <a className="key" data-primary="" href={REPO}>
              <GitHubIcon />
              github.com/ag2502/Tellerline
            </a>
          </p>
        </div>
        <div>
          <h2 className="label">Built on open models and tools</h2>
          <ul className="mt-4 grid gap-x-10 sm:grid-cols-2">
            {CREDITS.map(([name, by, licence, href]) => (
              <li key={name} className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-3 border-t border-rail py-2 text-[0.92rem]">
                <a href={href} className="font-semibold">
                  {name}
                </a>
                <span className="text-[0.82rem] text-ink-2">
                  {by}, {licence}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
