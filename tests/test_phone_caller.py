import numpy as np

from bench.phone import (
    PCMU,
    SipMessage,
    _Media,
    digest,
    parse_challenge,
    parse_message,
    parse_sdp,
    sdp_offer,
    to_phone,
    ulaw_decode,
    ulaw_encode,
)


def test_mu_law_matches_g711_at_the_extremes():
    assert ulaw_encode(np.array([0, -1, 32767, -32768], dtype=np.int16)) == bytes(
        [0xFF, 0x7F, 0x80, 0x00]
    )
    assert ulaw_decode(bytes([0xFF, 0x7F])).tolist() == [0, 0]


def test_mu_law_round_trip_keeps_the_signal():
    pcm = (np.sin(np.linspace(0, 40, 8000)) * np.linspace(100, 30000, 8000)).astype(np.int16)
    decoded = ulaw_decode(ulaw_encode(pcm)).astype(np.int32)
    error = np.abs(decoded - pcm.astype(np.int32))
    # mu-law keeps about 4 bits of mantissa: the error is a few per cent of the sample.
    assert np.all(error <= np.abs(pcm.astype(np.int32)) / 16 + 8)


def test_caller_lines_are_resampled_to_the_phone_rate():
    one_second = (np.sin(np.arange(48_000) / 9) * 10_000).astype(np.int16)
    assert len(to_phone(one_second)) == 8_000


def test_digest_answers_the_rfc_2617_example():
    challenge = parse_challenge(
        'Digest realm="testrealm@host.com", qop="auth,auth-int", '
        'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", opaque="5ccc069c403ebaf9f0171e9517f40e41"'
    )
    assert challenge["realm"] == "testrealm@host.com"
    assert challenge["qop"] == "auth,auth-int"
    header = digest("GET", "/dir/index.html", "Mufasa", "Circle Of Life", challenge, "0a4f113b")
    assert 'response="6629fae49393a05397450978507c4ef1"' in header
    assert 'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in header


def test_asterisk_challenges_parse():
    challenge = parse_challenge(
        'Digest realm="asterisk",nonce="1759660000/7a3e",opaque="2b5e",algorithm=MD5,qop="auth"'
    )
    assert challenge == {
        "realm": "asterisk",
        "nonce": "1759660000/7a3e",
        "opaque": "2b5e",
        "algorithm": "MD5",
        "qop": "auth",
    }


def test_sip_messages_parse_and_encode():
    data = (
        b"SIP/2.0 401 Unauthorized\r\n"
        b"Via: SIP/2.0/UDP 127.0.0.1:50000;rport=50000;branch=z9hG4bK1\r\n"
        b"f: <sip:bench@127.0.0.1>;tag=ab12\r\n"
        b"To: <sip:100@127.0.0.1>;tag=cd34\r\n"
        b"Call-ID: 1234@tellerline\r\n"
        b"CSeq: 1 INVITE\r\n"
        b'WWW-Authenticate: Digest realm="asterisk",nonce="n"\r\n'
        b"Content-Length: 0\r\n\r\n"
    )
    message = parse_message(data)
    assert message.status == 401
    assert message.method is None
    assert message.header("From") == "<sip:bench@127.0.0.1>;tag=ab12"  # compact form
    assert message.header("cseq") == "1 INVITE"
    request = SipMessage("BYE sip:100@127.0.0.1 SIP/2.0", [("CSeq", "3 BYE")], "")
    assert parse_message(request.encode()).method == "BYE"
    assert b"Content-Length: 0\r\n\r\n" in request.encode()


def test_sdp_offers_mu_law_and_reads_the_answer():
    offer = sdp_offer("127.0.0.1", 40000, 1)
    assert f"m=audio 40000 RTP/AVP {PCMU}" in offer
    assert "a=rtpmap:0 PCMU/8000" in offer
    answer = "v=0\r\nc=IN IP4 172.17.0.2\r\nt=0 0\r\nm=audio 10004 RTP/AVP 0\r\n"
    assert parse_sdp(answer) == ("172.17.0.2", 10004)
    assert parse_sdp("v=0\r\n") == (None, None)


class Ear:
    def __init__(self):
        self.heard = []

    def hear(self, samples, now):
        self.heard.append(samples)


def test_rtp_packets_reach_the_ear_decoded():
    ear = Ear()
    media = _Media(ear)
    payload = ulaw_encode(np.full(160, 8000, dtype=np.int16))
    header = bytes([0x80, PCMU]) + bytes(10)
    media.datagram_received(header + payload, ("127.0.0.1", 10000))
    # With one contributing source and a one-word header extension.
    extended = bytes([0x91, PCMU]) + bytes(10) + bytes(4) + bytes([0xBE, 0xDE, 0, 1]) + bytes(4)
    media.datagram_received(extended + payload, ("127.0.0.1", 10000))
    media.datagram_received(bytes([0x80, 101]) + bytes(10) + payload, ("127.0.0.1", 10000))
    assert len(ear.heard) == 2
    for samples in ear.heard:
        assert len(samples) == 160
        assert abs(float(samples.mean()) - 8000 / 32768) < 0.01
