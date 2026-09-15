"""Sentence embeddings on the CPU: BAAI/bge-small-en-v1.5 on ONNX Runtime.

Uses the ONNX export and tokenizer from the model repository directly, so no extra runtime
(PyTorch, sentence-transformers) is needed.
"""

from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import snapshot_download
from tokenizers import Tokenizer

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
MODEL_FILES = ["onnx/model.onnx", "tokenizer.json", "config.json"]
MAX_TOKENS = 64  # caller turns are short; longer ones keep their first 64 tokens


class Embedder:
    """Unit-length sentence vectors, so a dot product is cosine similarity."""

    def __init__(self, repo_id: str = EMBEDDING_MODEL, threads: int = 2):
        path = Path(snapshot_download(repo_id, allow_patterns=MODEL_FILES))
        self._tokenizer = Tokenizer.from_file(str(path / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self._tokenizer.enable_padding()
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        self._session = ort.InferenceSession(
            str(path / "onnx" / "model.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {tensor.name for tensor in self._session.get_inputs()}

    def embed(self, texts: list[str]) -> np.ndarray:
        encodings = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        feeds = {
            "input_ids": input_ids,
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
        }
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(input_ids)
        hidden = self._session.run(None, feeds)[0]
        # bge models use the [CLS] token as the sentence embedding.
        vectors = hidden[:, 0]
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
