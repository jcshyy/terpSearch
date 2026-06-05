from __future__ import annotations

import os

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class TextEmbedder:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.model = None
        self._load_error: Exception | None = None

    def _load_model(self):
        if self.model is not None:
            return self.model
        if self._load_error is not None:
            raise RuntimeError("Semantic model unavailable") from self._load_error

        from sentence_transformers import SentenceTransformer

        allow_download = os.getenv("TERPSEARCH_ALLOW_MODEL_DOWNLOAD", "").lower() in {
            "1",
            "true",
            "yes",
        }

        try:
            if allow_download:
                self.model = SentenceTransformer(self.model_name)
            else:
                # Default to local-only loading so search stays responsive when
                # the Hugging Face model is not already cached on the machine.
                self.model = SentenceTransformer(
                    self.model_name,
                    local_files_only=True,
                )
        except Exception as exc:
            self._load_error = exc
            raise RuntimeError(
                "Semantic model unavailable. Set TERPSEARCH_ALLOW_MODEL_DOWNLOAD=1 "
                "to let the app download it, or keep using BM25-only search."
            ) from exc

        return self.model

    def encode(self, texts):
        model = self._load_model()
        return np.array(
            model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        )
