from mcp.server.fastmcp import FastMCP
from datetime import datetime
from pathlib import Path

# Создаем MCP сервер
mcp = FastMCP("LocalTools")

@mcp.tool()
def get_current_time() -> str:
    """Возвращает текущее время на сервере."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def read_local_file(filename: str) -> str:
    """Читает текстовый файл из папки safe_data (защита от path traversal)."""
    # Мы ограничиваем доступ только папкой safe_data, чтобы агент не прочитал системные файлы
    safe_dir = Path("safe_data").resolve()
    safe_dir.mkdir(exist_ok=True)
    
    filepath = (safe_dir / filename).resolve()
    
    # Проверка, что агент не пытается выйти за пределы папки через ../
    if not str(filepath).startswith(str(safe_dir)):
        return "Ошибка доступа: нельзя выходить за пределы safe_data"
        
    if not filepath.exists():
        return f"Файл {filename} не найден."
        
    return filepath.read_text(encoding="utf-8")

if __name__ == "__main__":
    # Запуск сервера через stdio (стандартный ввод/вывод)
    mcp.run()