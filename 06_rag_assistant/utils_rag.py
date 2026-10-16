"""
Мелкие утилиты для RAG-проекта.
"""

from datetime import datetime


def debug_log(section: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{section:8}] {message}")


def print_separator(title: str = "") -> None:
    print("\n" + "═" * 60)
    if title:
        print(f"  {title}")
        print("═" * 60)