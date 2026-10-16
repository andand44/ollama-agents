"""
Оркестратор мультиагентной системы с diff-подходом.

Критик → Редактор (правки) → Факт-чекер → Судья.
"""

from utils import print_separator, debug_log
from agents.critic import criticize
from agents.editor import get_edits, apply_edits
from agents.fact_checker import check_facts
from agents.judge import judge


def improve_text(text: str) -> dict:
    """Прогоняет текст через цепочку агентов."""
    print_separator("МУЛЬТИАГЕНТНАЯ ОБРАБОТКА ТЕКСТА")
    debug_log("PIPELINE", f"Входной текст: {len(text)} символов")

    results = {'original': text}

    # ── Шаг 1: Критик ──
    print_separator("ШАГ 1/4: КРИТИК")
    critique = criticize(text)
    results['critique'] = critique
    print(f"\n🔍 Замечания критика:\n{critique}")

    # ── Шаг 2: Редактор (правки) ──
    print_separator("ШАГ 2/4: РЕДАКТОР (diff)")
    edits = get_edits(text, critique)
    new_text, applied, skipped = apply_edits(text, edits)
    results['edits'] = edits
    results['applied_edits'] = applied
    results['skipped_edits'] = skipped
    results['improved'] = new_text

    print(f"\n✍️ Применено правок: {len(applied)} из {len(edits)}")
    for e in applied:
        before = e['before'][:50]
        after = e['after'][:50] if e['after'] else '(удалено)'
        print(f"   • «{before}» → «{after}»")

    if skipped:
        print(f"\n⚠️ Пропущено (защита от потери фактов): {len(skipped)}")
        for e in skipped:
            reason = e.get('reason', 'неизвестно')
            print(f"   • «{e['before'][:50]}» — {reason}")

    # ── Шаг 3: Факт-чекер ──
    print_separator("ШАГ 3/4: ФАКТ-ЧЕКЕР")
    fact_report = check_facts(new_text)
    results['facts'] = fact_report
    print(f"\n🔎 Отчёт факт-чекера:\n{fact_report['report']}")

    # ── Шаг 4: Судья ──
    print_separator("ШАГ 4/4: СУДЬЯ")
    verdict = judge(text, critique, new_text, fact_report)
    results['verdict'] = verdict
    print(f"\n⚖️ Финальный вердикт:\n{verdict}")

    return results