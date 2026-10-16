"""
Общие утилиты для всех агентов.
"""

from datetime import datetime

import ollama

from config import MODEL_NAME, NUM_CTX, TEMPERATURE


def debug_log(section: str, message: str) -> None:
    """Единая точка для отладочных сообщений с временной меткой."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{section:10}] {message}")


def print_separator(title: str = "") -> None:
    """Печатает визуальный разделитель блоков."""
    print("\n" + "═" * 70)
    if title:
        print(f"  {title}")
        print("═" * 70)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Единая функция вызова LLM — все агенты используют её.

    Если завтра захочешь поменять модель или добавить логирование —
    меняешь в одном месте, а не в каждом агенте.
    """
    debug_log("LLM", f"Запрос к {MODEL_NAME} ({len(system_prompt) + len(user_prompt)} символов)")

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        options={'num_ctx': NUM_CTX, 'temperature': TEMPERATURE},
    )
    return response.message.content