"""Kokoro-82M on Apple Silicon: the MLX acoustic model fed with espeak-ng phonemes.

mlx-audio's own Kokoro pipeline turns text into phonemes with misaki, whose English module
imports PyTorch. kokoro-onnx already ships espeak-ng phonemisation, the same front end
Pipecat's KokoroTTSService uses, so text goes through that and only the acoustic model runs
on MLX. On the MacBook Air M5 this is about four times faster than ONNX Runtime on the CPU.
"""

from pathlib import Path

import mlx.core as mx
import numpy as np
from huggingface_hub import snapshot_download
from kokoro_onnx.tokenizer import Tokenizer
from kokoro_onnx.trim import trim
from mlx_audio.tts.models.kokoro.voice import load_voice_tensor
from mlx_audio.tts.utils import load_model

from tellerline.tts.phonemes import split_phonemes

SAMPLE_RATE = 24_000
# Only what inference needs: config, weights and voice packs (not the .pt voices or samples).
MODEL_FILES = ["*.json", "*.safetensors"]


class KokoroMLX:
    """Synthesise British English speech with Kokoro on the GPU, one sentence at a time."""

    def __init__(self, repo_id: str, lang: str = "en-gb"):
        self._path = Path(snapshot_download(repo_id, allow_patterns=MODEL_FILES))
        self._model = load_model(self._path)
        self._tokenizer = Tokenizer()
        self._lang = lang
        self._voice_packs: dict[str, mx.array] = {}

    @property
    def voices(self) -> list[str]:
        return sorted(p.stem for p in (self._path / "voices").glob("*.safetensors"))

    def phonemize(self, text: str) -> str:
        return self._tokenizer.phonemize(text, self._lang)

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray:
        """Return 24 kHz mono float32 audio with leading and trailing silence removed.

        Kokoro pads its output with about 0.3 s of silence; left in, the caller hears it
        as extra delay before every sentence.
        """
        pieces = [self._render(ps, voice, speed) for ps in split_phonemes(self.phonemize(text))]
        if not pieces:
            return np.zeros(0, dtype=np.float32)
        audio, _ = trim(np.concatenate(pieces))
        return audio

    def _render(self, phonemes: str, voice: str, speed: float) -> np.ndarray:
        pack = self._voice_pack(voice)
        output = self._model(phonemes, pack[len(phonemes) - 1], speed, return_output=True)
        return np.array(output.audio, dtype=np.float32).reshape(-1)

    def _voice_pack(self, voice: str) -> mx.array:
        if voice not in self._voice_packs:
            path = self._path / "voices" / f"{voice}.safetensors"
            if not path.exists():
                raise ValueError(f"Unknown Kokoro voice {voice!r}; available: {self.voices}")
            self._voice_packs[voice] = load_voice_tensor(str(path))
        return self._voice_packs[voice]
