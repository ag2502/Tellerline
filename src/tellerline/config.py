"""Model choices and runtime settings shared by the agent and the benchmarks."""

from pathlib import Path

# Gemma 4 small models, 4-bit MLX builds. Phase 0 decides which one ships.
LLM_MODELS: dict[str, str] = {
    "e2b": "mlx-community/gemma-4-e2b-it-4bit",
    "e4b": "mlx-community/gemma-4-e4b-it-4bit",
}
LLM_SERVER_HOST = "127.0.0.1"
LLM_SERVER_PORT = 8080
# MLX keeps freed GPU buffers for reuse; uncapped, the cache reached 5.4 GB in the agent and pushed
# the 16 GB Mac into swap. Each MLX process caps its cache at this size.
MLX_CACHE_LIMIT_BYTES = 512 * 1024**2
# Prompt caches the LLM server may keep (one per step prompt and conversation prefix).
LLM_PROMPT_CACHE_BYTES = 1024**3
# Gemma 4 can "think" before answering; on a phone call that is pure latency.
LLM_CHAT_TEMPLATE_ARGS = {"enable_thinking": False}

STT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
STT_SAMPLE_RATE = 16_000
# Time from the end of the caller's speech to Parakeet's transcript at p99: the 0.2 s silence
# the VAD waits for plus under 0.1 s of transcription (live calls, MacBook Air M5), with margin.
# Pipecat assumes 1.0 s for an STT it doesn't know and times turn-end fallbacks from it.
STT_TTFS_P99_S = 0.35
# Audio kept from before the VAD confirms the caller is speaking, so the transcript starts at
# their first word. With the stricter VAD settings below, confirmation comes 0.8-0.9 s after
# speech begins, which left Pipecat's 1 s with no room: on phone audio the first word or two of a
# turn were lost ("I've lost my card" heard as "lost my card").
STT_PRE_ROLL_S = 2.0

# Kokoro on MLX (GPU), fed with espeak-ng phonemes; see tellerline.tts.kokoro_mlx and D-010.
KOKORO_MLX_MODELS: dict[str, str] = {
    "bf16": "mlx-community/Kokoro-82M-bf16",
    "8bit": "mlx-community/Kokoro-82M-8bit",
}
TTS_MLX_VARIANT = "bf16"

# Kokoro via kokoro-onnx, the same files Pipecat's KokoroTTSService downloads. Kept as the
# CPU baseline in the TTS benchmark.
KOKORO_CACHE_DIR = Path.home() / ".cache" / "pipecat" / "kokoro-onnx"
KOKORO_VOICES_PATH = KOKORO_CACHE_DIR / "voices-v1.0.bin"
# Precision variants published alongside the default fp32 model; Phase 0 picks the fastest.
KOKORO_MODEL_FILES = {
    "fp32": "kokoro-v1.0.onnx",
    "fp16": "kokoro-v1.0.fp16.onnx",
    "int8": "kokoro-v1.0.int8.onnx",
}
KOKORO_RELEASE_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
TTS_LANG = "en-gb"
TTS_UK_VOICES = ("bf_emma", "bf_isabella", "bm_george", "bm_lewis")
TTS_DEFAULT_VOICE = "bf_emma"

# D1: 90% of turns must reach first reply audio within this many seconds of the caller
# finishing speaking, measured over 200+ turns on the MacBook Air M5.
LATENCY_TARGET_P90_S = 1.5
# Silence Silero VAD waits for before Smart Turn decides whether the caller has finished.
VAD_STOP_SECS = 0.2
# Stricter than Pipecat's defaults (0.7, 0.2 s, 0.6) so background voices and noise don't count
# as the caller: speech must be more certain, last longer, and be closer to the microphone.
VAD_CONFIDENCE = 0.8
VAD_START_SECS = 0.3
VAD_MIN_VOLUME = 0.65
# While the agent is talking, the caller must say this many words to interrupt it. A cough, a
# door or someone talking in the background shouldn't cut the agent off.
INTERRUPT_MIN_WORDS = 2
# If Smart Turn thinks the caller hasn't finished, how long to wait before answering anyway.
# Pipecat's default is 5 s; on a phone line that silence feels like the call has dropped.
USER_TURN_STOP_TIMEOUT_S = 2.0
# A caller who has given half their identity details ("My customer number is 45127890 ...") is
# usually about to give the rest; the agent holds its reply this long, and a caller who carries
# on cancels it before anything is said over them. It has to cover their pause plus the 0.3 s
# the VAD needs to confirm speech has resumed (VAD_START_SECS).
IDENTITY_HOLD_S = 1.0
