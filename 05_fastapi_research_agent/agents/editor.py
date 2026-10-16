"""
Агент-Редактор (diff-подход).

НЕ переписывает текст целиком — возвращает список правок.
Код применяет правки к оригиналу, гарантируя сохранение фактов.
"""

import json
import re

from utils import call_llm, debug_log


EDITOR_SYSTEM_PROMPT = """Ты — редактор. Ты НЕ переписываешь текст целиком. 
Ты возвращаешь список КОНКРЕТНЫХ ПРАВОК для устранения замечаний критика.

ФОРМАТ ОТВЕТА — JSON-массив объектов с полями "before" и "after":
[
  {"before": "точная фраза из оригинала", "after": "замена"},
  {"before": "очень важно отметить", "after": ""}
]

ЖЁСТКИЕ ПРАВИЛА:
1. В поле "before" — ТОЧНАЯ копия фразы из оригинала, символ в символ.
2. Если фразу нужно УДАЛИТЬ — оставь "after" пустой строкой "".
3. ЗАПРЕЩЕНО трогать: числа, проценты, даты, имена, названия исследований.
   Если в тексте есть "37%" или "120 тысяч" — не трогай их.
4. Не более 10 правок. Только самое важное.
5. Если правок нет — верни пустой массив: [].

ЧТО ИСПРАВЛЯТЬ:
- Канцеляризмы: "очень важно отметить, что" → ""
- Длинные обороты: "в заключение хотелось бы сказать" → ""
- Повторы одного слова 2+ раз

ПРИМЕР:
Вход: "Очень важно отметить, что нейросети играют очень важную роль."
Выход: [
  {"before": "Очень важно отметить, что ", "after": ""},
  {"before": "играют очень важную роль", "after": "важны"}
]

Отвечай ТОЛЬКО JSON-массивом. Начни с [ и закончи ]."""


def get_edits(text: str, critique: str) -> list[dict]:
    """Просит модель вернуть список правок."""
    debug_log("EDITOR", f"Запрашиваем правки для текста ({len(text)} символов)")

    user_prompt = (
        f"ТЕКСТ:\n\n---\n{text}\n---\n\n"
        f"ЗАМЕЧАНИЯ КРИТИКА:\n\n{critique}\n\n"
        "Верни JSON-массив правок."
    )

    raw = call_llm(EDITOR_SYSTEM_PROMPT, user_prompt)
    debug_log("EDITOR", f"Сырой ответ: {raw[:200]!r}")

    edits = _parse_edits(raw)
    debug_log("EDITOR", f"Распарсено правок: {len(edits)}")
    return edits


def _parse_edits(raw: str) -> list[dict]:
    """Парсит JSON-массив правок из ответа модели."""
    if not raw:
        return []

    # Убираем markdown-обёртку ```json ... ```
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    cleaned = re.sub(r'\s*```\s*$', '', cleaned)

    # Ищем JSON-массив в ответе
    match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if not match:
        debug_log("EDITOR", "JSON-массив не найден в ответе")
        return []

    try:
        data = json.loads(match.group())
    except (json.JSONDecodeError, ValueError) as e:
        debug_log("EDITOR", f"Ошибка JSON: {e}")
        return []

    if not isinstance(data, list):
        return []

    # Валидация каждой правки
    valid = []
    for item in data:
        if (isinstance(item, dict)
                and isinstance(item.get('before'), str)
                and isinstance(item.get('after'), str)
                and item['before'].strip()):
            valid.append({
                'before': item['before'],
                'after': item['after'],
            })
    return valid


def _is_safe_edit(edit: dict) -> tuple[bool, str]:
    """Проверяет, что правка не удаляет факты (числа/проценты).

    Returns:
        (is_safe, reason) — причина отклонения, если не безопасна.
    """
    before = edit['before']
    after = edit['after']

    # Ищем числа в before и after
    numbers_before = re.findall(r'\d+', before)
    numbers_after = re.findall(r'\d+', after)

    # Если в before есть числа, а в after их стало меньше — опасная правка
    if numbers_before and len(numbers_after) < len(numbers_before):
        missing = [n for n in numbers_before if n not in numbers_after]
        return False, f"удаляет числа: {missing}"

    return True, ''

def _is_safe_edit(edit: dict) -> tuple[bool, str]:
    """Проверяет, что правка не удаляет факты и структуру."""
    before = edit['before']
    after = edit['after']

    # ── ЗАЩИТА 1: заголовки (короткие фразы без точки в конце) ──
    if after == '' and len(before.split()) <= 6 and not before.rstrip().endswith(('.', ',', '!', '?')):
        return False, 'похоже на заголовок или ссылку'

    # ── ЗАЩИТА 2: числа/проценты ──
    numbers_before = re.findall(r'\d+', before)
    numbers_after = re.findall(r'\d+', after)
    if numbers_before and len(numbers_after) < len(numbers_before):
        missing = [n for n in numbers_before if n not in numbers_after]
        return False, f'удаляет числа: {missing}'

    return True, ''


def apply_edits(text: str, edits: list[dict]) -> tuple[str, list, list]:
    """Применяет правки к тексту.

    Returns:
        (new_text, applied, skipped) — новый текст, применённые правки, пропущенные.
    """
    new_text = text
    applied = []
    skipped = []

    for edit in edits:
        # Проверка безопасности
        is_safe, reason = _is_safe_edit(edit)
        if not is_safe:
            debug_log("EDITOR", f"Правка отклонена ({reason}): {edit['before'][:40]!r}")
            skipped.append({**edit, 'reason': reason})
            continue

        # Проверка наличия в тексте
        if edit['before'] not in new_text:
            debug_log("EDITOR", f"Фраза не найдена: {edit['before'][:40]!r}")
            skipped.append({**edit, 'reason': 'фраза не найдена'})
            continue

        # Применяем
        new_text = new_text.replace(edit['before'], edit['after'], 1)
        applied.append(edit)

    return new_text, applied, skipped