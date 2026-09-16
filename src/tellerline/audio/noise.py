"""RNNoise noise suppression as a Pipecat input audio filter.

RNNoise (Xiph, BSD-3-Clause) is a small recurrent network that removes steady and
non-speech noise (fans, traffic, keyboards, hum) in real time on the CPU. It runs on the
caller's audio before voice activity detection, so noise no longer looks like speech.

Pipecat ships an RNNoise filter, but it goes through pyrnnoise's high-level API, which is broken
against current ``audiolab`` releases. This filter calls the RNNoise C library directly through
pyrnnoise's ctypes binding.
"""

import ctypes

import numpy as np
from pipecat.audio.filters.base_audio_filter import BaseAudioFilter
from pipecat.audio.resamplers.soxr_stream_resampler import SOXRStreamAudioResampler
from pipecat.frames.frames import FilterControlFrame, FilterEnableFrame

RNNOISE_RATE = 48_000


class RNNoiseSuppressor(BaseAudioFilter):
    def __init__(self) -> None:
        self._enabled = True
        self._sample_rate = 0
        self._state = None
        self._lib = None
        self._frame_size = 480
        self._pending = np.zeros(0, dtype=np.float32)
        self._resample_in = SOXRStreamAudioResampler()
        self._resample_out = SOXRStreamAudioResampler()

    async def start(self, sample_rate: int):
        from pyrnnoise import rnnoise

        self._sample_rate = sample_rate
        self._lib = rnnoise.lib
        self._frame_size = rnnoise.FRAME_SIZE
        self._state = self._lib.rnnoise_create(None)

    async def stop(self):
        if self._state is not None and self._lib is not None:
            self._lib.rnnoise_destroy(self._state)
        self._state = None

    async def process_frame(self, frame: FilterControlFrame):
        if isinstance(frame, FilterEnableFrame):
            self._enabled = frame.enable

    async def filter(self, audio: bytes) -> bytes:
        if not self._enabled or self._state is None or not audio:
            return audio
        pcm = audio
        if self._sample_rate != RNNOISE_RATE:
            pcm = await self._resample_in.resample(audio, self._sample_rate, RNNOISE_RATE)
        # RNNoise works on 10 ms frames of float samples in 16-bit range.
        self._pending = np.concatenate([self._pending, np.frombuffer(pcm, dtype=np.int16)])
        frames = len(self._pending) // self._frame_size
        if frames == 0:
            return b""
        denoised = np.empty(frames * self._frame_size, dtype=np.float32)
        float_ptr = ctypes.POINTER(ctypes.c_float)
        for index in range(frames):
            start = index * self._frame_size
            source = np.ascontiguousarray(self._pending[start : start + self._frame_size])
            target = denoised[start : start + self._frame_size]
            self._lib.rnnoise_process_frame(
                self._state, target.ctypes.data_as(float_ptr), source.ctypes.data_as(float_ptr)
            )
        self._pending = self._pending[frames * self._frame_size :]
        out = np.clip(denoised, -32768, 32767).astype(np.int16).tobytes()
        if self._sample_rate != RNNOISE_RATE:
            out = await self._resample_out.resample(out, RNNOISE_RATE, self._sample_rate)
        return out
