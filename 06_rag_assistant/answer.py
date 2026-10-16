"""
Генерация ответа через LLM на основе найденных чанков.
"""

import ollama

from config import MODEL_NAME, NUM_CTX, TEMPERATURE


ANSWER_SYSTEM_PROMPT = """Ты — ассистент, отвечающий на вопросы на основе фрагментов документов.

ЖЁСТКИЕ ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе предоставленных фрагментов. Не используй свои знания.
2. Если в фрагментах нет ответа — честно скажи: «В загруженных документах нет этой информации».
3. НЕ выдумывай факты, ссылки, имена. Только то, что есть в тексте.
4. Отвечай простым языком, без воды. Максимум 5-7 предложений.
5. В конце ответа укажи, из каких файлов взята информация.

Отвечай на русском языке."""


def generate_answer(question: str, chunks: list) -> str:
    """Генерирует ответ на вопрос на основе найденных чанков.

    Args:
        question: вопрос пользователя
        chunks: список Chunk-объектов (с полем .text и .source)

    Returns:
        Текстовый ответ.
    """
    if not chunks:
        return "Не нашёл ничего релевантного в документах."

    # Формируем контекст из чанков
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Фрагмент {i} из {chunk.source}]\n{chunk.text}"
        )
    context = "\n\n---\n\n".join(context_parts)

    user_prompt = (
        f"ВОПРОС: {question}\n\n"
        f"ФРАГМЕНТЫ ДОКУМЕНТОВ:\n\n{context}\n\n"
        "Ответь на вопрос, опираясь ТОЛЬКО на эти фрагменты."
    )

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {'role': 'system', 'content': ANSWER_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
        options={'num_ctx': NUM_CTX, 'temperature': TEMPERATURE},
    )

    return response.message.content