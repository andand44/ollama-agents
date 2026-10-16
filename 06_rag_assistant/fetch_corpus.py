"""
Загрузчик корпуса из русской Wikipedia.

Использует action=parse для получения HTML + BeautifulSoup для очистки.
Это даёт чистый текст без LaTeX-формул и служебных элементов.

Запуск:
    python fetch_corpus.py
"""

import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# --- Настройки ---
CORPUS_DIR = Path(__file__).parent / "corpus"
USER_AGENT = "CorpusFetcher/1.0 (educational project)"
API_URL = "https://ru.wikipedia.org/w/api.php"

DELAY_BETWEEN_REQUESTS = 2.5
MAX_RETRIES = 3
RETRY_DELAY = 10


# --- Темы: (slug, точное название статьи) ---
TOPICS = [
    ("neural_network",          "Нейронная сеть"),
    ("machine_learning",        "Машинное обучение"),
    ("transformer",             "Трансформер (машинное обучение)"),
    ("large_language_model",    "Большая языковая модель"),
    ("deep_learning",           "Глубокое обучение"),
    ("nlp",                     "Обработка естественного языка"),
    ("computer_vision",         "Компьютерное зрение"),
    ("reinforcement_learning",  "Обучение с подкреплением"),
    ("python",                  "Python"),
    ("fastapi",                 "FastAPI"),
    ("word_embeddings",         "Векторное представление слов"),
    ("gradient_descent",        "Градиентный спуск"),
    ("cnn",                     "Свёрточная нейронная сеть"),
    ("rnn",                     "Рекуррентная нейронная сеть"),
    ("word2vec",                "Word2vec"),
    ("artificial_intelligence", "Искусственный интеллект"),
    ("regression",              "Регрессионный анализ"),
    ("probability_theory",      "Теория вероятностей"),
    ("statistics",              "Математическая статистика"),
    ("linear_algebra",          "Линейная алгебра"),
]


# --- Загрузка HTML ---

def fetch_article_html(title: str) -> str | None:
    """Загружает HTML-разметку статьи через action=parse."""
    params = {
        'action': 'parse',
        'format': 'json',
        'page': title,
        'prop': 'text',
        'redirects': True,
        'disableeditsection': True,
        'disabletoc': True,
        'disablelimitreport': True,
    }
    headers = {'User-Agent': USER_AGENT}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, params=params, headers=headers, timeout=20)

            if r.status_code == 429:
                print(f"  ⏸  Rate limit (попытка {attempt}/{MAX_RETRIES}), пауза {RETRY_DELAY}с...")
                time.sleep(RETRY_DELAY)
                continue

            r.raise_for_status()
            data = r.json()

            if 'error' in data:
                print(f"  ⚠️  {data['error'].get('info', 'Ошибка API')}")
                return None

            parse = data.get('parse', {})
            html = parse.get('text', {}).get('*', '')
            if not html:
                print(f"  ⚠️  Пустой HTML: '{title}'")
                return None

            return html

        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTP {e.response.status_code} (попытка {attempt})")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")
            return None

    return None


# --- Очистка HTML ---

# Селекторы, которые удаляем полностью
REMOVE_SELECTORS = [
    'style', 'script', 'sup.reference',       # скрипты, стили, сноски
    '.mw-editsection',                        # "править" ссылки
    '.navbox', '.infobox', '.metadata',       # навигация и инфобоксы
    '.reflist', '.references',                # список литературы
    '.mw-references-wrap',                    # обёртка ссылок
    '.thumb', '.thumbinner',                  # картинки с подписями
    'figure', 'figcaption',                   # медиа-блоки
    'table',                                  # таблицы (часто мусор)
    '.mwe-math-element',                      # ФОРМУЛЫ (главное!)
    '.mwe-math-fallback-image-inline',        # картинки-формулы
    '.mwe-math-fallback-image-display',       # блочные картинки-формулы
    'math',                                   # MathML формулы
    '.mw-empty-elt',                          # пустые элементы
    '.hatnote',                               # "не путать с ..."
    '.side-box', '.ambox',                    # плашки
]


def clean_html(html: str) -> str:
    """Превращает HTML статьи в чистый текст без формул и мусора."""
    soup = BeautifulSoup(html, 'html.parser')

    # Удаляем мусорные блоки
    for selector in REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Дополнительно убираем любые <span> с классом, содержащим 'math'
    for el in soup.find_all(class_=re.compile(r'math')):
        el.decompose()

    # Получаем текст из параграфов и заголовков
    parts = []
    for el in soup.find_all(['h2', 'h3', 'h4', 'p', 'li']):
        text = el.get_text(separator=' ', strip=True)
        if not text:
            continue
        # Пропускаем короткие мусорные строки
        if len(text) < 15:
            continue
        # Заголовки обрамляем в ==
        if el.name == 'h2':
            parts.append(f"\n== {text} ==\n")
        elif el.name == 'h3':
            parts.append(f"\n=== {text} ===\n")
        elif el.name == 'h4':
            parts.append(f"\n==== {text} ====\n")
        else:
            parts.append(text)

    text = '\n\n'.join(parts)

    # Финальная зачистка остатков LaTeX-мусора (если что-то проскочило)
    text = re.sub(r'\{\\displaystyle[^}]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = re.sub(r'[{}]+', '', text)

    # Убираем множественные пробелы и пустые строки
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def save_article(slug: str, text: str) -> Path:
    """Сохраняет очищенный текст как <slug>.txt."""
    path = CORPUS_DIR / f"{slug}.txt"
    path.write_text(text, encoding='utf-8')
    return path


# --- Главная логика ---

def main():
    CORPUS_DIR.mkdir(exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  Загрузка корпуса из русской Wikipedia (HTML → clean)")
    print(f"  Статей: {len(TOPICS)}")
    print(f"  Папка: {CORPUS_DIR}")
    print(f"{'=' * 60}\n")

    success, failed, skipped = 0, 0, 0

    for i, (slug, title) in enumerate(TOPICS, 1):
        target = CORPUS_DIR / f"{slug}.txt"
        if target.exists() and target.stat().st_size > 500:
            size_kb = target.stat().st_size / 1024
            print(f"[{i}/{len(TOPICS)}] {slug} — уже есть ({size_kb:.1f} KB), пропускаем")
            skipped += 1
            continue

        print(f"[{i}/{len(TOPICS)}] {slug}  ←  «{title}»")

        html = fetch_article_html(title)
        if html is None:
            failed += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        cleaned = clean_html(html)
        if len(cleaned) < 500:
            print(f"  ⚠️  Слишком короткий текст ({len(cleaned)} симв), пропускаем")
            failed += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        path = save_article(slug, cleaned)
        size_kb = len(cleaned) / 1024
        print(f"  ✅ {path.name} ({size_kb:.1f} KB)")
        success += 1

        time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"\n{'=' * 60}")
    print(f"  Готово!")
    print(f"  Скачано: {success}")
    print(f"  Пропущено (уже было): {skipped}")
    print(f"  Ошибок: {failed}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()