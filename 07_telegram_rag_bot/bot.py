"""
Telegram-бот с RAG-агентом.

Переиспользует RAG-ядро из проекта 06_rag_assistant:
- тот же индекс (index.pkl)
- ту же генерацию ответов (answer.py)

Что умеет:
- /start — приветствие
- /stats — информация о базе знаний
- любой текст — задать вопрос RAG-системе
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
import logging

logging.basicConfig(level=logging.INFO)

WORKER_URL = "https://telegram-api-proxy.andand44-telegram.workers.dev"


# ── Загружаем переменные окружения из .env ──
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не найден в .env")


# ── Импортируем RAG-ядро из проекта 06 ──
RAG_PROJECT = Path(__file__).parent.parent / "06_rag_assistant"
sys.path.insert(0, str(RAG_PROJECT))

from indexer import get_or_build_index   # noqa: E402
from answer import generate_answer       # noqa: E402


# ── Глобальное состояние ──
STORE = None


# ── Инициализация бота ──
session = AiohttpSession(api=TelegramAPIServer.from_base(WORKER_URL))
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()


def log(section: str, message: str) -> None:
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{section:8}] {message}")


# ── Хэндлеры ──

@dp.message(Command("start"))
async def cmd_start(message: Message):
    log("BOT", f"/start от @{message.from_user.username or message.from_user.id}")
    await message.answer(
        "👋 Привет! Я — RAG-ассистент по базе знаний о ML и IT.\n\n"
        "Задай мне любой вопрос — я найду ответ в 1292 фрагментах "
        "из 19 статей Wikipedia.\n\n"
        "Команды:\n"
        "• /stats — информация о базе знаний\n"
        "• /help — эта справка\n\n"
        "Примеры вопросов:\n"
        "• Что такое нейронная сеть?\n"
        "• В чём разница между CBoW и Skip-gram?\n"
        "• Как работает градиентный спуск?"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    log("BOT", f"/stats от @{message.from_user.username or message.from_user.id}")

    if STORE is None:
        await message.answer("⏳ Индекс ещё загружается...")
        return

    files = sorted(set(c.source for c in STORE.chunks))
    await message.answer(
        f"📊 <b>База знаний</b>\n\n"
        f"• Чанков: <b>{len(STORE.chunks)}</b>\n"
        f"• Файлов: <b>{len(files)}</b>\n"
        f"• Модель эмбеддингов: nomic-embed-text\n"
        f"• Модель генерации: qwen2.5:3b",
        parse_mode="HTML"
    )


@dp.message(F.text)
async def handle_question(message: Message):
    """Обрабатывает любой текст как вопрос к RAG."""
    query = message.text.strip()

    if not query:
        return

    log("BOT", f"Вопрос от @{message.from_user.username or message.from_user.id}: {query[:60]}")

    # Отправляем "печатает..."
    await bot.send_chat_action(message.chat.id, "typing")

    if STORE is None:
        await message.answer("⏳ Индекс загружается, попробуйте через минуту.")
        return

    # ── Поиск релевантных чанков ──
    results = STORE.search(query, top_k=3)

    if not results:
        await message.answer("🔍 Ничего не найдено в базе знаний.")
        return

    # ── Генерируем ответ ──
    top_score = results[0][0]
    log("BOT", f"Top score: {top_score:.3f}")

    chunks = [chunk for _, chunk in results]
    answer = generate_answer(query, chunks)

    # ── Форматируем источники ──
    sources_lines = []
    for score, chunk in results:
        sources_lines.append(f"• {chunk.source} (score: {score:.3f})")
    sources = "\n".join(sources_lines)

    # ── Отправляем ответ ──
    text = (
        f"{answer}\n\n"
        f"📚 <b>Источники:</b>\n{sources}"
    )

    # Telegram ограничивает сообщение 4096 символами
    if len(text) > 4000:
        text = text[:4000] + "..."

    await message.answer(text, parse_mode="HTML")


# ── Точка входа ──

async def main():
    global STORE

    log("INIT", "Загружаем RAG-индекс...")
    STORE = get_or_build_index()
    log("INIT", f"Готово: {len(STORE.chunks)} чанков")

    log("INIT", "Запускаем Telegram-бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())