from sentence_transformers import SentenceTransformer
import numpy as np
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
class TextEmbedder:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = SentenceTransformer(model_name)
    def encode(self, texts):
        return np.array(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False))
