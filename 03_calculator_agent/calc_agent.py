"""
Calculator Agent — многошаговые задачи с памятью переменных.

Агент умеет: считать, сохранять результат под именем, читать и
показывать переменные. Демонстрирует agentic loop — цикл, в котором
модель может вызывать инструменты несколько раз подряд, пока не
решит задачу.

Особенность: calculate() автоматически подставляет значения из MEMORY,
поэтому выражение "total + 100" работает, даже если модель не знает
о существовании переменной total.
"""

import json
import re
from datetime import datetime

import ollama


# --- Конфигурация ---
MODEL_NAME = 'qwen2.5:3b'
NUM_CTX = 2048
TEMPERATURE = 0
MAX_ITERATIONS = 10


# --- Состояние агента ---
# Глобальная память переменных. Аналог const MEMORY = {} в JS.
MEMORY: dict = {}


# --- Отладочные утилиты ---

def debug_log(section: str, message: str) -> None:
    """Единая точка для отладочных сообщений с временной меткой."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{section:8}] {message}")


def print_separator(title: str = "") -> None:
    """Печатает визуальный разделитель для блоков вывода."""
    print("\n" + "=" * 65)
    if title:
        print(f"  {title}")
        print("=" * 65)


# --- Инструменты ---

def calculate(expression: str) -> str:
    """Вычисляет математическое выражение с подстановкой переменных из MEMORY.

    Перед вычислением все имена переменных заменяются на их значения.
    Это позволяет модели писать "total + 100", не зная о существовании MEMORY.
    """
    debug_log("TOOL", f"calculate() → {expression!r}")

    for var_name, var_value in MEMORY.items():
        # \b — граница слова, чтобы 'a' не заменялось внутри 'abc'
        expression = re.sub(
            rf'\b{re.escape(var_name)}\b',
            str(var_value),
            expression,
        )

    debug_log("TOOL", f"После подстановки: {expression!r}")

    try:
        result = eval(expression)
        debug_log("TOOL", f"calculate() ← {result!r}")
        return f"Результат вычисления: {result}"
    except Exception as e:
        debug_log("TOOL", f"calculate() ОШИБКА: {e}")
        return f"Ошибка вычисления: {e}"


def save_variable(name: str, value: str) -> str:
    """Сохраняет значение под именем в MEMORY.

    Если значение можно превратить в число — сохраняет как число,
    иначе — как строку. Это позволяет использовать его в calculate().
    """
    debug_log("TOOL", f"save_variable() → name={name!r}, value={value!r}")

    try:
        numeric_value = float(value)
        if numeric_value.is_integer():
            numeric_value = int(numeric_value)
        MEMORY[name] = numeric_value
        debug_log("MEMORY", f"Сохранено (число): {name} = {numeric_value}")
        return f"Переменная '{name}' сохранена со значением {numeric_value}"
    except (ValueError, TypeError):
        MEMORY[name] = value
        debug_log("MEMORY", f"Сохранено (строка): {name} = {value!r}")
        return f"Переменная '{name}' сохранена со значением {value}"


def get_variable(name: str) -> str:
    """Возвращает значение переменной из MEMORY."""
    debug_log("TOOL", f"get_variable() → {name!r}")

    if name in MEMORY:
        value = MEMORY[name]
        debug_log("MEMORY", f"Найдено: {name} = {value!r}")
        return f"{name} = {value}"

    available = list(MEMORY.keys())
    debug_log("MEMORY", f"НЕ найдено: {name!r}. Доступные: {available}")
    return f"Переменная '{name}' не найдена. Доступные: {available}"


def list_variables() -> str:
    """Показывает все сохранённые переменные."""
    debug_log("TOOL", "list_variables()")
    debug_log("MEMORY", f"Текущее состояние: {MEMORY}")

    if not MEMORY:
        return "Память пуста."

    lines = [f"  {k} = {v}" for k, v in MEMORY.items()]
    return "Сохранённые переменные:\n" + "\n".join(lines)


# --- Схема инструментов для модели ---

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'calculate',
            'description': (
                'Вычислить математическое выражение. '
                'Поддерживает +, -, *, /, скобки. '
                'Может использовать сохранённые переменные по имени. '
                'Примеры: "10 + 5", "(2 + 3) * 4", "total + 100".'
            ),
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
            'name': 'save_variable',
            'description': (
                'Сохранить значение под именем. '
                'Вызывай ВСЕГДА, когда пользователь говорит "сохрани", '
                '"запомни как", "запиши в". '
                'Пример: name="total", value="60".'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Имя переменной, например "result"',
                    },
                    'value': {
                        'type': 'string',
                        'description': 'Значение (число или строка)',
                    },
                },
                'required': ['name', 'value'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_variable',
            'description': (
                'Получить значение сохранённой переменной по имени. '
                'Используй, когда пользователь упоминает ранее сохранённое имя.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': 'Имя переменной'},
                },
                'required': ['name'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_variables',
            'description': 'Показать все сохранённые переменные. Без аргументов.',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
]


# --- Словарь инструментов ---
# Сопоставление «имя из ответа модели» → «Python-функция».
TOOL_FUNCTIONS = {
    'calculate': calculate,
    'save_variable': save_variable,
    'get_variable': get_variable,
    'list_variables': list_variables,
}


# --- Агентный цикл ---

def run_agent(user_message: str) -> str:
    """Запускает агентный цикл для одного сообщения пользователя.

    Цикл продолжается, пока модель запрашивает инструменты.
    Как только модель возвращает ответ без tool_calls — выходим.
    """
    print_separator(f"ПОЛЬЗОВАТЕЛЬ: {user_message}")

    messages = [
        {
            'role': 'system',
            'content': (
                'Ты — калькулятор с памятью. Отвечай только на русском языке.\n\n'
                'ПРАВИЛА:\n'
                '1. НИКОГДА не пиши текст с названиями инструментов. СРАЗУ вызывай инструмент.\n'
                '2. Просят посчитать → вызови calculate.\n'
                '3. Просят сохранить → вызови save_variable.\n'
                '4. Упоминают сохранённое имя → вызови calculate, оно само подставит значение.\n'
                '5. Просят показать переменные → вызови list_variables.\n'
                '6. Когда задача выполнена — напиши финальный ответ без упоминания инструментов.\n\n'
                'ЗАПРЕЩЕНО писать "Шаг 1: calculate(...)" или "calculate(expression=...)". '
                'Это не вызов, это просто текст. Вызывай инструмент через tool_calls.'
            ),
        },
        {'role': 'user', 'content': user_message},
    ]

    for iteration in range(1, MAX_ITERATIONS + 1):
        debug_log("LOOP", f"─── Итерация {iteration} ───")
        debug_log("API", f"Отправка {len(messages)} сообщений в Ollama...")

        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS,
            options={'num_ctx': NUM_CTX, 'temperature': TEMPERATURE},
        )

        tool_calls = response.message.tool_calls

        if not tool_calls:
            debug_log("API", "Модель вернула финальный ответ")
            print(f"\n🤖 ОТВЕТ АГЕНТА: {response.message.content}")
            return response.message.content

        debug_log("API", f"Модель запросила {len(tool_calls)} инструмент(ов)")
        messages.append(response.message)

        for i, tool_call in enumerate(tool_calls, 1):
            function_name = tool_call.function.name
            arguments = tool_call.function.arguments

            debug_log(
                "LOOP",
                f"Инструмент #{i}: {function_name}({json.dumps(arguments, ensure_ascii=False)})",
            )

            func = TOOL_FUNCTIONS.get(function_name)

            if func is None:
                result = f"Ошибка: инструмент '{function_name}' не найден"
                debug_log("ERROR", result)
            else:
                try:
                    result = func(**arguments)
                except TypeError as e:
                    result = f"Ошибка вызова {function_name}: {e}"
                    debug_log("ERROR", result)
                except Exception as e:
                    result = f"Неожиданная ошибка: {e}"
                    debug_log("ERROR", result)

            messages.append({
                'role': 'tool',
                'content': str(result),
                'tool_name': function_name,
            })

    debug_log("ERROR", f"Превышен лимит итераций ({MAX_ITERATIONS})")
    return "Ошибка: агент зациклился."


if __name__ == "__main__":
    print_separator("КАЛЬКУЛЯТОР С ПАМЯТЬЮ")

    run_agent("Посчитай 10 + 5")
    run_agent("Посчитай 20 * 3 и сохрани результат как total")
    run_agent("Покажи все переменные")
    run_agent("Сколько будет total + 100?")
    run_agent(
        "Посчитай 2 + 2, сохрани как a. "
        "Посчитай 3 + 3, сохрани как b. "
        "Посчитай a + b"
    )