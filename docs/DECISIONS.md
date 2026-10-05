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

## D-017 The bank is a separate HTTP service scoped by verified customer (2026-09-15)

**Decision:** The mock bank is a FastAPI + SQLite service the agent calls over HTTP. Account,
card and dispute endpoints take a customer id, which the agent only receives from a successful
identity check; the agent's client refuses banking calls before then.
**Why:** It mirrors how a voice agent integrates with core banking, and it makes "another
customer's data" unreachable by construction rather than by prompt: a caller who names someone
else's card gets "I can't find a card ending ... on your account".

## D-018 The agent's turn is a subclass of Pipecat's OpenAI LLM service (2026-09-15)

**Decision:** `TellerlineLLMService` extends Pipecat's OpenAI-compatible service and overrides
only how a response is produced: route the turn, stream Gemma from the local server, pass speech
straight to text-to-speech, hold back an `ACTION` line, validate it, call the bank and speak the
template.
**Why:** Interruptions, metrics and OpenTelemetry tracing keep working as for any Pipecat LLM,
while none of Pipecat's tool-calling machinery is involved (D-012). Only text that could still
become "ACTION" is ever delayed.

## D-019 Memory: capped MLX cache, Parakeet in bfloat16, models warmed once (2026-09-15)

**Decision:** Every MLX process caps its freed-buffer cache at 512 MB; Parakeet loads in
bfloat16; the launcher loads and warms every model and primes the LLM's prompt cache before the
first call.
**Why:** The first live calls took up to 9 s per turn because the Mac was swapping: MLX's cache
had grown to 5.4 GB in the agent, Parakeet's float32 weights took 2.3 GB, and each call re-ran a
warm-up that compiled kernels for 11 s. bfloat16 Parakeet matched float32 on 23 of 24 test
clips (WER 0.8%). Memory pressure from other apps is treated as normal: capacity such as the
LLM prompt cache is not reduced to avoid it.

## D-020 Turn-taking settings for a phone line (2026-09-15)

**Decision:** Silero VAD waits 0.2 s of silence, Smart Turn v3.2 judges whether the caller has
finished, and if it thinks they haven't, the agent answers anyway after 2 s (Pipecat's default is
5 s). When a caller pauses mid-sentence and the pause is taken as the end of a turn, everything
they said since the agent last spoke is sent to the model as one message.
**Why:** In pilot calls, sentences with pauses ("My customer number is ... and my date of birth
is ...") were split into fragments and the model only saw the last one. Five seconds of silence
on a phone line sounds like a dropped call.

## D-021 Latency is measured by phoning the agent (2026-09-15)

**Decision:** The Phase 1 gate uses an automated WebRTC caller (`bench.caller`) that connects
like the browser page, speaks benchmark caller lines (numbers digit by digit, as callers say
them), and times each turn from its last speech sample to the first audible reply sample.
**Why:** It measures what a caller experiences, including WebRTC buffering, the silence wait,
turn detection and playback, which stage benchmarks can't. The caller's audio is rendered in a
separate process before calls so it never competes with the agent for memory or the GPU.

## D-022 Replies are spoken clause by clause, with fixed phrases rendered in advance (2026-10-05)

**Decision:** Kokoro renders each sentence one clause at a time: the first clause alone, the rest
merged up to 140 characters, with the pause a comma or full stop implies put back as silence
(`tellerline.tts.chunks`). Rendered clauses go into a cache shared by every call, and the fixed
phrases (greeting, follow-up questions, the opening of every spoken result) are rendered at
start-up. Result templates now open with a fixed clause that already says what happened ("I've
frozen that card for you.", "On your savings account,") and give the details after it.
**Why:** Kokoro renders a whole text before any of it plays, at about 60 ms plus 2.7 ms per
character on the M5. Live calls showed the cost: a balance sentence took 0.3 s to start, and five
transactions read as one sentence 1.25 s. Across every template (`bench.first_audio`), time from
text to first audio went from p50 150 ms / p90 1,105 ms for the whole first sentence to p50 127 ms
/ p90 151 ms for the first clause, and p50 0 ms / p90 54 ms with the cache.
**Considered:** A one-word acknowledgement ("Done.") before each result: faster still, but it
says nothing and would game the latency measure (D-002). Splitting inside a clause: Kokoro's
prosody breaks at a seam with no punctuation.

## D-023 Code makes digits, amounts and dates exact before the model reads a turn (2026-10-05)

**Decision:** Each caller turn passes through `tellerline.understanding` before the model sees
it: digits said as words become figures ("seven two oh six" is 7206, "double oh four one" is
0041), amounts become euro figures ("34 euro 60" is €34.60), and every date is followed by the
date it means ("last Tuesday (2026-09-08)", "14/07/1985 (1985-07-14)"). One shared step,
`Brain.interpret`, then decides what the model's answer leads to, for the live agent and the
benchmarks alike: a card or customer number the caller never said becomes a follow-up question
rather than reaching the bank, and an unverified caller whose turn produced a banking action is
asked for their details instead of hearing "Sorry, I didn't quite catch that".
**Why:** On a new held-out set (written before this work), Gemma 4 E2B with the router copied
the prompt example's customer number when the real one was said as "double seven four five...",
froze card "41" for "double oh four one", dropped the cents from "34 euro 60", got "last
Tuesday" and "on the 3rd" wrong, and invented card 7890 from the tail of the customer number.
Each of these is arithmetic or copying, which code does exactly. With this step the dev set went
to 97% single-turn and 100% of dialogue turns.
**Considered:** More prompt examples (they grow every prompt and still leave arithmetic to a
2B model); rejecting ungrounded values silently (the caller would hear nothing useful).

## D-024 Callers can unfreeze a found card and ask about a card; calls end only on a goodbye (2026-10-05)

**Decision:** Two new actions, `unfreeze` and `status`, are offered in the cards skill and the
full prompt. The bank lifts a freeze only for cards frozen as lost or temporary; a card frozen as
stolen or for suspicious payments stays blocked and the caller is offered a replacement. The
status answer says whether a card is frozen, why, and when its replacement arrives (in working
days). Separately, `end` now runs only if the caller's own words contain a goodbye or "that's
all"; otherwise the agent asks whether there's anything else.
**Why:** "I found my card" was the most common thing a frozen-card caller could not do, and E2B
answered it by freezing the card again. On dev, E2B also hung up on "No, I'm sure it'll turn up"
after declining a replacement, and a hang-up can't be taken back. The goodbye rule was written
from the dev and test cases and then checked against every end-of-call label in all three splits
without changes.
**Result:** Measured once after the work, Gemma 4 E2B with the router on the held-out set: 100%
single-turn (72% before D-023), 100% of dialogue turns (89%), 8 of 8 dialogues (6). On the Phase 0
test set: 95% single-turn (84% in Phase 0) and 7 of 7 dialogues. Decision p90: 376 ms for replies,
544 ms for actions.

## D-025 Turn-taking: voice starts a turn when the agent is silent; transcripts are final (2026-10-05)

**Decision:** While the agent is silent, the caller's turn starts as soon as Silero VAD hears
speech; while it talks, the caller needs two words to interrupt (the noise rule from Phase 1,
now applied only where it was meant to). Parakeet's transcripts are marked final, since each
VAD segment is transcribed whole, and Pipecat is told Parakeet's real p99 (0.35 s from the end of
speech) instead of its 1.0 s default. When Smart Turn judges a caller unfinished but Parakeet's
transcript ends a sentence of four or more words, the turn is released after 0.5 s instead of
2 s. When an unverified caller has given half their details, or a turn ends on a label whose
value hasn't come yet ("My customer number..."), the reply is held for 1.0 s; a caller who
carries on cancels it before a word is spoken over them. `bench.caller` now counts turns where
the agent spoke before the caller finished as overlaps, apart from latency.
**Why:** Per-turn traces from live calls (D-021's caller, now with the agent's own report of each
turn) showed "turn end" taking about 1,070 ms on most turns. The two-word rule started every
turn from its transcript, after the caller had already finished; that reset Pipecat's stop
strategy, which then waited out a timer derived from the 1.0 s STT default. The same traces
showed the agent answering at the pause after a customer number, which the old caller scored as
20-200 ms "replies".
**Result:** 30-turn pilots on the MacBook Air M5 (battery, other apps open): before, p50 1.49 s and
p90 1.76 s with overlap artefacts counted as fast turns; after, 28 turns measured, 2 overlaps,
none without a reply, p50 0.92 s, p90 1.13 s, p95 1.19 s. The full 220-turn gate follows.
**Considered:** A shorter VAD silence (0.2 s is already short); disabling the noise rule (it
protects real calls in noisy rooms).

## D-026 No punctuation grace; the identity hold reads the whole call (2026-10-05)

**Decision:** The rule from D-025 that released a turn 0.5 s after Smart Turn doubted it, when
Parakeet's transcript ended a sentence, is removed: Smart Turn's verdict stands, with Pipecat's
2 s fallback. The 1 s hold now applies only when this turn gives a customer number or a date
of birth (a date at least ten years back, not "yesterday") and the call still lacks the other.
Digit groups split by pauses ("four five one two. seven eight nine zero", "573. 02918") are
joined when they make the eight digits of a customer number; dates are never joined.
**Why:** The first full 220-turn gate after D-025 measured 135 clean turns (p50 0.96 s, p90
1.50 s) and 85 overlaps, turns where the agent spoke before the caller had finished. The
synthetic callers pause mid-sentence (at commas, around digits read one by one, inside "49.99"),
Parakeet writes each pause as a full stop, and the grace turned Smart Turn's correct "not
finished" into a reply over the caller. Meanwhile no clean turn took the slow 2 s path, so the
grace bought nothing. Separately, the hold fired on any date ("What's the weather like today?")
and on a date of birth that completed a number given a turn earlier, adding 1 s to those turns.
**Result:** The 220-turn gate after this change, on the MacBook Air M5 running on battery with
other apps open (6.9 GB in swap): 208 caller turns spoken, 182 replies measured and none
unanswered; p50 1.01 s, p90 1.40 s, p95 1.48 s, within the 1.5 s target. 26 turns were overlaps,
against 85 in the gate before (`results/caller-20261005T120429Z.jsonl`). Most of those left are
Smart Turn ending the turn at a pause inside a synthetic caller's sentence ("A cash machine in
Galway | swallowed my card"), plus a few where Parakeet misheard a customer number read digit by
digit, so the identity hold didn't apply.
**Considered:** A longer VAD silence (adds latency to every turn); keeping the grace with more
words required (Parakeet punctuates long fragments too).

## D-027 What recording the demo calls found (2026-10-05)

**Decision:** Three fixes, each from a recorded demo call. A verified caller's open task keeps
answers the classifier reads confidently as small talk: "Yes, please." to the replacement offer
had moved the call to the general skill, which transferred the caller instead of ordering the
card. A date of birth must be at least ten years back: "the 29th", heard on its own, became
29 September 2026. And once the agent has ended the call, nothing the caller says starts a turn
and the agent answers nothing more, so a "bye" over its goodbye no longer brings a second
goodbye. (This was first a Pipecat user-mute strategy, which also dropped the caller's audio
before it reached the call recording; the turn-start rules now hold off instead.) The demo script now says each request
as one sentence, gives the found-card caller a regular voice and says "34 euro and 60 cent".
A second recording added two more: a turn that's only a greeting ("Hi, it's Niamh", heard as
"Naim" and taken for a request for a person) can't transfer the caller, and an amount may have a
full stop after "euro" and "sent" for "cent" ("It was 34 euro. And 60 sent").
**Why:** The website replays the five scripted demo calls (`bench/data/demo_calls.json`), so each
has to go through cleanly, and each failure was a defect a real caller could hit. The latency
gate's calls are short and don't walk through an offer and its answer.
**Result:** Dialogue accuracy is unchanged on every split after all five changes: held-out 100%
single-turn and 8 of 8 dialogues, test 95% and 7 of 7, dev 97%. The third recording went through
on every call. Two problems stay open. Kokoro's breathy af_nicole voice wasn't detected as speech
for its first few seconds (Silero VAD at confidence 0.8). And Parakeet, given only "thirty-four
euro sixty" cut off at a pause, once wrote "€3460", which no rule can safely read as €34.60: the
dispute reads the amount back, but only after opening it, so the next step is to confirm the
amount first. The slow first reply these calls also showed is D-028.

## D-028 Two latency tails: a lone "Bye." and a cold first reply (2026-10-05)

**Decision:** A caller's turn ends at once when they've stopped and the transcript ends with a
goodbye ("bye", "bye now", "cheers", "see you"), alongside Smart Turn (`GoodbyeStopStrategy`).
And when a call starts with no other call in progress, the agent runs one small pass through
Parakeet, Kokoro, the intent classifier and Gemma while the pre-rendered greeting plays, at the
lowest MLX priority (`tellerline.agent.warm`).
**Why:** The two slowest replies of the 220-turn gate (3.29 s and 2.85 s) were "No, it's fine.
Bye.": Smart Turn was unsure about the lone "Bye." and the turn waited out the 2 s fallback. And
on a Mac in everyday use, macOS pages out models that sit idle: the first reply of a call placed
after the caller's lines were rendered in another process took 11.0-11.6 s (D-027).
**Result:** `bench/data/goodbye_calls.json` rings off five ways, plus a control without a
goodbye: the closing replies took 0.64-0.92 s, and the control was asked whether there was
anything else. With the cached lines deleted so they render first, as before, the first reply
took 1.24 s instead of 11.0 s; the re-warm itself took 11.6 s, but behind the greeting and the
caller's first sentence instead of in front of the reply. With the models already in memory it
takes about 0.3 s.
**Considered:** Keeping the models warm with a timer (costs energy all day on a laptop, and
doesn't help if a call arrives between ticks); a shorter Smart Turn fallback (adds cut-ins).

## D-029 The website shows only what was measured or recorded (2026-10-05)

**Decision:** The project website (`site/`, Next.js on Vercel) is generated from the repository.
`scripts/export_site_data.py` reads every benchmark result and this log into
`site/data/site.json`, and turns calls the agent recorded (`TELLERLINE_RECORD=1`) into a replay:
both voices, when each was audible (found in the audio, not from voice activity events, which
arrive 0.2 s late), the agent's own report of each turn, the caller's script line, and the wait
the automated caller timed. The film is rendered frame by frame from one recording with its own
audio (`scripts/render_film.py`). Nothing on the site is typed in by hand, and the hourly rebuild
only adds the repository's latest commits.
**Why:** The site is for engineers and hiring managers, who need to hear a real call and trace
every number to a run they could repeat. A screen recording would show one call at whatever the
recorder caught and drift from the data, and a hosted live demo would contradict the point: the
agent needs the Mac. Each replayed wait is shown twice because the two honest measurements differ:
at the agent the recording shows the answer, and the caller hears it a median 0.35 s later on
these calls, after WebRTC both ways, which is what every latency number on the site includes.
**Result:** Recording the demo calls found seven defects, fixed in D-027 and D-028 before the
calls were recorded for the site.
**Considered:** A live demo through a tunnel to the Mac (works only while the Mac is awake and
serving); a screen-recorded video (not reproducible); showing only the agent-side gaps (they look
faster than the measured numbers, for a reason a visitor can't see).
