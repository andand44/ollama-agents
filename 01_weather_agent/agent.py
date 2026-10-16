"""
Weather Agent — базовый пример tool calling на Ollama.

Агент умеет: получить погоду, посчитать математику, показать время.
Демонстрирует, как LLM выбирает инструмент из описания JSON Schema
и как обрабатывать нестабильный формат аргументов от маленьких моделей.
"""

import json
from datetime import datetime

import ollama


# --- Конфигурация ---
MODEL_NAME = 'qwen2.5:3b'
NUM_CTX = 2048
TEMPERATURE = 0


# --- Инструменты ---

def get_current_weather(city: str) -> str:
    """Возвращает погоду в указанном городе (заглушка)."""
    weather_data = {
        "Москва": "Облачно, +15°C",
        "Лондон": "Дождь, +12°C",
        "Нью-Йорк": "Солнечно, +22°C",
    }
    return weather_data.get(city, f"Нет данных о погоде для города {city}")


def calculate(expression: str) -> str:
    """Вычисляет математическое выражение.

    ВНИМАНИЕ: eval() небезопасен для продакшена — только для обучения.
    """
    try:
        result = eval(expression)
        return f"Результат: {result}"
    except Exception as e:
        return f"Ошибка вычисления: {e}"


def get_current_time() -> str:
    """Возвращает текущее время в формате ЧЧ:ММ:СС."""
    try:
        result = datetime.now().strftime("%H:%M:%S")
        return f"Текущее время: {result}"
    except Exception as e:
        return f"Ошибка получения времени: {e}"


# --- Защита от галлюцинаций ---

def extract_city(arguments: dict) -> str | None:
    """Извлекает название города из аргументов, присланных моделью.

    Маленькие модели иногда оборачивают значение в словарь
    вместо простой строки. Эта функция разбирает оба формата.
    """
    if 'city' not in arguments:
        return None

    value = arguments['city']
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        for key in ('value', 'name', 'city', 'text'):
            if key in value and isinstance(value[key], str):
                return value[key]
        for v in value.values():
            if isinstance(v, str):
                return v

    return None


# --- Схема инструментов для модели ---

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'get_current_weather',
            'description': 'Получить текущую погоду в городе',
            'parameters': {
                'type': 'object',
                'properties': {
                    'city': {
                        'type': 'string',
                        'description': 'Название города, например, Москва',
                    },
                },
                'required': ['city'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'calculate',
            'description': 'Вычислить математическое выражение, например, 2+2*2',
            'parameters': {
                'type': 'object',
                'properties': {
                    'expression': {
                        'type': 'string',
                        'description': 'Математическое выражение',
                    },
                },
                'required': ['expression'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_current_time',
            'description': 'Получить текущее время. Не требует аргументов.',
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
    """Запускает агента: отправляет запрос, выполняет инструменты, возвращает ответ."""
    print(f"\n--- Пользователь: {user_message} ---")

    messages = [
        {
            'role': 'system',
            'content': (
                'Ты — полезный ассистент. Отвечай только на русском языке. '
                'В аргументах инструментов передавай только конкретные значения.'
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

    # Сохраняем ответ модели с tool_calls в историю
    messages.append(response.message)

    # Выполняем все запрошенные инструменты
    for tool_call in response.message.tool_calls:
        function_name = tool_call.function.name
        arguments = tool_call.function.arguments

        if arguments:
            print(f"🤖 Вызов: {function_name}({json.dumps(arguments, ensure_ascii=False)})")
        else:
            print(f"🤖 Вызов: {function_name}")

        result = "Ошибка: не удалось обработать аргументы"

        if function_name == 'get_current_weather':
            city = extract_city(arguments)
            if city and city != 'Название города' and 'description' not in city:
                result = get_current_weather(city)
            else:
                result = "Ошибка: модель не смогла корректно указать город."

        elif function_name == 'calculate':
            expression = arguments.get('expression', '2+2')
            if isinstance(expression, dict):
                expression = expression.get('value', '2+2')
            result = calculate(expression)

        elif function_name == 'get_current_time':
            result = get_current_time()

        print(f"🔧 Результат: {result}")

        messages.append({
            'role': 'tool',
            'content': result,
            'tool_name': function_name,
        })

    # Финальный запрос — модель формулирует ответ на основе данных инструментов
    final_response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        options={'num_ctx': NUM_CTX, 'temperature': TEMPERATURE},
    )

    print(f"🤖 Финальный ответ: {final_response.message.content}")
    return final_response.message.content


if __name__ == "__main__":
    run_agent("Сколько сейчас времени?")
    run_agent("Какая погода в Лондоне и Москве?")
    run_agent("Сколько будет 25 * 4 + 10?")