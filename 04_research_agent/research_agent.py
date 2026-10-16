"""
Research Agent — поиск в интернете с проверкой фактов.

Агент умеет: искать в интернете, читать Wikipedia и загружать веб-страницы.
Демонстрирует:
- работу с внешними API (requests, ddgs, BeautifulSoup);
- agentic loop с narration detector (защита от "модель пишет, но не делает");
- контекст разговора (CONVERSATION_HISTORY, CURRENT_TOPIC);
- проверку фактов через fetch_page — борьбу с галлюцинациями.
"""

import json
import re
from datetime import datetime

import ollama
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS


# --- Конфигурация ---
MODEL_NAME = 'qwen2.5:3b'
NUM_CTX = 2048
TEMPERATURE = 0
MAX_ITERATIONS = 12
HISTORY_LIMIT = 10


# --- Состояние агента (живёт между вызовами) ---
CONVERSATION_HISTORY: list = []
CURRENT_TOPIC: str = ""


# --- Отладочные утилиты ---

def debug_log(section: str, message: str) -> None:
    """Печатает отладочное сообщение с временной меткой."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{section:8}] {message}")


def print_separator(title: str = "") -> None:
    """Печатает визуальный разделитель блоков."""
    print("\n" + "=" * 65)
    if title:
        print(f"  {title}")
        print("=" * 65)


# --- Инструменты ---

def search_web(query: str, max_results: int = 3) -> str:
    """Ищет в интернете через ddgs и возвращает результаты строкой."""
    debug_log("TOOL", f"search_web() → query={query!r}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="ru-ru"))

        if not results:
            debug_log("TOOL", "Результатов не найдено")
            return f"По запросу '{query}' ничего не найдено."

        lines = [f"Найдено {len(results)} результатов по запросу '{query}':"]
        for i, r in enumerate(results, 1):
            lines.append(f"\n{i}. {r.get('title', 'Без названия')}")
            lines.append(f"   URL: {r.get('href', '')}")
            lines.append(f"   Описание: {r.get('body', '')[:200]}")

        result_text = "\n".join(lines)
        debug_log("TOOL", f"search_web() ← {len(result_text)} символов")
        return result_text

    except Exception as e:
        debug_log("TOOL", f"search_web() ОШИБКА: {e}")
        return f"Ошибка поиска: {e}"


def fetch_wikipedia(query: str) -> str:
    """Получает краткое описание статьи из русской Wikipedia."""
    debug_log("TOOL", f"fetch_wikipedia() → query={query!r}")

    url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
    headers = {
        'User-Agent': 'ResearchAgent/1.0 (educational project)',
        'Accept': 'application/json',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            title = data.get('title', '')
            extract = data.get('extract', 'Нет описания')
            debug_log("TOOL", f"fetch_wikipedia() ← {title}")
            return f"Wikipedia: {title}\n\n{extract}"

        debug_log("TOOL", f"fetch_wikipedia() статус {response.status_code}")
        return f"Wikipedia не нашла статью '{query}'. Статус: {response.status_code}"

    except Exception as e:
        debug_log("TOOL", f"fetch_wikipedia() ОШИБКА: {e}")
        return f"Ошибка Wikipedia: {e}"


def fetch_page(url: str, max_chars: int = 1500) -> str:
    """Загружает страницу по URL и извлекает чистый текст."""
    debug_log("TOOL", f"fetch_page() → url={url!r}")

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ru-RU,ru;q=0.9',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        debug_log("TOOL", f"Статус: {response.status_code}")

        if response.status_code != 200:
            return f"Ошибка загрузки страницы: статус {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')

        # Убираем неинформативные блоки
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))

        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        debug_log("TOOL", f"fetch_page() ← {len(text)} символов")
        return f"Содержимое страницы {url}:\n\n{text}"

    except requests.exceptions.Timeout:
        debug_log("TOOL", "Ошибка: timeout")
        return f"Ошибка: страница {url} не ответила за 15 секунд."
    except Exception as e:
        debug_log("TOOL", f"Ошибка: {e}")
        return f"Ошибка загрузки: {e}"


# --- Схема инструментов для модели ---

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'search_web',
            'description': (
                'Поиск в интернете через поисковую систему. '
                'Возвращает список из 2-3 результатов с заголовками, URL и описанием. '
                'Используй, когда нужно найти актуальную информацию или ссылки.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Поисковый запрос, например "нейросети 2026"',
                    },
                },
                'required': ['query'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'fetch_wikipedia',
            'description': (
                'Получить краткую статью из Wikipedia. '
                'Используй для быстрого получения определения или справки. '
                'Если термин имеет несколько значений (например, "трансформеры" — '
                'это фильм и ML-архитектура), уточняй запрос: '
                '"Трансформер (архитектура нейронных сетей)" вместо просто "трансформеры".'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Название статьи, например "Нейронная сеть"',
                    },
                },
                'required': ['query'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'fetch_page',
            'description': (
                'Загрузить полное содержимое веб-страницы по URL. '
                'Используй этот инструмент, чтобы ПРОВЕРИТЬ информацию из search_web. '
                'Возвращает первые 1500 символов текста страницы.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'description': 'Полный URL страницы, например "https://vc.ru/ai/..."',
                    },
                },
                'required': ['url'],
            },
        },
    },
]


TOOL_FUNCTIONS = {
    'search_web': search_web,
    'fetch_wikipedia': fetch_wikipedia,
    'fetch_page': fetch_page,
}


# --- Управление темой ---

def update_topic(user_message: str, agent_answer: str) -> None:
    """Определяет тему разговора отдельным мини-запросом к модели."""
    global CURRENT_TOPIC

    debug_log("TOPIC", "Обновление темы...")

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': (
                    'Определи тему разговора в 2-5 словах. '
                    'Ответь ТОЛЬКО темой, без пояснений и кавычек. '
                    'Если новая тема — продолжение предыдущей, верни её без изменений.'
                )},
                {'role': 'user', 'content': (
                    f"Предыдущая тема: {CURRENT_TOPIC or 'нет'}\n"
                    f"Пользователь: {user_message}\n"
                    f"Ассистент: {agent_answer[:200]}\n\n"
                    f"Какова тема разговора?"
                )},
            ],
            options={'num_ctx': 512, 'temperature': 0},
        )

        new_topic = response.message.content.strip().strip('"').strip("'")
        old_topic = CURRENT_TOPIC
        CURRENT_TOPIC = new_topic
        debug_log("TOPIC", f"Тема: {old_topic!r} → {new_topic!r}")

    except Exception as e:
        debug_log("TOPIC", f"Ошибка обновления темы: {e}")


def should_reset_topic(user_message: str) -> bool:
    """Проверяет явные маркеры смены темы в сообщении пользователя."""
    markers = ('другое', 'сменим тему', 'теперь про', 'а теперь', 'кстати о')
    return any(m in user_message.lower() for m in markers)


# --- Агентный цикл ---

def run_agent(user_message: str) -> str:
    """Запускает агентный цикл для одного сообщения пользователя."""
    global CONVERSATION_HISTORY, CURRENT_TOPIC

    # Смена темы — ДО формирования messages
    if should_reset_topic(user_message):
        debug_log("TOPIC", "Смена темы: сбрасываем контекст")
        CURRENT_TOPIC = ""
        CONVERSATION_HISTORY.clear()

    print_separator(f"ПОЛЬЗОВАТЕЛЬ: {user_message}")
    debug_log("MEMORY", f"Текущая тема: {CURRENT_TOPIC or '(не задана)'}")
    debug_log("MEMORY", f"История: {len(CONVERSATION_HISTORY)} сообщений")

    context_block = ""
    if CURRENT_TOPIC:
        context_block = (
            f"\n\nВАЖНО: Текущая тема разговора — «{CURRENT_TOPIC}». "
            f"Если пользователь использует двусмысленные слова, "
            f"интерпретируй их В КОНТЕКСТЕ этой темы."
        )

    system_prompt = (
        'Ты — исследовательский ассистент. Отвечай только на русском языке.\n'
        'ПРАВИЛА:\n'
        '1. НИКОГДА не пиши текст с названиями инструментов. СРАЗУ вызывай инструмент.\n'
        '2. Если нужна актуальная информация — вызови search_web.\n'
        '3. Если нужно определение — вызови fetch_wikipedia.\n'
        '4. Можешь вызывать инструменты несколько раз подряд.\n'
        '5. Когда задача выполнена — напиши финальный ответ без инструментов.\n'
        'ЗАПРЕЩЕНО писать "search_web(...)" или "Шаг 1: ...". Это текст, а не вызов.\n'
        'Не используй XML-теги в ответах.\n\n'
        'ПРАВИЛА ПРОВЕРКИ ФАКТОВ:\n'
        '1. Если пользователь спрашивает о фактах (даты, названия) — '
        'сначала search_web, потом fetch_page для 1-2 самых релевантных ссылок.\n'
        '2. Если источники противоречат твоим знаниям — доверяй источникам.\n'
        '3. Если два источника противоречат друг другу — явно укажи это в ответе.\n'
        '4. В конце ответа указывай, на какие источники ты опирался.'
        + context_block
    )

    messages = [{'role': 'system', 'content': system_prompt}]
    messages.extend(CONVERSATION_HISTORY)
    messages.append({'role': 'user', 'content': user_message})

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
            content = response.message.content or ''

            # Narration detector
            narration_markers = ('search_web(', 'fetch_wikipedia(', 'fetch_page(')
            if any(m in content for m in narration_markers):
                debug_log("NARRATION", "Обнаружен narration, переспрашиваем...")
                debug_log("NARRATION", f"Текст: {content[:100]}")

                messages.append({'role': 'assistant', 'content': content})
                messages.append({'role': 'user', 'content': (
                    'СТОП. Ты написал текст вместо вызова. '
                    'Вызови инструмент через tool_calls, а не текстом.'
                )})
                continue

            debug_log("API", "Модель вернула финальный ответ")
            print(f"\n🤖 ОТВЕТ АГЕНТА:\n{content}")

            CONVERSATION_HISTORY.append({'role': 'user', 'content': user_message})
            CONVERSATION_HISTORY.append({'role': 'assistant', 'content': content})
            update_topic(user_message, content)

            # Ограничиваем историю
            if len(CONVERSATION_HISTORY) > HISTORY_LIMIT:
                CONVERSATION_HISTORY[:] = CONVERSATION_HISTORY[-HISTORY_LIMIT:]
                debug_log("MEMORY", f"История обрезана до {HISTORY_LIMIT} сообщений")

            return content

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
    print_separator("АГЕНТ С ПРОВЕРКОЙ ФАКТОВ")

    run_agent(
        "Какие фильмы про Трансформеров существуют? "
        "Проверь факты по источникам и назови год выхода первого фильма."
    )