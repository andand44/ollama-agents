import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from dotenv import load_dotenv

load_dotenv()

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_08") # Токен нового бота
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/ask-portfolio" # Production URL из n8n

# Используем Cloudflare Worker (из 7-го урока) для обхода блокировок
WORKER_URL = "https://telegram-api-proxy.andand44-telegram.workers.dev"

# Настройка сессии с прокси
session = AiohttpSession(api=TelegramAPIServer.from_base(WORKER_URL))
bot = Bot(token=TELEGRAM_TOKEN, session=session)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Задай мне вопрос о моих проектах, и n8n найдет ответ.")

@dp.message(F.text)
async def handle_message(message: Message):
    query = message.text.strip()
    await message.answer("⏳ Думаю...")
    
    # Отправляем запрос в n8n
    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(N8N_WEBHOOK_URL, json={"question": query}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    answer = data.get("answer", "n8n не вернул ответ.")
                    await message.answer(answer)
                else:
                    await message.answer(f"Ошибка n8n: статус {resp.status}")
    except Exception as e:
        await message.answer(f"Ошибка соединения с n8n: {e}")

async def main():
    print("Бот запущен. Напиши ему в Telegram.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())