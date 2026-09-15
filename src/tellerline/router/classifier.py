"""Nearest-example intent classifier over sentence embeddings.

Each intent is represented by example sentences. A caller turn scores each intent by its
similarity to that intent's closest examples; the classifier is confident only when the best
intent clears a minimum similarity and beats the runner-up by a margin. Unconfident turns let
the session keep the current task (see ``tellerline.router.session``).
"""

from dataclasses import dataclass

import numpy as np

from tellerline.router.embedder import Embedder

TOP_K = 3  # average of the closest few examples is steadier than the single closest one


@dataclass(frozen=True)
class Prediction:
    intent: str
    score: float
    margin: float
    confident: bool
    scores: dict[str, float]


class IntentClassifier:
    def __init__(
        self,
        embedder: Embedder,
        examples: dict[str, list[str]],
        # Tuned on the dev split by bench.router: no confident mistakes, most confident turns.
        min_score: float = 0.60,
        min_margin: float = 0.04,
    ):
        self._embedder = embedder
        self.min_score = min_score
        self.min_margin = min_margin
        self._intents = list(examples)
        self._vectors = {intent: embedder.embed(texts) for intent, texts in examples.items()}

    @property
    def intents(self) -> list[str]:
        return list(self._intents)

    def predict(self, text: str) -> Prediction:
        return self.score_vector(self._embedder.embed([text])[0])

    def score_vector(self, vector: np.ndarray) -> Prediction:
        """Classify an already embedded turn (lets a benchmark sweep thresholds cheaply)."""
        scores = {}
        for intent, vectors in self._vectors.items():
            similarities = np.sort(vectors @ vector)[::-1]
            scores[intent] = float(similarities[:TOP_K].mean())
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        (best, best_score), (_, second_score) = ranked[0], ranked[1]
        margin = best_score - second_score
        confident = best_score >= self.min_score and margin >= self.min_margin
        return Prediction(best, best_score, margin, confident, scores)
