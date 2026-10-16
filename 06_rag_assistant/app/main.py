"""
FastAPI-сервер для RAG-ассистента.
Индекс загружается один раз при старте, вопросы — через /api/ask.
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from indexer import get_or_build_index
from answer import generate_answer


# ── Глобальное состояние (индекс живёт между запросами) ──
STATE = {
    'store': None,
    'loaded_at': None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загружаем индекс при старте сервера."""
    print("\n" + "═" * 60)
    print("  Запуск RAG-сервера...")
    print("═" * 60)

    start = time.time()
    STATE['store'] = get_or_build_index()
    STATE['loaded_at'] = time.time()

    print(f"\n✓ Сервер готов: {len(STATE['store'].chunks)} чанков")
    print(f"✓ Время загрузки: {time.time() - start:.2f} сек")
    print("═" * 60 + "\n")

    yield   # здесь сервер работает

    print("\n  Остановка RAG-сервера...")
    STATE['store'] = None


app = FastAPI(title="RAG Document Assistant", lifespan=lifespan)

MAX_QUESTION_LENGTH = 500


class Question(BaseModel):
    query: str
    top_k: int = 3


@app.get("/")
def index():
    """Отдаёт главную HTML-страницу."""
    path = Path(__file__).parent.parent / "frontend" / "index.html"
    return FileResponse(path)


@app.post("/api/ask")
def ask(question: Question):
    """Принимает вопрос, ищет чанки, генерирует ответ."""
    query = question.query.strip()

    if not query:
        raise HTTPException(400, "Пустой вопрос")
    if len(query) > MAX_QUESTION_LENGTH:
        raise HTTPException(400, f"Вопрос слишком длинный (макс {MAX_QUESTION_LENGTH})")

    store = STATE['store']
    if store is None:
        raise HTTPException(503, "Индекс не загружен")

    # ── Поиск ──
    results = store.search(query, top_k=question.top_k)

    if not results:
        return {
            "answer": "Ничего не найдено в базе знаний.",
            "sources": [],
        }

    # ── Генерация ответа ──
    start = time.time()
    answer = generate_answer(query, [chunk for _, chunk in results])
    elapsed = time.time() - start

    return {
        "answer": answer,
        "sources": [
            {
                "score": round(score, 3),
                "file": chunk.source,
                "preview": chunk.text[:150] + "...",
            }
            for score, chunk in results
        ],
        "elapsed": round(elapsed, 1),
    }


@app.get("/api/stats")
def stats():
    """Информация о загруженном индексе."""
    store = STATE['store']
    if store is None:
        return {"loaded": False}

    files = sorted(set(c.source for c in store.chunks))
    return {
        "loaded": True,
        "chunks": len(store.chunks),
        "files": len(files),
        "file_list": files,
        "uptime": round(time.time() - STATE['loaded_at'], 1) if STATE['loaded_at'] else 0,
    }