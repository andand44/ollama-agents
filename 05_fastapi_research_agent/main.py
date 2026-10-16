"""
Точка входа. Тестовый запуск мультиагентной системы.
"""

from pipeline import improve_text


TEST_TEXT = """
Очень важно отметить, что в современном мире, в котором мы все живём и работаем,
нейросети играют очень большую и важную роль. Они очень сильно помогают людям
в очень разных задачах. Например, в очень многих случаях нейросети используются
для того, чтобы делать разные полезные вещи. По данным исследований, около 70%
людей уже используют нейросети каждый день, что является очень значительным
показателем. В заключение хотелось бы сказать, что нейросети — это очень важная
и перспективная технология, которая будет и дальше очень сильно развиваться.
"""


if __name__ == "__main__":
    result = improve_text(TEST_TEXT)

    print("\n" + "═" * 70)
    print("  ИТОГ")
    print("═" * 70)

    original = result['original'].strip()
    improved = result['improved'].strip()

    print(f"  Оригинал:        {len(original)} символов")
    print(f"  Улучшенный:      {len(improved)} символов")
    print(f"  Правок от LLM:   {len(result['edits'])}")
    print(f"  Применено:       {len(result['applied_edits'])}")
    print(f"  Отклонено:       {len(result['skipped_edits'])}")

    reduction = (1 - len(improved) / len(original)) * 100 if original else 0
    print(f"  Сокращение:      {reduction:.1f}%")

    claims = result['facts']['claims']
    if claims:
        confirmed = sum(1 for c in claims if c['verdict'] == 'confirmed')
        refuted = sum(1 for c in claims if c['verdict'] == 'refuted')
        unclear = sum(1 for c in claims if c['verdict'] == 'unclear')
        print(f"  Фактов:          {len(claims)} (✅{confirmed} ❌{refuted} ❓{unclear})")