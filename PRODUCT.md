# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

The site is Next.js (App Router, React 19) deployed on Vercel, chosen by the owner. It lives
beside the Python agent in this repository. The agent itself is Python (Pipecat, MLX) and runs
only on Apple Silicon Macs.

## Users

Primary: engineers and hiring managers judging the project and its author. They arrive from a
CV, a GitHub profile or a post, give the page a minute or two, and want to know whether the
thing is real, how good it is, and how it was built. They should leave having heard a real call,
believing the measured numbers, and opening the GitHub repository.

Secondary: developers who want to run it on their own Apple Silicon Mac.

## Product Purpose

Tellerline is a voice banking agent for a fictional Irish bank, Tellerline Bank. A caller rings
in (browser call over WebRTC, or a phone line through Asterisk), and an AI assistant speaking
British English verifies them, then handles everyday requests: balances, recent transactions,
freezing, unfreezing and replacing cards, card status, disputes, and handing over to a human.
Success means replies that feel like a person on the line (p90 within 1.5 s of the caller
finishing), correct actions, and nothing a caller hears being invented by the model.

## Positioning

The whole call runs on one MacBook Air M5 with 16 GB of memory: hearing (Silero VAD, Smart Turn,
Parakeet), deciding (an intent router and Gemma 4 E2B) and speaking (Kokoro). No cloud APIs and
no running costs. The model only decides what to do; code checks every value, the bank runs the
action, and a template speaks the result, so balances, dates and references always come from
data. A caller who has not verified cannot reach account data, by construction rather than by
prompt.

## Operating Context

- The agent starts with `python -m tellerline.agent`; callers use the call page at
  http://localhost:7860 in a browser, or a SIP softphone through Asterisk (this phase).
- Six synthetic test customers with fixed details (docs/DEMO.md); everything else is generated.
- Benchmarks run on the target Mac and write JSONL results under `results/`; reports such as
  results/PHASE0.md are generated from them.
- Decisions are logged with their measurements in docs/DECISIONS.md.

## Capabilities and Constraints

- British English only, in a British Kokoro voice; Irish is parked (D-001).
- Euro amounts; Irish context; all customers, cards and transactions are synthetic (D-009).
- Every call starts with an AI disclosure.
- The agent never moves money, never asks for a full card number or PIN, and transfers to a
  colleague for anything else (loans, hardship, bereavement, other people's accounts).
- Prompt-only actions (`ACTION freeze card=4217 reason=lost`) instead of native tool calling
  (D-012).
- Runs only on Apple Silicon; the website cannot host the live agent, so the site shows real
  recorded calls and measured results rather than a live call.

## Brand Commitments

- Name: Tellerline (a bank teller on a phone line); the bank is Tellerline Bank, fictional and
  not imitating any real bank (D-008).
- Voice: plain, specific, measured British English; honest engineering, where every number
  comes from a run on the target Mac.
- Credits for every model must stay visible (Parakeet CC-BY-4.0, Gemma 4 Apache-2.0,
  Kokoro Apache-2.0, bge-small MIT). Code is MIT.
- Author: Amogh Gaikwad (GitHub `ag2502`).

## Evidence on Hand

- Phase 0 report and raw results: results/PHASE0.md, results/*.jsonl.
- Live-call latency runs from the automated WebRTC caller: results/caller-*.jsonl.
- Decision log with measurements: docs/DECISIONS.md.
- Real call recordings, transcripts and per-stage timings from this phase's recorder.
- None of the following exist and none may be invented: users, customers, testimonials,
  press, pricing, partner logos, or benchmark numbers not produced by a run.

## Product Principles

1. Prove it with a measurement taken on the target Mac, or don't say it.
2. The model decides; code owns facts. Anything a caller hears that is a number, date or
   reference comes from data.
3. Safety by construction: what an unverified caller can reach is decided by code and APIs,
   not by the prompt.
4. On-device and free: no cloud dependency at call time.
5. Sound like a good British phone manner: short, plain, warm, never chatty.
