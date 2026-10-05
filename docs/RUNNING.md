# Running Tellerline, step by step

Everything runs on one Apple Silicon Mac. These steps were written on a MacBook Air M5 (16 GB).

## 1. Install the prerequisites (once)

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Get the code:
   ```bash
   git clone https://github.com/ag2502/Tellerline.git
   cd Tellerline
   ```

## 2. Create the environment (once)

```bash
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Check it worked:

```bash
make test
```

All tests should pass.

## 3. Download the models (once, about 12.6 GB)

```bash
python scripts/download_models.py
```

This fetches Gemma 4 E2B and E4B, Parakeet, Kokoro and the benchmark baselines into your
Hugging Face and Pipecat caches. The intent classifier (bge-small, 130 MB) downloads the first
time the agent starts.

After the first successful start, you can skip Hugging Face's network checks:

```bash
export HF_HUB_OFFLINE=1
```

## 4. Start the agent

In a terminal, from the project folder:

```bash
source .venv/bin/activate
python -m tellerline.agent
```

Wait for these lines (about 10–30 seconds):

```
Mock bank running at http://127.0.0.1:8090
Models, intent classifier and LLM prompt cache warmed up
Bot ready! (WebRTC)
```

The agent starts three things on your Mac:

| Port | What |
|---|---|
| 7860 | The call page and WebRTC server |
| 8080 | Gemma 4 on mlx-lm (a child process) |
| 8090 | The mock bank |

## 5. Call it from your browser

1. Open **http://localhost:7860** in Chrome or Safari (it opens the call page at `/call/`).
2. Press **Call** and allow microphone access.
3. The agent says: "Hello, you're through to Tellerline Bank. I'm an AI assistant."
4. Wear headphones, so the agent doesn't hear itself and interrupt.
5. Verify as a test customer. For example, say: "My customer number is 4 5 1 2 7 8 9 0 and my date
   of birth is the 3rd of March 1991." Say the digits one by one.
6. Ask for something: "What's the balance on my current account?"

More test customers and things to try are in [DEMO.md](DEMO.md).

Each call's turn latencies are written to `results/calls/<call id>.jsonl`, and traces to
`results/traces/`.

## 6. Stop the agent

Press `Ctrl+C` in the agent's terminal. The Gemma server stops with it. If a server is left
over (for example after closing the terminal window), stop it with:

```bash
pkill -f llm_server_main
```

## 7. Measure latency without a microphone (optional)

With the agent running (step 4), open a second terminal:

```bash
source .venv/bin/activate
python -m bench.caller --turns 20     # quick check, about 3 minutes
python -m bench.caller --turns 220    # the full latency gate, about 40 minutes
```

The automated caller phones the agent over WebRTC and prints each call's turn latencies, then
p50, p90 and p95. Results are saved to `results/caller-<time>.jsonl`.

## 8. Re-run the Phase 0 benchmarks (optional)

Stop the agent first, so benchmarks don't compete with it for the chip:

```bash
make bench     # every stage, then writes results/PHASE0.md
```

Or one at a time: see the Benchmarks section of the [README](../README.md).

## Options

Set these before `python -m tellerline.agent`:

```bash
TELLERLINE_VOICE=bm_george python -m tellerline.agent
```

| Variable | Default | Choices |
|---|---|---|
| `TELLERLINE_VOICE` | `bf_emma` | `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis` |
| `TELLERLINE_LLM` | `e2b` | `e2b`, `e4b` |
| `TELLERLINE_TRACING` | `1` | `1` on, `0` off |
| `TELLERLINE_RECORD` | `0` | `1` saves each call's timeline and both voices to `results/recordings/<call id>/` |
| `TELLERLINE_NOISE` | `1` | `1` RNNoise and noise-aware turn-taking, `0` off (to measure their effect) |

To hear the voices first: `python scripts/voice_samples.py`, then open `results/samples/`.

## Troubleshooting

| Problem | Fix |
|---|---|
| You can't hear the agent | Its voice plays in the browser tab at http://localhost:7860, not in the terminal. Open the page, press Call, allow the microphone and check the tab isn't muted. Typing in the terminal does nothing. |
| Strange calls appear in the log | The automated caller (`bench.caller`) is running. Stop it before calling from the browser; both would share the same agent. |
| `Address already in use` | An agent is already running. Stop it (`Ctrl+C`), or find it with `lsof -i :7860`. |
| The page loads but there's no greeting | Check the terminal for errors, reload the page and connect again. |
| The agent keeps interrupting itself | Use headphones; speakers feed its own voice back into the microphone. |
| The agent answers before you've finished | Pause less mid-sentence. It answers after 0.2 s of silence if your sentence sounds complete, or 2 s otherwise. |
| First reply is slow | The first start after a reboot loads models from disk; later calls are warm. |
| Replies get slower over a long session | Other apps are using memory and macOS is compressing the agent's. Closing heavy apps helps, but isn't required. |
| `mlx_lm.server exited early` | Read `results/logs/mlx-server-agent.log`. Usually the model isn't downloaded: run step 3. |
| Model downloads fail with `HF_HUB_OFFLINE` set | Unset it (`unset HF_HUB_OFFLINE`) for the download, then set it again. |
