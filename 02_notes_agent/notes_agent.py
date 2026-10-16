"""
Notes Agent — работа с файлами и защита от галлюцинаций.

Агент умеет: сохранять заметки и читать их из файла.
Демонстрирует универсальный санитайзер для нестабильного
формата аргументов от маленьких моделей.
"""

import json
import os

import ollama


# --- Конфигурация ---
MODEL_NAME = 'qwen2.5:3b'
NOTES_FILE = 'notes.txt'
NUM_CTX = 2048
TEMPERATURE = 0


# --- Утилиты ---

def sanitize_to_string(value, default: str = '') -> str:
    """Превращает любое значение в чистую строку.

    Модели иногда возвращают аргументы не как строку, а как словарь,
    список или число. Эта функция рекурсивно извлекает осмысленное
    значение и приводит его к строке.
    """
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float)):
        return str(value)

    if value is None:
        return default

    if isinstance(value, dict):
        for key in ('value', 'text', 'content', 'name', 'result', 'data'):
            if key in value:
                return sanitize_to_string(value[key], default)

        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v.strip()

        return default

    if isinstance(value, (list, tuple)):
        for item in value:
            result = sanitize_to_string(item, default)
            if result:
                return result
        return default

    return str(value).strip() if value else default


# --- Инструменты ---

def save_note(text: str) -> str:
    """Добавляет заметку в конец файла."""
    try:
        with open(NOTES_FILE, 'a', encoding='utf-8') as f:
            f.write(text + '\n')
        return f"Заметка сохранена: {text}"
    except Exception as e:
        return f"Ошибка сохранения: {e}"


def read_notes() -> str:
    """Читает все заметки из файла."""
    try:
        if not os.path.exists(NOTES_FILE):
            return "Заметок пока нет."

        with open(NOTES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return "Заметок пока нет."

        return f"Вот все заметки:\n{content}"
    except Exception as e:
        return f"Ошибка чтения: {e}"


# --- Схема инструментов для модели ---

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'save_note',
            'description': (
                'Сохранить заметку в файл. '
                'В аргумент text передавай ТОЛЬКО суть заметки, без командных слов. '
                'Примеры: "Запомни: купить молоко" → text="купить молоко". '
                '"Запиши позвонить маме" → text="позвонить маме".'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'text': {
                        'type': 'string',
                        'description': 'Суть заметки без слов "запомни", "запиши"',
                    },
                },
                'required': ['text'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_notes',
            'description': (
                'Прочитать ВСЕ сохранённые заметки из файла. '
                'Вызывай ВСЕГДА, когда пользователь спрашивает о заметках. '
                'НИКОГДА не отвечай на такие вопросы без вызова этого инструмента.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
]


# --- Агент ---

def run_agent(user_message: str) -> str:
    """Запускает агента: выполняет инструменты и возвращает финальный ответ."""
    print(f"\n--- Пользователь: {user_message} ---")

    messages = [
        {
            'role': 'system',
            'content': (
                'Ты — ассистент для заметок. Отвечай только на русском языке.\n\n'
                'У тебя есть инструменты, и ты ОБЯЗАН их использовать:\n'
                '- save_note(text) — когда пользователь просит что-то запомнить.\n'
                '- read_notes() — ВСЕГДА, когда пользователь спрашивает о заметках.\n\n'
                'ВАЖНО: у тебя нет собственной памяти. Все заметки хранятся в файле. '
                'На вопросы "что я записал", "покажи заметки" — '
                'ты НИКОГДА не отвечаешь сам. Сначала вызывай read_notes, '
                'получаешь данные и только потом отвечаешь.'
            ),
        },
        {'role': 'user', 'content': user_message},
    ]

    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        tools=TOOLS,
        options={'num_ctx': NUM_CTX, 'temperature': TEMPERATURE},
    )

    if not response.message.tool_calls:
        print(f"🤖 Ответ агента: {response.message.content}")
        return response.message.content

    messages.append(response.message)

    for tool_call in response.message.tool_calls:
        function_name = tool_call.function.name
        arguments = tool_call.function.arguments

        print(f"🤖 Вызов: {function_name}({json.dumps(arguments, ensure_ascii=False)})")

        result = "Ошибка: не удалось обработать аргументы"

        if function_name == 'save_note':
            text = sanitize_to_string(arguments.get('text'), default='')
            if text:
                result = save_note(text)
            else:
                result = "Ошибка: пустая заметка."

        elif function_name == 'read_notes':
            result = read_notes()

        print(f"🔧 Результат: {result}")

        messages.append({
            'role': 'tool',
            'content': result,
            'tool_name': function_name,
        })

    final_response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={'num_ctx': NUM_CTX, 'temperature': TEMPERATURE},
    )

    print(f"🤖 Финальный ответ: {final_response.message.content}")
    return final_response.message.content


if __name__ == "__main__":
    run_agent("Запомни: купить молоко и компот")
    run_agent("Запомни: позвонить маме")
    run_agent("Что я записал?")