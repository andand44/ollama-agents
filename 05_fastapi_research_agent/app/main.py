"""
Веб-интерфейс для мультиагентной системы редактирования текста.
"""
import ollama
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline import improve_text


# --- Инициализация ---
app = FastAPI(title="Multi-Agent Text Editor")
MAX_TEXT_LENGTH = 5000


# --- Модели данных ---

class TextInput(BaseModel):
    text: str


# --- Эндпоинты ---

@app.get("/")
async def index():
    """Главная страница."""
    html_path = Path(__file__).parent.parent / "frontend" / "index.html"
    return FileResponse(html_path)


@app.post("/api/improve")
async def api_improve(data: TextInput):
    """Прогоняет текст через всех 4 агентов."""
    text = data.text.strip()

    if not text:
        raise HTTPException(400, "Текст пустой")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(400, f"Текст слишком большой. Максимум: {MAX_TEXT_LENGTH}")

    try:
        result = improve_text(text)
        return {
            "original": result['original'],
            "critique": result['critique'],
            "improved": result['improved'],
            "edits": result['applied_edits'],
            "skipped": result['skipped_edits'],
            "facts_report": result['facts']['report'],
            "facts_count": len(result['facts']['claims']),
            "verdict": result['verdict'],
        }
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки: {e}")