# The phone line

Tellerline answers phone calls through [Asterisk](https://www.asterisk.org/) 23. Asterisk takes
the SIP call and hands it to the agent over its WebSocket channel driver (chan_websocket): one
websocket per call, carrying the call's audio as 16 kHz signed linear PCM, with JSON control
messages. The agent runs the same pipeline as for a browser call; only the line differs
(`src/tellerline/agent/phone.py`, D-030).

```
SIP phone ──SIP + RTP, G.711 or G.722──▶ Asterisk (container) ──WebSocket, slin16──▶ agent /phone
```

A phone call carries far less audio than the browser: G.711 is 8 kHz at 8 bits a sample, so
everything above 4 kHz is gone before the agent hears it. Asterisk converts it to 16 kHz for
Parakeet and converts the agent's voice back down. Silero VAD is less sure of telephone-band
speech, so phone calls use a lower VAD confidence than browser calls (`PHONE_VAD_CONFIDENCE`).

## 1. Run Asterisk

Asterisk runs in a Linux container (`telephony/asterisk`). On a Mac without Docker Desktop,
[Colima](https://github.com/abiosoft/colima) provides the Linux VM; its gRPC port forwarder is
the one that carries UDP, which SIP and RTP need:

```bash
brew install colima docker docker-compose        # or the release binaries of each
colima start --vm-type vz --cpu 2 --memory 2 --port-forwarder grpc
docker compose -f telephony/asterisk/compose.yaml up -d --build
```

The configuration in `telephony/asterisk/etc` is built into the image rather than mounted
(macOS keeps a VM's file sharing out of Desktop and Documents), so rebuild after changing it:
`docker compose -f telephony/asterisk/compose.yaml up -d --build`. Asterisk loads only the 46
modules the line uses.

Asterisk listens for SIP on `127.0.0.1:5060` (UDP), with RTP on ports 10000-10019, and sends each
call to the agent at `ws://host.docker.internal:7860/phone`, which Colima maps to the Mac's own
localhost: the agent never listens beyond the Mac. Check it's up:

```bash
docker compose -f telephony/asterisk/compose.yaml ps        # "healthy"
docker compose -f telephony/asterisk/compose.yaml exec asterisk asterisk -rx "pjsip show endpoints"
```

To stop it: `docker compose -f telephony/asterisk/compose.yaml down`, then `colima stop`.

## 2. Start the agent

```bash
python -m tellerline.agent
```

The same process serves the browser call page and the phone line; its log shows
`Phone line for Asterisk: ws://localhost:7860/phone`.

## 3. Ring it

**From a softphone** on the Mac (Linphone, Zoiper or any SIP client):

| Setting | Value |
|---|---|
| Username | `caller` |
| Password | `tellerline` |
| Domain / server | `127.0.0.1` |
| Transport | UDP |

Dial **2000**. The agent answers with its greeting; verify as a test customer from
[DEMO.md](DEMO.md) and talk as you would on the browser call.

**Automatically**, to measure the line: `bench.phone` places bench.caller's scripted calls over
SIP with G.711 mu-law audio at 8 kHz, like a basic phone, and times every reply from the last
packet of the caller's speech to the first audible packet of the answer.

```bash
python -m bench.phone --turns 40
python -m bench.phone --script bench/data/demo_calls.json
```

Results go to `results/phone-<time>.jsonl`.

## Reaching it from another device

The SIP and audio ports are published on the Mac's localhost only, and the passwords above are
in the repository, so nothing outside the Mac can call in. To answer a phone on your own network,
publish the ports on the Mac's address in `compose.yaml`, set `external_signaling_address` and
`external_media_address` in `etc/pjsip.conf` to that address, and change both passwords.

A real phone number needs a SIP trunk from a telephony provider: add the trunk to `pjsip.conf`
and send its incoming calls to the `tellerline` context in `extensions.conf`.

## Troubleshooting

| Problem | Fix |
|---|---|
| The call fails at once with "404 Not Found" | Asterisk couldn't reach the agent: start `python -m tellerline.agent` first. |
| Nothing answers on port 5060 | Colima is forwarding TCP only: `colima stop`, then start it again with `--port-forwarder grpc`. |
| `docker compose up` fails with "operation not permitted" on a mount | An older compose file mounted `etc/`; use the one in the repository, which builds it in. |
| The agent doesn't react to some short replies | Raise the caller's volume, or lower `PHONE_VAD_CONFIDENCE` in `src/tellerline/config.py`. |
