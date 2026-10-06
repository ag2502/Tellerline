# Tellerline

An on-device voice banking agent in British English. A caller rings a fictional bank, and a
local AI assistant verifies them and handles everyday requests: balances, recent
transactions, freezing a lost card, disputes, and handing over to a human. Speech
recognition, the language model and the voice all run on one MacBook Air M5 with 16 GB of
memory. No cloud APIs, no running costs.

> **Status: Phase 1 gate passed.** The voice agent runs end to end over WebRTC with a mock bank.
> An automated caller timed 182 replies over 220 scripted turns: p50 1.01 s, p90 1.40 s, within
> the 1.5 s target ([D-026](docs/DECISIONS.md)). See [docs/PLAN.md](docs/PLAN.md) and the
> [Phase 0 results](results/PHASE0.md).

## How a turn works

1. **Hear:** Silero VAD, gated on the caller's own speech level rather than the room's, and
   Smart Turn v3.2 decide the caller has finished; Parakeet transcribes. A reply never starts
   over a caller who carries on after a pause: it waits, and the agent answers the whole
   sentence ([D-032, D-033](docs/DECISIONS.md)).
2. **Route:** a 2 ms CPU intent classifier and the call's state choose a focused prompt. A task
   that just asked the caller a question keeps the conversation until the caller clearly
   changes topic, and nothing but identity checks is reachable before verification.
3. **Decide:** Gemma 4 either replies or writes one line such as
   `ACTION freeze card=4217 reason=lost`. There's no tool-calling API: prompt-only actions
   scored 87–97% against 77–80% for native tool calling on the dev set.
4. **Check:** code validates every value and asks a follow-up question when one is missing.
5. **Act and speak:** the bank runs the action and a template speaks the result, so balances
   and dates always come from data rather than the model. Kokoro reads it in a British voice.

## Phase 1 results

Measured by phoning the running agent: `bench.caller` speaks scripted caller lines over WebRTC
and times each reply from the caller's last sample to the agent's first audible one. MacBook Air
M5 on battery with other apps open (about 7 GB in swap).

| Calls at once | Replies measured | Overlaps | Unanswered | p50 | p90 |
|---|---:|---:|---:|---:|---:|
| 1 (the gate) | 182 | 26 | 0 | 1.01 s | 1.40 s |
| 2 | 27 | 1 | 0 | 1.04 s | 1.43 s |
| 3 | 35 | 4 | 1 | 0.94 s | 1.11 s |
| 4 | 44 | 10 | 0 | 0.95 s | 1.22 s |
| 1, in a noisy room | 27 | 1 | 5 | 5.10 s | 9.95 s |

An overlap is a turn where the agent started talking before the caller had finished; it's
counted apart rather than as a fast reply. Quiet-room latency holds with four calls at once. A
noisy room (other people talking 15 dB below the caller) doesn't work yet: the background talk
keeps the caller's turn open.

On the held-out set, written before this phase's tuning, Gemma 4 E2B with the router now gets
every single-turn case and all 8 dialogues right (72% and 6 of 8 before; D-023, D-024).

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
| Telephony | [Asterisk](https://www.asterisk.org/) 23 in a container, its WebSocket channel to the agent ([D-030](docs/DECISIONS.md)) | GPL-2.0 (run as a separate program) |
| Website | [Next.js](https://nextjs.org/) 16, built for Vercel, generated from the results and recorded calls | MIT |
| Tracing | OpenTelemetry | Apache-2.0 |

Why each choice was made, with the measurements behind it: [docs/DECISIONS.md](docs/DECISIONS.md).

## Setup

Requires macOS on Apple Silicon and [uv](https://docs.astral.sh/uv/).

```bash
make setup      # creates .venv and installs the package with its dev extras
make download   # fetches the models, about 12.6 GB
```

Or the same steps by hand:

```bash
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
python scripts/download_models.py
```

## Call the agent

```bash
python -m tellerline.agent
```

Then open **http://localhost:7860**, press Call and allow the microphone. The agent starts the
mock bank and the Gemma 4 server itself. Pipecat's own playground is still at `/client`.

- Step-by-step guide, options and troubleshooting: [docs/RUNNING.md](docs/RUNNING.md)
- Test customers and things to try: [docs/DEMO.md](docs/DEMO.md)

### Ring it from a phone

Asterisk takes a SIP call and hands it to the same agent over its WebSocket channel. With a
container runtime (Colima or Docker Desktop):

```bash
colima start --vm-type vz --port-forwarder grpc
docker compose -f telephony/asterisk/compose.yaml up -d --build
```

Then dial **2000** from a softphone on the Mac (user `caller`, password `tellerline`, server
`127.0.0.1`). Setup, measurement and troubleshooting: [docs/PHONE.md](docs/PHONE.md).

## Website

`site/` is the project's page: a real recorded call replayed with its trace, the measured
numbers, the decision log and a film of one call. Everything on it is generated from the
repository, never typed in: `scripts/export_site_data.py` reads `results/` and
`docs/DECISIONS.md`, and turns calls recorded with `TELLERLINE_RECORD=1` into replays;
`scripts/render_film.py` renders the film from one of them ([D-029](docs/DECISIONS.md)).

```bash
python scripts/export_site_data.py --calls     # results, decisions and the calls in scripts/site_calls.json
cd site && npm install && npm run dev          # http://localhost:3000
```

## Benchmarks

`make bench` runs the whole suite one stage at a time, so the stages don't compete for the
chip, and finishes by writing [results/PHASE0.md](results/PHASE0.md). Each stage also has its
own target:

```bash
make test                                        # unit tests
make lint                                        # ruff check and format --check
make format                                      # apply both fixes
python -m bench.turn                             # make bench-turn: Smart Turn inference time
python -m bench.tts                              # make bench-tts: ONNX (CPU, CoreML) vs MLX
python -m bench.stt                              # make bench-stt: browser- and phone-quality audio
python -m bench.memory                           # make bench-memory: memory per model
python -m bench.router                           # make bench-router: accuracy, thresholds, latency
python -m bench.llm --split dev --mode tools     # native tool calling (the approach replaced)
python -m bench.dialogues --split test           # make bench-dialogues: single prompt vs router
python -m bench.contention                       # make bench-contention: Kokoro and Gemma on the GPU
python -m bench.report                           # make report: writes results/PHASE0.md
python scripts/voice_samples.py                  # make samples: British voices in results/samples/
```

### The latency gate

The Phase 1 gate — 220 automated call turns, p90 within 1.5 s — drives a real WebRTC call
rather than the pipeline in isolation, so it needs the agent already serving. Start the agent
in one shell and run the caller in another:

```bash
python -m tellerline.agent   # shell one
make bench-caller            # shell two
```

It's left out of `make bench` for that reason.

Prompts, examples and thresholds are tuned only on the `dev` split; results are reported on
`test`.

## Repository layout

```
src/tellerline/
  agent/          the voice agent: launcher, Pipecat pipeline, latency logs and tracing
  services/       Pipecat services: Parakeet STT, Kokoro TTS on MLX, the agent's LLM turn
  bank/           mock core-banking API (FastAPI + SQLite) and its client
  brain.py        the decision step: prompt, allowed actions, call state
  actions.py      ACTION syntax, parsing, validation, follow-up questions
  prompts.py      persona and single-prompt steps
  router/         embedder, intent classifier, skill prompts, session rules
  banking/        tool definitions and spoken response templates
  speech.py       money, dates and codes written out for text-to-speech
  tts/            Kokoro on MLX
  agent/phone.py  the phone line: Asterisk's WebSocket channel as a Pipecat transport
bench/            benchmarks, labelled cases (dev, test, held-out), the automated callers
                  (bench.caller over WebRTC, bench.phone over SIP) and their scripts
telephony/        Asterisk for the phone line: container and configuration
site/             the website (Next.js): replay, numbers, decision log, film
scripts/          model download, voice samples, the site's data export, the film renderer
results/          benchmark results (JSONL) and the Phase 0 report
docs/             plan, decision log, running, demo and phone guides
tests/
```

## Credits

- Parakeet TDT 0.6B v3 by NVIDIA, licensed under CC-BY-4.0.
- Gemma 4 by Google DeepMind, licensed under Apache-2.0.
- Kokoro-82M by hexgrad, licensed under Apache-2.0.
- bge-small-en-v1.5 by BAAI, licensed under MIT.
- Asterisk by Sangoma, licensed under GPL-2.0; it runs as a separate program in its own container,
  from the `andrius/asterisk` image.
- The website's typeface is IBM 3270 by Ricardo Bánffy and contributors, licensed under
  BSD-3-Clause.

Tellerline Bank is fictional, and all customer data is synthetic.

## Licence

MIT
