# Plan

Tellerline is an on-device voice banking agent: a caller phones or opens a browser call, and
a fictional bank's assistant answers in British English, verifies them, and handles everyday
requests. Everything runs on one MacBook Air M5 (16 GB) and costs nothing to run.

## Goals

- **Latency:** p90 ≤ 1.5 s from the caller finishing speaking to the first audio of the
  reply, over 200+ turns (see D-002).
- **Zero cost:** open models and tools only; no paid APIs.
- **Honest engineering:** every number in the README comes from a run on the target Mac.

## Call flow

1. **Caller speaks** in a browser call (WebRTC) or on a softphone through Asterisk.
2. **End of turn:** Silero VAD detects silence, then Smart Turn v3.2 judges whether the
   caller has finished.
3. **Transcribe:** Parakeet TDT 0.6B v3 on MLX.
4. **Route:** a CPU intent classifier (bge-small, about 2 ms) and the call's state pick a focused
   skill prompt, or the full prompt when unsure (`tellerline.router`, see D-015).
5. **Decide:** Gemma 4 on mlx-lm server replies, or writes one `ACTION` line; no tool-calling
   API (D-012). Code validates the action and asks a follow-up question if a value is missing
   (D-014).
6. **Act and speak:** the mock bank runs the action and a template speaks the result (D-011),
   through Kokoro on MLX with a British voice (D-010), one sentence at a time.
7. **Measure:** every stage is traced with OpenTelemetry.

## Phases

Each phase ends at a gate; the next phase starts only when the gate passes.

### Phase 0: Prove it on this Mac (done, see `results/PHASE0.md`)

- uv environment, model downloads.
- Benchmarks for each stage: Smart Turn, Kokoro runtimes, Parakeet (browser and phone audio),
  memory, the intent classifier, and Gemma 4 E2B vs E4B with a single prompt and with the
  router, on held-out single-turn cases and multi-turn dialogues.
- Findings that changed the design: Kokoro on ONNX was too slow (D-010), native tool calling
  was unreliable (D-012), and speaking results through the LLM cost 0.8 s (D-011).
- **Gate:** projected p90 within 1.5 s, a Gemma 4 model chosen, and every model fits in memory
  together.

### Phase 1: Browser call, end to end (gate passed, see D-026)

- Mock bank API (FastAPI, SQLite, synthetic customers).
- Pipecat pipeline with SmallWebRTC and the AI disclosure at the start of every call.
- Custom Pipecat services: Parakeet speech-to-text and Kokoro-on-MLX text-to-speech, plus an
  agent processor that runs the brain (`tellerline.brain`), validates actions and speaks
  templates.
- Real end-to-end latency measured from the audio, per stage, per turn.
- OpenTelemetry tracing and a turn-latency log.
- **Gate:** measured p90 ≤ 1.5 s over 200 turns.

### Phase 2: Telephony (gate passed, see D-030)

- Asterisk 23 in a container (Colima), bridging each call to the agent over its WebSocket
  channel with Tellerline's own serializer (`pipecat-asterisk` was the plan; D-030 says why not).
- A SIP softphone calls extension 2000; `bench.phone` places scripted calls over G.711.
- Later, optionally: a phone number from a SIP trunk provider.
- **Gate:** a full call from a phone works, and phone-line latency is measured: 34 replies over
  40 benchmark turns, p90 1.23 s (`docs/PHONE.md`).

### The website (D-029)

- `site/`: the project's page on Vercel, generated from the results and recorded calls, with a
  replay of real calls and a film rendered from one of them.

### Phase 3: callsim

- Simulated callers from YAML scenarios, in text mode (fast, runs in CI) and voice mode
  (synthetic speech through the full pipeline, including phone-band audio).
- Deterministic checks plus an offline LLM judge, calibrated against human labels.
- **Gate:** the regression suite passes in CI.

### Phase 4: Benchmarks, hardening, launch

- Apple Silicon benchmark report, including a 30-minute heat test on the fanless Air.
- PII redaction in logs, AI audio watermark (AudioSeal), model cards, demo video.
- **Gate:** review, then publish the repository.

### Later: Irish

Omnilingual ASR for Irish speech, OmniVoice for an Irish voice, and an Irish-capable LLM
(Qomhrá-8B, EuroLLM-9B). Parked until the English agent ships (see D-001).
