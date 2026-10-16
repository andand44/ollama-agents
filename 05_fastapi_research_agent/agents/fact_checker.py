"""
Агент-Факт-чекер: находит утверждения, требующие проверки,
и проверяет их через интернет (search_web).
"""

import json

import ollama

import time

import re   # добавь в начало файла, если нет

from config import MODEL_NAME, NUM_CTX
from utils import call_llm, debug_log
from ddgs import DDGS


# ── Системные промпты ──

EXTRACT_SYSTEM_PROMPT = """Ты — анализатор. Извлекаешь из текста ТОЛЬКО проверяемые факты.

ФАКТ — это конкретное утверждение с ЧИСЛОМ, ПРОЦЕНТОМ, ДАТОЙ или СОБЫТИЕМ.
НЕ факт:
- Рекомендации: «Освойте Figma», «Пройдите курс»
- Общие фразы: «дизайн важен», «нужно учиться»
- Инструкции: «соберите портфолио из 3-4 проектов» (это совет, не факт)

ПРИМЕРЫ:
Вход: "Python создан в 1991 году. Популярен среди разработчиков."
Выход: ["Python создан в 1991 году"]

Вход: "37% детей используют нейросети. Освойте Figma."
Выход: ["37% детей используют нейросети"]

Вход: "Идите учиться. Развивайте навыки."
Выход: []

Отвечай ТОЛЬКО JSON-массивом строк."""


VERDICT_SYSTEM_PROMPT = """Ты — факт-чекер. На основе результатов поиска определи, 
подтверждается ли утверждение.

ФОРМАТ ОТВЕТА (строго JSON):
{
  "verdict": "confirmed" | "refuted" | "unclear",
  "explanation": "краткое пояснение на русском"
}

- "confirmed" — информация найдена в нескольких источниках
- "refuted" — источники прямо опровергают
- "unclear" — однозначного ответа нет, данных недостаточно

Отвечай только JSON."""


# ── Функции-помощники ──

def _extract_claims(text: str) -> list[str]:
    """Извлекает факты из текста. Возвращает список строк."""
    debug_log("FACT", "Извлекаем утверждения для проверки...")

    raw = call_llm(EXTRACT_SYSTEM_PROMPT, f"Текст:\n\n{text}")
    debug_log("FACT", f"Сырой ответ модели: {raw[:200]!r}")   # ← НОВОЕ: смотрим что вернула модель

    # ── Стратегия 1: попытка чистого JSON ──
    cleaned = raw.strip().strip('`').replace('json\n', '', 1).strip()

    try:
        claims = json.loads(cleaned)
        if isinstance(claims, list):
            result = [str(c) for c in claims if c]
            debug_log("FACT", f"JSON-парсинг успешен: {len(result)} фактов")
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # ── Стратегия 2: ищем JSON-массив в любом месте ответа ──
    match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if match:
        try:
            claims = json.loads(match.group())
            if isinstance(claims, list):
                result = [str(c) for c in claims if c]
                debug_log("FACT", f"Regex-парсинг успешен: {len(result)} фактов")
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Стратегия 3: fallback через regex по тексту ──
    # Ищем проценты, годы, большие числа — явные кандидаты в факты
    debug_log("FACT", "JSON не найден, используем regex-fallback")
    fallback_patterns = [
        r'[^.!?]*\d+\s*%[^.!?]*[.!?]',       # предложения с процентами
        r'[^.!?]*\b(19|20)\d{2}\b[^.!?]*[.!?]',   # предложения с годами
        r'[^.!?]*\b\d{2,}\b[^.!?]*[.!?]',    # предложения с большими числами
    ]
    found = []
    for pattern in fallback_patterns:
        for match in re.finditer(pattern, text):
            sentence = match.group().strip()
            if sentence and sentence not in found:
                found.append(sentence)

    debug_log("FACT", f"Regex-fallback нашёл: {len(found)} фактов")
    if not raw or len(raw.strip()) < 3:
        debug_log("FACT", "Модель вернула пустой ответ, используем regex-fallback")
        # сразу переходим к стратегии 3
    return found[:5]   # не больше 5 — защита от лавины

def _search_snippets(query: str, max_results: int = 3) -> str:
    """Ищет в интернете с одним retry на случай rate limit."""
    for attempt in range(1, 3):   # 2 попытки
        try:
            debug_log("FACT", f"Поиск (попытка {attempt}): {query[:50]}...")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results, region="ru-ru"))

            if not results:
                return "Ничего не найдено."

            lines = []
            for i, r in enumerate(results, 1):
                title = r.get('title', '')
                body = r.get('body', '')[:200]
                lines.append(f"{i}. {title}\n   {body}")

            debug_log("FACT", f"Успех: {len(results)} результатов")
            return "\n\n".join(lines)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            debug_log("FACT", f"Попытка {attempt} провалилась: {error_msg}")

            if attempt == 1:
                debug_log("FACT", "Ждём 2 секунды и пробуем снова...")
                time.sleep(2)
            else:
                debug_log("FACT", "Обе попытки ddgs провалились, идём в Wikipedia...")
                return _wiki_fallback(query)

    return "Не удалось выполнить поиск."

def _wiki_fallback(query: str) -> str:
    """Fallback: ищем в Wikipedia, если ddgs недоступен."""
    import requests

    # Обрезаем запрос до 5 слов — Wikipedia плохо ищет длинные фразы
    short_query = ' '.join(query.split()[:5])
    url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{short_query.replace(' ', '_')}"
    headers = {'User-Agent': 'FactChecker/1.0 (educational)'}

    try:
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            title = data.get('title', '')
            extract = data.get('extract', '')[:300]
            debug_log("FACT", f"Wikipedia fallback: {title}")
            return f"Wikipedia '{title}': {extract}"
        return f"Wikipedia: статья не найдена (статус {r.status_code})"
    except Exception as e:
        return f"Wikipedia fallback тоже не сработал: {e}"
    
def _extract_claims(text: str) -> list[str]:
    """Просит модель извлечь факты из текста. Возвращает список строк."""
    debug_log("FACT", "Извлекаем утверждения для проверки...")

    raw = call_llm(EXTRACT_SYSTEM_PROMPT, f"Текст:\n\n{text}")

    # Модель может обернуть JSON в ```json ... ``` — убираем обёртку
    cleaned = raw.strip().strip('`').replace('json\n', '', 1).strip()

    try:
        claims = json.loads(cleaned)
        if isinstance(claims, list):
            return [str(c) for c in claims if c]
    except (json.JSONDecodeError, ValueError) as e:
        debug_log("FACT", f"Не удалось распарсить JSON: {e}")
        debug_log("FACT", f"Сырой ответ: {raw[:200]}")

    return []


def _check_claim(claim: str) -> dict:
    """Проверяет одно утверждение через поиск + LLM."""
    debug_log("FACT", f"Проверяем: {claim[:60]}...")

    snippets = _search_snippets(claim, max_results=3)

    user_prompt = (
        f"УТВЕРЖДЕНИЕ: {claim}\n\n"
        f"РЕЗУЛЬТАТЫ ПОИСКА:\n\n{snippets}\n\n"
        "Определи verdict. Верни только JSON."
    )

    raw = call_llm(VERDICT_SYSTEM_PROMPT, user_prompt)
    cleaned = raw.strip().strip('`').replace('json\n', '', 1).strip()

    try:
        result = json.loads(cleaned)
        return {
            'claim': claim,
            'verdict': result.get('verdict', 'unclear'),
            'explanation': result.get('explanation', ''),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            'claim': claim,
            'verdict': 'unclear',
            'explanation': 'Не удалось распарсить ответ модели',
        }


# ── Публичная функция ──

def check_facts(text: str) -> dict:
    """Проверяет все факты в тексте. Возвращает отчёт."""
    debug_log("FACT", f"Факт-чекер запущен на тексте ({len(text)} символов)")

    claims = _extract_claims(text)
    debug_log("FACT", f"Найдено утверждений: {len(claims)}")

    if not claims:
        return {
            'claims': [],
            'report': "Конкретных фактов для проверки не найдено.",
        }

    checked = [_check_claim(c) for c in claims]

    # Формируем отчёт
    icons = {'confirmed': '✅', 'refuted': '❌', 'unclear': '❓'}
    lines = []
    for c in checked:
        icon = icons.get(c['verdict'], '?')
        lines.append(f"{icon} «{c['claim']}»")
        if c['explanation']:
            lines.append(f"   → {c['explanation']}")

    return {
        'claims': checked,
        'report': "\n".join(lines),
    }