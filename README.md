# Tellerline

An on-device voice banking agent in British English. A caller rings a fictional bank, and a
local AI assistant verifies them and handles everyday requests: balances, recent
transactions, freezing a lost card, disputes, and handing over to a human. Speech
recognition, the language model and the voice all run on one MacBook Air M5 with 16 GB of
memory. No cloud APIs, no running costs.

> **Status: Phase 0 complete.** Every stage has been benchmarked on the target Mac, and the
> agent's decision logic is built and tested. The voice pipeline is next (Phase 1).
> See [docs/PLAN.md](docs/PLAN.md) and the full [Phase 0 results](results/PHASE0.md).

## How a turn works

1. **Hear:** Silero VAD and Smart Turn v3.2 decide the caller has finished; Parakeet
   transcribes.
2. **Route:** a 2 ms CPU intent classifier and the call's state choose a focused prompt. A task
   that just asked the caller a question keeps the conversation until the caller clearly
   changes topic, and nothing but identity checks is reachable before verification.
3. **Decide:** Gemma 4 either replies or writes one line such as
   `ACTION freeze card=4217 reason=lost`. There's no tool-calling API: prompt-only actions
   scored 87–97% against 77–80% for native tool calling on the dev set.
4. **Check:** code validates every value and asks a follow-up question when one is missing.
5. **Act and speak:** the bank runs the action and a template speaks the result, so balances
   and dates always come from data rather than the model. Kokoro reads it in a British voice.

## Phase 0 results

Held-out test set: 38 single-turn cases and 7 multi-turn dialogues, written before any
tuning. Measured on a MacBook Air M5 (16 GB).

| Gemma 4 | Brain | Single-turn | Dialogues fully right | Decision p90, reply | Decision p90, action |
|---|---|---:|---:|---:|---:|
| E2B | single prompt | 92% | 5/7 | 336 ms | 483 ms |
| **E2B** | **router** | 84% | **7/7** | 452 ms | 530 ms |
| E4B | single prompt | 97% | 5/7 | 924 ms | 1,009 ms |
| E4B | router | 92% | 6/7 | 1,180 ms | 1,097 ms |

| Stage | p90 |
|---|---:|
| Smart Turn end-of-turn check | 16 ms |
| Parakeet speech-to-text (browser or phone audio) | 67 ms |
| Intent classifier | 3 ms |
| Kokoro first audio, medium sentence (MLX) | 657 ms |

Projected turn latency (sum of stage p90s, conservative): **1.36–1.47 s for replies with E2B**;
action turns land at 1.50–1.55 s, just over the 1.5 s target. The biggest lever for Phase 1 is
making the first sentence of each spoken result short, since Kokoro's short-sentence p90 is
about 160 ms. E4B misses the target in every configuration.

## Stack

| Stage | Choice | Licence |
|---|---|---|
| Pipeline | [Pipecat](https://github.com/pipecat-ai/pipecat) 1.10 | BSD-2-Clause |
| Voice activity and turn detection | Silero VAD, Smart Turn v3.2 | MIT, BSD-2-Clause |
| Speech to text | [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) on MLX via [mlx-audio](https://github.com/Blaizzy/mlx-audio) | CC-BY-4.0 |
| Intent classifier | [bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) on ONNX Runtime (CPU) | MIT |
| Language model | [Gemma 4](https://huggingface.co/google/gemma-4-E2B-it) E2B, 4-bit, on [mlx-lm](https://github.com/ml-explore/mlx-lm) server | Apache-2.0 |
| Text to speech | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) on MLX, espeak-ng phonemes (British voices) | Apache-2.0 |
| Telephony (Phase 2) | Asterisk 23 + [pipecat-asterisk](https://github.com/NikolayShakin/pipecat-asterisk) | GPL-2.0, BSD-2-Clause |
| Tracing | OpenTelemetry | Apache-2.0 |

Why each choice was made, with the measurements behind it: [docs/DECISIONS.md](docs/DECISIONS.md).

## Setup

Requires macOS on Apple Silicon and [uv](https://docs.astral.sh/uv/).

```bash
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/download_models.py   # about 12.6 GB
```

## Benchmarks

```bash
make test                                        # unit tests
python -m bench.turn                             # Smart Turn inference time
python -m bench.tts                              # Kokoro runtimes: ONNX (CPU, CoreML) vs MLX
python -m bench.stt                              # Parakeet on browser- and phone-quality audio
python -m bench.memory                           # memory per model
python -m bench.router                           # intent classifier accuracy, thresholds, latency
python -m bench.llm --split dev --mode tools     # native tool calling (the approach replaced)
python -m bench.dialogues --split test           # single prompt vs router, E2B vs E4B
python -m bench.contention                       # Kokoro and Gemma sharing the GPU
python -m bench.report                           # writes results/PHASE0.md
python scripts/voice_samples.py                  # British voice samples in results/samples/
```

Prompts, examples and thresholds are tuned only on the `dev` split; results are reported on
`test`.

## Repository layout

```
src/tellerline/
  brain.py        the decision step: prompt, allowed actions, call state
  actions.py      ACTION syntax, parsing, validation, follow-up questions
  prompts.py      persona and single-prompt steps
  router/         embedder, intent classifier, skill prompts, session rules
  banking/        tool definitions and spoken response templates
  speech.py       money, dates and codes written out for text-to-speech
  tts/            Kokoro on MLX
bench/            Phase 0 benchmarks and labelled cases (dev and test)
scripts/          model download, voice samples
results/          benchmark results (JSONL) and the Phase 0 report
docs/             plan and decision log
tests/
```

## Credits

- Parakeet TDT 0.6B v3 by NVIDIA, licensed under CC-BY-4.0.
- Gemma 4 by Google DeepMind, licensed under Apache-2.0.
- Kokoro-82M by hexgrad, licensed under Apache-2.0.
- bge-small-en-v1.5 by BAAI, licensed under MIT.

Tellerline Bank is fictional, and all customer data is synthetic.

## Licence

MIT
