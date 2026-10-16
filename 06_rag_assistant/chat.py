"""
Интерактивный RAG-чат: загружаем индекс, задаём вопросы в цикле.
"""

from pathlib import Path

from config import MIN_SCORE
from indexer import get_or_build_index
from answer import generate_answer
from utils_rag import print_separator, debug_log


def main():
    print_separator("RAG-АССИСТЕНТ")
    store = get_or_build_index()

    print_separator("ГОТОВ К РАБОТЕ")
    print("Введите вопрос (или 'exit' для выхода).\n")

    while True:
        try:
            question = input("❓ Ваш вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not question or question.lower() in ('exit', 'quit', 'выход'):
            print("Выход.")
            break

        # ── Поиск ──
        results = store.search(question, top_k=3)

        if not results:
            print("🔍 Ничего не найдено.\n")
            continue

        top_score, top_chunk = results[0]

        # ── Порог отсечения ──
        if top_score < MIN_SCORE:
            print(f"🔍 Не нашёл релевантной информации (лучший score: {top_score:.3f}).")
            print(f"   Возможно, в загруженных документах нет ответа.\n")
            continue

        # ── Показываем источники ──
        print(f"\n📚 Найдено {len(results)} фрагментов:")
        for i, (score, chunk) in enumerate(results, 1):
            print(f"   [{i}] score={score:.3f} — {chunk.source}")

        # ── Генерируем ответ ──
        print(f"\n🤖 Генерирую ответ...\n")
        answer = generate_answer(question, [c for _, c in results])

        print(f"{'─' * 60}")
        print(f"ОТВЕТ:\n{answer}")
        print(f"{'─' * 60}\n")


if __name__ == "__main__":
    main()