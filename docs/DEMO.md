# Calling Tellerline

## Start the agent

```bash
source .venv/bin/activate
python -m tellerline.agent
```

This starts the mock bank, the Gemma 4 server and the call page, and warms every model (about
10 seconds when the models are already downloaded). Then open
**http://localhost:7860**, press Call and allow the microphone. Headphones stop the
agent from hearing itself.

Options, as environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TELLERLINE_VOICE` | `bf_emma` | Agent voice: `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis` |
| `TELLERLINE_LLM` | `e2b` | `e2b` or `e4b` |
| `TELLERLINE_TRACING` | `1` | OpenTelemetry spans to `results/traces/` |
| `TELLERLINE_RECORD` | `0` | `1` records each call to `results/recordings/` |

Per-turn latency for each call is written to `results/calls/<call id>.jsonl`.

## Test customers

All customers are fictional. The agent needs the 8-digit customer number and the date of birth
before it will discuss an account. Say the customer number digit by digit.

| Name | Customer number | Date of birth | Cards (last four) |
|---|---|---|---|
| Aoife Byrne | 45127890 | 3 March 1991 | 4217, 0093 |
| Cian Murphy | 30118842 | 14 July 1985 | 5561 |
| Niamh Kelly | 77451102 | 29 February 1996 | 7780, 1188 |
| Seán O'Brien | 61023397 | 21 November 1978 | 6604, 3317 |
| Róisín Walsh | 22904718 | 1 April 2001 | 2291, 8850 |
| Declan Ryan | 58331026 | 9 June 1964 | 5092, 7701 |

Aoife's current account holds €1,250.40 (€1,180.40 available). Other balances and all
transactions are generated fresh each time the bank starts.

## Things to try

- "What's the balance on my savings account?"
- "Read me my last four transactions."
- "I think my card ending 4217 has been stolen." Then: "Yes, send me a new one."
- "There's a 30 euro charge from Pizza Palace yesterday that wasn't me."
- "Actually, can I speak to a person?" (ends the call with a transfer)
- Interrupt the agent while it's talking.
- Try a card that isn't yours, or a wrong date of birth three times.

## Measure latency without a microphone

With the agent running, in a second terminal:

```bash
python -m bench.caller --turns 220
```

The automated caller phones the agent over WebRTC, speaks benchmark caller lines in an
American voice, and times every turn from the end of its speech to the first audio of the
reply.
