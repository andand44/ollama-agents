"""
Индексатор корпуса с кэшированием.

Первый запуск: индексирует все файлы (6 минут).
Последующие: загружает из index.pkl (1 секунда).
"""

import time
from pathlib import Path

from rag import RAGStore, save_index, load_index, INDEX_PATH


CORPUS_DIR = Path(__file__).parent / "corpus"


def get_or_build_index(force_rebuild: bool = False) -> RAGStore:
    """Загружает индекс из кэша или строит заново."""
    if not force_rebuild and INDEX_PATH.exists():
        size_mb = INDEX_PATH.stat().st_size / 1024 / 1024
        print(f"📦 Загружаем индекс из {INDEX_PATH.name} ({size_mb:.1f} MB)...")
        start = time.time()
        store = load_index()
        print(f"✓ Загружено {len(store.chunks)} чанков за {time.time() - start:.2f} сек")
        return store

    print(f"\n{'=' * 60}")
    print(f"  Построение индекса (первый запуск или --rebuild)")
    print(f"{'=' * 60}")

    files = sorted(CORPUS_DIR.glob("*.txt"))
    if not files:
        raise RuntimeError(f"Папка {CORPUS_DIR} пуста. Запусти fetch_corpus.py")

    store = RAGStore()
    start = time.time()

    for f in files:
        size_kb = f.stat().st_size / 1024
        print(f"  → {f.name} ({size_kb:.1f} KB)...", end=' ', flush=True)
        count = store.add_file(f)
        print(f"{count} чанков")

    print(f"\n✓ Индексация: {len(store.chunks)} чанков за {time.time() - start:.1f} сек")

    print(f"💾 Сохраняем в {INDEX_PATH.name}...")
    save_index(store)
    size_mb = INDEX_PATH.stat().st_size / 1024 / 1024
    print(f"✓ Сохранено ({size_mb:.1f} MB)")

    return store


if __name__ == "__main__":
    import sys
    force = '--rebuild' in sys.argv
    get_or_build_index(force_rebuild=force)