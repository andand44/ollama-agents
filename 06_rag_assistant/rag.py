"""
Ядро RAG-системы: чанкинг, эмбеддинги, векторный поиск.
"""

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import ollama
import pickle


# --- Конфигурация ---
EMBED_MODEL = 'nomic-embed-text'
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
TOP_K = 3


@dataclass
class Chunk:
    """Один фрагмент текста с эмбеддингом и метаданными."""
    text: str
    embedding: list[float]
    source: str = ''
    chunk_id: int = 0


@dataclass
class RAGStore:
    """Хранилище чанков всех загруженных документов."""
    chunks: list[Chunk] = field(default_factory=list)

    def clear(self) -> None:
        self.chunks.clear()

    def add_text(self, text: str, source: str = '') -> int:
        """Разбивает текст на чанки, создаёт эмбеддинги, добавляет в хранилище."""
        pieces = split_into_chunks(text, CHUNK_SIZE, CHUNK_OVERLAP)
        for i, piece in enumerate(pieces):
            embedding = get_embedding(piece)
            self.chunks.append(
                Chunk(text=piece, embedding=embedding, source=source, chunk_id=i)
            )
        return len(pieces)

    def add_file(self, path: Path) -> int:
        """Загружает файл и добавляет его в хранилище."""
        text = path.read_text(encoding='utf-8')
        return self.add_text(text, source=path.name)

    def search(self, query: str, top_k: int = TOP_K) -> list[tuple[float, Chunk]]:
        """Находит top_k наиболее похожих чанков на запрос."""
        if not self.chunks:
            return []

        query_vec = get_embedding(query)
        scored = [
            (cosine_similarity(query_vec, chunk.embedding), chunk)
            for chunk in self.chunks
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]


# --- Вспомогательные функции ---

def get_embedding(text: str) -> list[float]:
    """Получает вектор эмбеддинга через Ollama."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response['embedding']


def split_into_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Режет текст на чанки с перекрытием."""
    text = re.sub(r'\s+', ' ', text).strip()

    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Косинусное сходство двух векторов (от -1 до 1)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


INDEX_PATH = Path(__file__).parent / "index.pkl"


def save_index(store: 'RAGStore', path: Path = INDEX_PATH) -> None:
    """Сохраняет индекс на диск (pickle)."""
    with open(path, 'wb') as f:
        pickle.dump(store.chunks, f)


def load_index(path: Path = INDEX_PATH) -> 'RAGStore | None':
    """Загружает индекс с диска. Возвращает None, если файла нет."""
    if not path.exists():
        return None

    with open(path, 'rb') as f:
        chunks = pickle.load(f)

    store = RAGStore()
    store.chunks = chunks
    return store