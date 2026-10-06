"""Silero VAD that listens for the caller, not the room.

Pipecat confirms speech when Silero is confident and the audio is loud enough, measuring loudness
(ITU-R BS.1770) over the last 400 ms and smoothing it, against a fixed threshold (0.65, about
-45 LUFS). The long window made the VAD slow to hear a caller: half a second from their first word
to confirmed speech, and 0.16 s just to notice them carry on after a pause. The fixed threshold
lets a conversation in the room through as the caller: with one 20 dB below the caller, the VAD
started on the room alone in half of the benchmark's lines.

This VAD gates Silero's verdict on the caller instead. A frame is the caller's voice when Silero
is confident and the last ``CALLER_WINDOW_S`` of audio is above ``CALLER_FLOOR_DBFS`` (where
Pipecat's threshold was) and within ``CALLER_MARGIN_DB`` of the caller's speech level: the median
level of their confirmed speech over the last ``CALLER_MEMORY_S`` while the agent was silent.

Simulated over the benchmark's 99 caller lines (D-032): in a quiet room it confirms a caller 0.13 s
sooner and notices them carry on after a pause in 0.06 s instead of 0.16 s, cutting nobody off
more often than before; with a conversation 20 dB below the caller it starts on the room alone in
22 lines instead of 49 and lets go of the caller's turn 0.35 s after their last word (p90) instead
of 0.70 s. With the room 15 dB below, level alone can't tell its voices from the caller's.
"""

from collections import deque

import numpy as np
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams, VADState

from tellerline.config import (
    CALLER_FLOOR_DBFS,
    CALLER_MARGIN_DB,
    CALLER_MEMORY_S,
    CALLER_WINDOW_S,
)

# Silero judges 32 ms frames (512 samples at 16 kHz, 256 at 8 kHz).
FRAME_S = 0.032
# A second of confirmed speech before the caller's level is trusted.
MIN_LEVEL_FRAMES = round(1.0 / FRAME_S)


class CallerVAD(SileroVADAnalyzer):
    """Silero VAD gated on the caller's own speech level (``caller_gate``), or on Pipecat's
    volume threshold without it."""

    def __init__(
        self,
        *,
        params: VADParams,
        caller_gate: bool = True,
        window_s: float = CALLER_WINDOW_S,
        margin_db: float = CALLER_MARGIN_DB,
        floor_dbfs: float = CALLER_FLOOR_DBFS,
        memory_s: float = CALLER_MEMORY_S,
        **kwargs,
    ):
        if caller_gate:
            params = params.model_copy(update={"min_volume": 0.0})  # the caller gate replaces it
        super().__init__(params=params, **kwargs)
        self._caller_gate = caller_gate
        self._margin_db = margin_db
        self._floor_dbfs = floor_dbfs
        self._energies: deque[float] = deque(maxlen=max(1, round(window_s / FRAME_S)))
        self._caller_levels: deque[float] = deque(maxlen=round(memory_s / FRAME_S))
        # The agent's own voice coming back must not teach the VAD the caller's level.
        self._agent_speaking = False

    def voice_confidence(self, buffer: bytes) -> float:
        confidence = float(np.squeeze(super().voice_confidence(buffer)))
        if not self._caller_gate:
            return confidence
        samples = np.frombuffer(buffer, dtype=np.int16).astype(np.float32) / 32768
        self._energies.append(float(np.mean(samples * samples)))
        level = 10 * np.log10(np.mean(self._energies) + 1e-12)
        speaking = self._vad_state == VADState.SPEAKING
        if speaking and confidence >= self.params.confidence and not self._agent_speaking:
            self._caller_levels.append(level)
        return confidence if level >= self.threshold_dbfs() else 0.0

    def set_agent_speaking(self, speaking: bool) -> None:
        self._agent_speaking = speaking

    def threshold_dbfs(self) -> float:
        """The level below which nothing is the caller's voice."""
        if len(self._caller_levels) < MIN_LEVEL_FRAMES:
            return self._floor_dbfs
        return max(self._floor_dbfs, float(np.median(self._caller_levels)) - self._margin_db)
