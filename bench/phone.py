"""Automated phone caller: ring the agent through Asterisk and time each reply.

The same scripted calls and the same measurement as bench.caller, over a phone line instead of
WebRTC. A small SIP user agent dials the bank's number on Asterisk (telephony/asterisk) and talks
G.711 mu-law at 8 kHz, which is what a real phone call carries: a third of the bandwidth of the
browser call's audio, quantised to 8 bits a sample. Asterisk converts it for the agent, so the
agent hears what it would hear from a phone.

Each turn is timed from the last packet of the caller's speech to the first audible packet of
the reply, so the interval includes Asterisk, both of its audio conversions and the agent.

Usage (with python -m tellerline.agent and Asterisk running; see docs/PHONE.md):
    python -m bench.phone --turns 40
    python -m bench.phone --script bench/data/demo_calls.json
"""

import argparse
import asyncio
import contextlib
import hashlib
import re
import secrets
import socket
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soxr

from bench.caller import RATE, BotEar, converse
from bench.caller import run as run_calls

PHONE_RATE = 8_000
PACKET_SAMPLES = 160  # 20 ms at 8 kHz
PACKET_S = PACKET_SAMPLES / PHONE_RATE
PCMU = 0  # RTP payload type for G.711 mu-law
SIP_TIMEOUT_S = 8.0
SIP_RETRANSMIT_S = 0.5
USER_AGENT = "tellerline-bench"


# ---------------------------------------------------------------- G.711 mu-law

_BIAS = 0x84
_CLIP = 32635


def ulaw_encode(pcm: np.ndarray) -> bytes:
    """16-bit samples to G.711 mu-law bytes."""
    x = pcm.astype(np.int32)
    sign = np.where(x < 0, 0x80, 0)
    x = np.minimum(np.abs(x), _CLIP) + _BIAS
    exponent = np.clip(np.floor(np.log2(x)).astype(np.int32) - 7, 0, 7)
    mantissa = (x >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa) & 0xFF).astype(np.uint8).tobytes()


def ulaw_decode(data: bytes) -> np.ndarray:
    """G.711 mu-law bytes to 16-bit samples."""
    u = ~np.frombuffer(data, dtype=np.uint8).astype(np.int32) & 0xFF
    exponent = (u >> 4) & 0x07
    magnitude = ((((u & 0x0F) << 3) + _BIAS) << exponent) - _BIAS
    return np.where(u & 0x80, -magnitude, magnitude).astype(np.int16)


def to_phone(pcm: np.ndarray, rate: int = RATE) -> np.ndarray:
    """A caller line (16-bit at `rate`) as the 8 kHz audio a phone line carries."""
    samples = soxr.resample(pcm.astype(np.float32) / 32768.0, rate, PHONE_RATE)
    return (np.clip(samples, -1, 1) * 32767).astype(np.int16)


# ---------------------------------------------------------------- SIP messages


@dataclass
class SipMessage:
    start: str
    headers: list[tuple[str, str]]
    body: str = ""

    @property
    def status(self) -> int | None:
        match = re.match(r"SIP/2\.0 (\d{3})", self.start)
        return int(match[1]) if match else None

    @property
    def method(self) -> str | None:
        return None if self.status else self.start.split(" ", 1)[0]

    def header(self, name: str) -> str | None:
        name = _COMPACT.get(name.lower(), name.lower())
        for key, value in self.headers:
            if _COMPACT.get(key.lower(), key.lower()) == name:
                return value
        return None

    def encode(self) -> bytes:
        lines = [self.start, *(f"{key}: {value}" for key, value in self.headers)]
        lines.append(f"Content-Length: {len(self.body.encode())}")
        return ("\r\n".join(lines) + "\r\n\r\n" + self.body).encode()


_COMPACT = {
    "v": "via",
    "f": "from",
    "t": "to",
    "i": "call-id",
    "m": "contact",
    "l": "content-length",
    "c": "content-type",
}


def parse_message(data: bytes) -> SipMessage:
    head, _, body = data.decode(errors="replace").partition("\r\n\r\n")
    start, *rest = head.split("\r\n")
    headers = []
    for line in rest:
        if ":" in line:
            key, _, value = line.partition(":")
            headers.append((key.strip(), value.strip()))
    return SipMessage(
        start, [h for h in headers if h[0].lower() not in ("content-length", "l")], body
    )


def sdp_offer(address: str, rtp_port: int, session: int) -> str:
    """Offer G.711 mu-law only, in 20 ms packets, as a basic phone would."""
    return (
        "v=0\r\n"
        f"o=- {session} {session} IN IP4 {address}\r\n"
        "s=tellerline-bench\r\n"
        f"c=IN IP4 {address}\r\n"
        "t=0 0\r\n"
        f"m=audio {rtp_port} RTP/AVP {PCMU}\r\n"
        f"a=rtpmap:{PCMU} PCMU/8000\r\n"
        "a=ptime:20\r\n"
        "a=sendrecv\r\n"
    )


def parse_sdp(body: str) -> tuple[str | None, int | None]:
    """The address and port the answer wants audio sent to."""
    address = re.search(r"^c=IN IP4 (\S+)", body, re.M)
    port = re.search(r"^m=audio (\d+)", body, re.M)
    return (address[1] if address else None), (int(port[1]) if port else None)


def parse_challenge(header: str) -> dict[str, str]:
    """The fields of a `Digest realm="...", nonce="...", ...` challenge."""
    fields = re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]*))', header)
    return {key.lower(): quoted or bare for key, quoted, bare in fields}


def digest(
    method: str,
    uri: str,
    user: str,
    password: str,
    challenge: dict[str, str],
    cnonce: str | None = None,
) -> str:
    """An Authorization header answering a digest challenge (RFC 2617, MD5)."""

    def md5(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    realm, nonce = challenge.get("realm", ""), challenge.get("nonce", "")
    ha1 = md5(f"{user}:{realm}:{password}")
    ha2 = md5(f"{method}:{uri}")
    fields = [
        f'username="{user}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
        "algorithm=MD5",
    ]
    if "auth" in challenge.get("qop", "").split(","):
        cnonce = cnonce or secrets.token_hex(8)
        response = md5(f"{ha1}:{nonce}:00000001:{cnonce}:auth:{ha2}")
        fields += ["qop=auth", "nc=00000001", f'cnonce="{cnonce}"']
    else:
        response = md5(f"{ha1}:{nonce}:{ha2}")
    fields.append(f'response="{response}"')
    if "opaque" in challenge:
        fields.append(f'opaque="{challenge["opaque"]}"')
    return "Digest " + ", ".join(fields)


# ---------------------------------------------------------------- the call


@dataclass
class Target:
    host: str = "127.0.0.1"
    port: int = 5060
    number: str = "2000"
    user: str = "bench"
    password: str = "tellerline"


class _Signalling(asyncio.DatagramProtocol):
    def __init__(self, call: "PhoneCall"):
        self.call = call
        self.responses: asyncio.Queue[SipMessage] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr) -> None:
        message = parse_message(data)
        if message.status is not None:
            self.responses.put_nowait(message)
        else:
            self.call.request_received(message)


class _Media(asyncio.DatagramProtocol):
    def __init__(self, ear: BotEar):
        self.ear = ear

    def datagram_received(self, data: bytes, addr) -> None:
        if len(data) < 12 or data[1] & 0x7F != PCMU:
            return
        offset = 12 + 4 * (data[0] & 0x0F)
        if data[0] & 0x10:  # header extension
            offset += 4 + 4 * int.from_bytes(data[offset + 2 : offset + 4], "big")
        samples = ulaw_decode(data[offset:]).astype(np.float32) / 32768.0
        self.ear.hear(samples, time.perf_counter())


@dataclass
class PhoneCall:
    """One SIP call: dial, talk mu-law over RTP, hang up."""

    target: Target
    background: np.ndarray | None = None
    ear: BotEar = field(default_factory=BotEar)
    up: bool = False
    _call_id: str = field(default_factory=lambda: f"{secrets.token_hex(8)}@tellerline")
    _tag: str = field(default_factory=lambda: secrets.token_hex(4))
    _cseq: int = 0
    _remote_tag: str = ""
    _remote_contact: str = ""
    _pending: deque = field(default_factory=deque)
    _done: asyncio.Future | None = None
    _invite: tuple[SipMessage, str] | None = None  # the last INVITE sent, and its branch

    @property
    def uri(self) -> str:
        return f"sip:{self.target.number}@{self.target.host}:{self.target.port}"

    async def dial(self) -> None:
        loop = asyncio.get_running_loop()
        server = (self.target.host, self.target.port)
        self._sip, self._signalling = await loop.create_datagram_endpoint(
            lambda: _Signalling(self), remote_addr=server
        )
        self._rtp, _ = await loop.create_datagram_endpoint(
            lambda: _Media(self.ear), local_addr=(self._local_address(), 0)
        )
        self._rtp_port = self._rtp.get_extra_info("sockname")[1]
        offer = sdp_offer(self._local_address(), self._rtp_port, int(time.time()))
        response = await self._transact("INVITE", body=offer)
        if response.status in (401, 407):
            self._ack(response)
            header = "WWW-Authenticate" if response.status == 401 else "Proxy-Authenticate"
            challenge = parse_challenge(response.header(header) or "")
            authorization = digest(
                "INVITE", self.uri, self.target.user, self.target.password, challenge
            )
            name = "Authorization" if response.status == 401 else "Proxy-Authorization"
            response = await self._transact("INVITE", body=offer, extra=[(name, authorization)])
        if response.status != 200:
            raise ConnectionError(f"Asterisk answered {response.start}")
        self._remote_tag = _tag_of(response.header("To") or "")
        contact = re.search(r"<([^>]+)>", response.header("Contact") or "")
        self._remote_contact = contact[1] if contact else self.uri
        self._ack(response)
        # Send the audio back the way the signalling went: the answer's address is Asterisk's
        # view of itself, which may be a container's.
        _, media_port = parse_sdp(response.body)
        self._media_to = (self.target.host, media_port)
        self.up = True
        self._sender = asyncio.ensure_future(self._send_audio())

    def say(self, pcm: np.ndarray) -> asyncio.Future:
        """Queue a line of 8 kHz audio; resolves with the time its last packet went out."""
        chunks = [pcm[i : i + PACKET_SAMPLES] for i in range(0, len(pcm), PACKET_SAMPLES)]
        if len(chunks[-1]) < PACKET_SAMPLES:
            chunks[-1] = np.pad(chunks[-1], (0, PACKET_SAMPLES - len(chunks[-1])))
        self._pending.extend(chunks)
        self._done = asyncio.get_running_loop().create_future()
        return self._done

    async def hang_up(self) -> None:
        if self.up:
            self.up = False
            with contextlib.suppress(TimeoutError):
                await self._transact("BYE", uri=self._remote_contact, timeout=2.0)
        if hasattr(self, "_sender"):
            self._sender.cancel()
        for endpoint in ("_rtp", "_sip"):
            if hasattr(self, endpoint):
                getattr(self, endpoint).close()

    def request_received(self, message: SipMessage) -> None:
        """Requests from Asterisk: the agent hanging up, or a keep-alive."""
        if message.method == "ACK":
            return
        reply = SipMessage(
            "SIP/2.0 200 OK",
            [(key, value) for key, value in message.headers if key.lower() in _ECHOED],
        )
        self._sip.sendto(reply.encode())
        if message.method == "BYE":
            self.up = False
            self.ear.ended = True

    # ------------------------------------------------------------ internals

    def _local_address(self) -> str:
        return (
            "127.0.0.1"
            if self.target.host in ("127.0.0.1", "localhost")
            else _route_to(self.target.host)
        )

    def _request(
        self, method: str, uri: str, cseq: int, branch: str, extra=(), body=""
    ) -> SipMessage:
        local = self._sip.get_extra_info("sockname")
        to = f"<sip:{self.target.number}@{self.target.host}>"
        if self._remote_tag:
            to += f";tag={self._remote_tag}"
        headers = [
            ("Via", f"SIP/2.0/UDP {local[0]}:{local[1]};branch={branch};rport"),
            ("Max-Forwards", "70"),
            ("From", f"<sip:{self.target.user}@{self.target.host}>;tag={self._tag}"),
            ("To", to),
            ("Call-ID", self._call_id),
            ("CSeq", f"{cseq} {method}"),
            ("Contact", f"<sip:{self.target.user}@{local[0]}:{local[1]}>"),
            ("User-Agent", USER_AGENT),
            *extra,
        ]
        if body:
            headers.append(("Content-Type", "application/sdp"))
        return SipMessage(f"{method} {uri} SIP/2.0", headers, body)

    async def _transact(self, method, uri=None, extra=(), body="", timeout=SIP_TIMEOUT_S):
        """Send a request (resending until answered) and return its final response."""
        self._cseq += 1
        branch = f"z9hG4bK{secrets.token_hex(8)}"
        request = self._request(method, uri or self.uri, self._cseq, branch, extra, body)
        if method == "INVITE":
            self._invite = (request, branch)
        deadline = time.perf_counter() + timeout
        answered = False
        while time.perf_counter() < deadline:
            if not answered:
                self._sip.sendto(request.encode())
            try:
                response = await asyncio.wait_for(
                    self._signalling.responses.get(), SIP_RETRANSMIT_S
                )
            except TimeoutError:
                continue
            if response.header("CSeq") != f"{self._cseq} {method}":
                continue
            if response.status and response.status < 200:
                answered = True  # ringing: stop resending, wait for the final answer
                continue
            return response
        raise TimeoutError(f"No answer to {method} from {self.target.host}:{self.target.port}")

    def _ack(self, response: SipMessage) -> None:
        """Acknowledge a final answer to the INVITE (same CSeq number, method ACK)."""
        cseq = int((response.header("CSeq") or "1").split()[0])
        if response.status == 200:
            branch = f"z9hG4bK{secrets.token_hex(8)}"  # a 2xx ACK is a new transaction
            uri = re.search(r"<([^>]+)>", response.header("Contact") or "")
            ack = self._request("ACK", uri[1] if uri else self.uri, cseq, branch)
        else:
            # A failure is acknowledged inside the INVITE's own transaction, to its To tag.
            _, branch = self._invite
            ack = self._request("ACK", self.uri, cseq, branch)
            ack.headers = [
                (key, response.header("To") or value) if key == "To" else (key, value)
                for key, value in ack.headers
            ]
        self._sip.sendto(ack.encode())

    async def _send_audio(self) -> None:
        """A packet every 20 ms: the queued line if there is one, silence otherwise."""
        sequence, stamp, ssrc = (
            secrets.randbelow(65536),
            secrets.randbelow(2**32),
            secrets.randbits(32),
        )
        start, sent = time.perf_counter(), 0
        position = 0
        while True:
            wait = start + sent * PACKET_S - time.perf_counter()
            if wait > 0:
                await asyncio.sleep(wait)
            if self._pending:
                chunk = self._pending.popleft()
                if not self._pending and self._done is not None and not self._done.done():
                    self._done.set_result(time.perf_counter())
            else:
                chunk = np.zeros(PACKET_SAMPLES, dtype=np.int16)
            if self.background is not None:
                noise = np.take(
                    self.background, range(position, position + PACKET_SAMPLES), mode="wrap"
                )
                position = (position + PACKET_SAMPLES) % len(self.background)
                chunk = np.clip(chunk.astype(np.int32) + noise, -32768, 32767).astype(np.int16)
            header = bytes([0x80, (0x80 if sent == 0 else 0) | PCMU])
            header += (sequence & 0xFFFF).to_bytes(2, "big") + (stamp & 0xFFFFFFFF).to_bytes(
                4, "big"
            )
            self._rtp.sendto(header + ssrc.to_bytes(4, "big") + ulaw_encode(chunk), self._media_to)
            sequence, stamp, sent = sequence + 1, stamp + PACKET_SAMPLES, sent + 1


_ECHOED = {"via", "v", "from", "f", "to", "t", "call-id", "i", "cseq"}


def _tag_of(header: str) -> str:
    match = re.search(r";\s*tag=([^;>\s]+)", header)
    return match[1] if match else ""


def _route_to(host: str) -> str:
    """This machine's address on the route to `host`."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((host, 9))
        return probe.getsockname()[0]


async def place_phone_call(
    target: Target,
    lines: list[str],
    audio: dict[str, np.ndarray],
    background: np.ndarray | None = None,
) -> list[dict]:
    """bench.caller's call, over the phone: the same lines, sent as 8 kHz mu-law."""
    phone_audio = {line: to_phone(audio[line]) for line in lines}
    call = PhoneCall(target, background=None if background is None else to_phone(background))
    await call.dial()
    try:
        return await converse(
            call.say, call.ear, lines, phone_audio, PHONE_RATE, connected=lambda: call.up
        )
    finally:
        await call.hang_up()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--host", default="127.0.0.1", help="Asterisk's address")
    parser.add_argument("--port", type=int, default=5060)
    parser.add_argument("--number", default="2000", help="the bank's number on Asterisk")
    parser.add_argument("--user", default="bench")
    parser.add_argument("--password", default="tellerline")
    parser.add_argument("--turns", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--background-db", type=float)
    parser.add_argument("--script", type=Path, help="scripted calls (see bench.caller)")
    args = parser.parse_args()
    target = Target(args.host, args.port, args.number, args.user, args.password)

    async def place(lines, audio, background):
        return await place_phone_call(target, lines, audio, background)

    asyncio.run(run_calls(args, place=place, bench="phone"))


if __name__ == "__main__":
    main()
