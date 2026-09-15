# Decisions

Each entry records what was decided, why, and what was considered instead. Newest last.

## D-001 English only, in a British voice (2026-09-14)

**Decision:** The agent speaks UK-style English. Irish (Gaeilge) is parked.
**Why:** Open Irish speech models are the hard part: the best small open recognisers get
roughly a third to half of words wrong on the BlasBench benchmark, and only one open TTS
model (OmniVoice, non-commercial weights) speaks Irish. Shipping a solid English agent first
gives a working, measurable product.
**Considered:** A bilingual agent from day one; kept as a later phase.

## D-002 Latency target: p90 ≤ 1.5 s (2026-09-14)

**Decision:** 90% of turns must reach the first audio of the reply within 1.5 s of the caller
finishing speaking, measured over 200+ turns on a MacBook Air M5 (16 GB).
**Why:** A median hides slow turns, and slow turns are what callers notice. Filler sounds such
as "mm-hmm" don't count as a reply.
**Considered:** Median-only target.

## D-003 Speech to text: Parakeet TDT 0.6B v3 on MLX (2026-09-14)

**Decision:** `mlx-community/parakeet-tdt-0.6b-v3` via mlx-audio.
**Why:** More accurate on English than Whisper small, fast on Apple Silicon, and less prone to
inventing text on short or silent clips. Licence CC-BY-4.0 (attribution in the README).
**Considered:** Whisper small, Whisper large-v3-turbo, Nemotron 3.5 streaming.

## D-004 LLM: Gemma 4 E2B or E4B, 4-bit, on mlx-lm server (2026-09-14)

**Decision:** Benchmark both in Phase 0 and keep the one that meets the latency target with
the better tool-calling accuracy. Thinking mode is off.
**Why:** Apache-2.0, native tool calling, and only 2.3B (E2B) or 4.5B (E4B) parameters do
the heavy work per token, so both are fast on the M5. `mlx_lm.server` exposes an
OpenAI-compatible API that Pipecat already speaks, and reuses the cached system prompt.
**Considered:** Qwen3.5-4B, EuroLLM-9B, Qomhrá-8B (needed only for Irish).

## D-005 Text to speech: Kokoro-82M with British voices (2026-09-14)

**Decision:** Kokoro v1.0 via kokoro-onnx, Pipecat's built-in `KokoroTTSService`, language
`en-gb`, voices `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis` under evaluation.
**Why:** The fastest open TTS model, Apache-2.0, streams sentence by sentence, and runs on the
CPU so it doesn't compete with the LLM for the GPU. It has no voice cloning, so the voice is a
British preset rather than a cloned accent.
**Considered:** OmniVoice (slower, non-streaming, non-commercial weights), Chatterbox-Turbo,
Qwen3-TTS.

## D-006 Calls: browser WebRTC and self-hosted telephony (2026-09-14)

**Decision:** Two ways to call the same agent: a browser call over Pipecat's SmallWebRTC
transport, and a phone call through Asterisk 23 (open-source phone system, in Docker via
Colima) with a free SIP softphone app, connected with `pipecat-asterisk` over Asterisk's
WebSocket channel. A Twilio trial number may be added later for a demo.
**Why:** No provider offers a permanently free phone number. A local phone system is free
forever, uses the same SIP and phone codecs as real contact centres, and needs no account.
**Considered:** Twilio, Telnyx or Plivo trials only (temporary credit, account needed);
LiveKit SIP (heavier: server, SIP service and Redis).

## D-007 Observability: OpenTelemetry (2026-09-14)

**Decision:** Pipecat's built-in OpenTelemetry tracing, exported locally, with per-stage
timings stored for the latency reports.
**Why:** Vendor-neutral, free, and the same instrumentation used in production at work.

## D-008 Name: Tellerline (2026-09-14)

**Decision:** The project is called Tellerline, and the fictional bank is Tellerline Bank.
**Why:** A bank teller on a phone line: self-explanatory on a CV, and the fictional bank name
avoids imitating any real bank.
**Considered:** Parley, Quay, Glór.

## D-009 Currency and data (2026-09-14)

**Decision:** Amounts are in euro and all customers, cards and transactions are synthetic.
**Why:** The project is built in Ireland. No real customer or employer data is used anywhere.

## D-010 Kokoro runs on MLX, not ONNX Runtime (2026-09-14, supersedes the runtime in D-005)

**Decision:** Kokoro-82M runs as the MLX model on the GPU (`mlx-community/Kokoro-82M-bf16`),
fed with the same espeak-ng phonemes kokoro-onnx uses (`tellerline.tts.kokoro_mlx`), with
leading and trailing silence trimmed.
**Why:** Measured on the MacBook Air M5, kokoro-onnx on the CPU needed 1.2 s (fp16) to 1.4 s
(fp32) before the first audio of a medium sentence; CoreML was slower and int8 about 2.5× slower.
MLX bf16 needs about 0.6 s at p90 across four British voices, a real-time factor of 0.07. The
8-bit MLX build was no faster, so full precision stays. mlx-audio's own Kokoro pipeline needs
misaki, whose English module imports PyTorch; phonemising with espeak-ng avoids that. Kokoro
pads its output with about 0.3 s of silence, which callers would hear as delay, so it is trimmed.
**Considered:** kokoro-onnx fp32/fp16/int8 on CPU and CoreML, MLX 8-bit, misaki + PyTorch.

## D-011 Tool results are spoken from templates (2026-09-14)

**Decision:** The LLM decides what to do; code runs the operation and speaks the result from a
template (`tellerline.banking.responses`), with amounts, dates, card digits and references
written out in words (`tellerline.speech`).
**Why:** Speaking results through a second LLM pass cost about 0.8 s more per action (E4B tool
turn p90 2.66 s in the first benchmark). Templates also mean the caller never hears a balance
or date the model made up, and text-to-speech never has to guess how to read "€1,250.40".
**Considered:** A second LLM pass over the tool result.

## D-012 Prompt-only actions instead of native tool calling (2026-09-14)

**Decision:** No tool-calling API. The prompt lists actions with their exact syntax and a few
made-up examples, and the model either replies or writes one line such as
`ACTION freeze card=4217 reason=lost`, which code parses (`tellerline.actions`).
**Why:** Asked for by the product owner, and confirmed by measurement on the 30-case dev set.
Native tool calling peaked at 80% (E2B) and 77% (E4B) even with a logit bias on the tool-call
token; Gemma 4's small models tend to say "I can freeze that for you" instead of calling. The
same cases in prompt-only form scored 87% (E2B) and 97% (E4B), and an action line is shorter to
generate than a tool call.
**Considered:** Native tool calling with and without a tool-call logit bias (0, 2, 4, 6), and
with per-step tool subsets.

## D-013 Evaluation method: dev for tuning, held-out test for results (2026-09-14)

**Decision:** Prompts, examples and thresholds are tuned only on the dev cases and dialogues.
Results are reported on a separate test set that was written before any tuning, with different
wording, card numbers, merchants and date formats. A test checks the two sets never share a
sentence, and that prompt examples never repeat a benchmark sentence.
**Why:** Tuning prompts against the cases you report inflates accuracy; with 30 cases that
effect is large.

## D-014 Code checks every action before it runs (2026-09-14)

**Decision:** Action values are validated (8-digit customer number, real dates, 4-digit card
number, known account and reason). When the model picks the right action but a value is missing
or invalid, the agent asks a fixed follow-up question instead of running it. The prompt lists
the past week's dates explicitly.
**Why:** On dev, models copied syntax placeholders (`customer=<8 digits>`) or wrote a
verification with an empty date of birth, and got relative dates ("on Saturday") wrong. Validation
turns those into correct slot-filling questions, and the date list removes arithmetic from
the model. Together they took E2B dialogue turns on dev from 59% to 100%.

## D-015 Intent router with sticky tasks (2026-09-15)

**Decision:** Each caller turn is classified on the CPU by bge-small-en-v1.5 embeddings against
hand-written example sentences (about 2 ms). The call's state then picks one focused skill
prompt (identity, accounts, cards, disputes, general): banking skills are unreachable before
verification; a skill that just asked a question keeps the conversation unless the classifier
is confident the topic changed; unsure turns use the full single prompt.
**Why:** Proposed by the product owner as prompt-per-use-case routing, with an LLM deciding
whether to classify. An LLM classifier would add one or two LLM calls per turn (250–550 ms
each on this Mac), so the classifier is an embedding model instead, and "don't reclassify
mid-conversation" becomes "classify every turn, but only switch on a confident signal". On the
held-out test set the classifier was never confidently wrong (100% accuracy on the 78% of turns
it was confident about). With Gemma 4 E2B the router got every multi-turn dialogue fully right
(7/7, against 5/7 for the single prompt), at the cost of single-turn accuracy (84% against 92%)
and about 0.1 s of p90 latency from switching between prompts. Test failures to address in
Phase 1, with a fresh held-out set: the identity skill sometimes transfers unverified callers
instead of asking for their details, relative dates ("last Friday"), amounts spoken as
"63 euro 20", and freeze reasons the case labels treat more strictly than the bank would.
**Considered:** One prompt with every action (best single-turn accuracy, weaker in
conversations and grows with every use case); an LLM intent classifier (too slow).

## D-016 Gemma 4 E2B (2026-09-15)

**Decision:** Ship Gemma 4 E2B (4-bit).
**Why:** On the held-out test set E2B was within a few turns of E4B on accuracy (and ahead in
multi-turn dialogues with the router), while its decision latency was about half: reply p90
0.34–0.45 s against 0.92–1.18 s. The conservative projected turn latency is 1.36–1.47 s for
replies with E2B and 1.94–2.20 s with E4B, which misses the target in every configuration.
The E4B test runs came last in a long benchmark session on a fanless laptop, so some of its
gap may be heat; its dev-set reply p90 was 0.69 s, still too slow.
