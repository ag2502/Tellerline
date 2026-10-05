import { REPO } from "./links";

const CREDITS = [
  ["Gemma 4 E2B", "Google DeepMind", "Apache-2.0", "https://huggingface.co/google/gemma-4-E2B-it"],
  ["Parakeet TDT 0.6B v3", "NVIDIA", "CC-BY-4.0", "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3"],
  ["Kokoro-82M", "hexgrad", "Apache-2.0", "https://huggingface.co/hexgrad/Kokoro-82M"],
  ["bge-small-en-v1.5", "BAAI", "MIT", "https://huggingface.co/BAAI/bge-small-en-v1.5"],
  ["Silero VAD", "Silero", "MIT", "https://github.com/snakers4/silero-vad"],
  ["Smart Turn v3.2", "Pipecat", "BSD-2-Clause", "https://github.com/pipecat-ai/smart-turn"],
  ["Pipecat", "Daily", "BSD-2-Clause", "https://github.com/pipecat-ai/pipecat"],
  ["MLX", "Apple", "MIT", "https://github.com/ml-explore/mlx"],
  ["IBM 3270 font", "Ricardo Banffy and contributors", "BSD-3-Clause", "/fonts/LICENSE-3270.txt"],
] as const;

export function Footer() {
  return (
    <footer className="window border-t border-scan pb-[calc(var(--status-h)+3rem)]">
      <div className="mx-auto grid max-w-[80rem] gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-4">
          <p className="display text-[clamp(1.6rem,1.2rem+1.4vw,2.4rem)]">Tellerline</p>
          <p className="max-w-[48ch]">
            An on-device voice banking agent, built and measured on one MacBook Air by{" "}
            <a href="https://github.com/ag2502">Amogh Gaikwad</a>.
          </p>
          <p className="dim max-w-[48ch] text-[0.95em]">
            Tellerline Bank is fictional and imitates no real bank. Every customer, card and payment
            is synthetic. The code is MIT licensed.
          </p>
          <p>
            <a href={REPO}>github.com/ag2502/Tellerline</a>
          </p>
        </div>
        <div>
          <p className="dim mb-3">Built on open models and tools</p>
          <ul className="grid gap-x-8 gap-y-1.5 text-[0.92em] sm:grid-cols-2">
            {CREDITS.map(([name, by, licence, href]) => (
              <li key={name} className="min-w-0">
                <a href={href}>{name}</a> <span className="dim">{by}, {licence}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="after mx-auto mt-16 max-w-[80rem] text-[0.9em]" aria-hidden="true">
        [process exited with code 0]
      </p>
    </footer>
  );
}
