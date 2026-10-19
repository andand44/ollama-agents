from fastapi import FastAPI
from pydantic import BaseModel
import requests
import re

app = FastAPI(title="Portfolio Tools")

class Query(BaseModel):
    query: str

GITHUB_REPO = "andand44/ollama-agents"
BRANCH = "main"

def get_portfolio_context() -> str:
    """Собирает структуру репозитория: папки, README и имена файлов."""
    headers = {'User-Agent': 'n8n-portfolio-bot'}
    
    try:
        # 1. ОДИН запрос, чтобы получить всё дерево файлов (экономит лимиты)
        tree_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{BRANCH}?recursive=1"
        resp = requests.get(tree_url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return f"Ошибка GitHub API (статус {resp.status_code}). Попробуйте позже."
            
        tree = resp.json().get('tree', [])
        
        # 2. Группируем файлы по папкам проектов (01_, 02_...)
        projects = {}
        for item in tree:
            path = item['path']
            if '/' in path:
                folder = path.split('/')[0]
                if re.match(r'^\d{2}_', folder):
                    if folder not in projects:
                        projects[folder] = []
                    projects[folder].append(path)

        context_parts = []
        
        # 3. Для каждого проекта вытаскиваем README и список файлов
        for folder in sorted(projects.keys()):
            files = projects[folder]
            readme_path = f"{folder}/README.md"
            
            # Ищем описание в README
            description = "Описание отсутствует."
            if readme_path in files:
                raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{BRANCH}/{readme_path}"
                readme_resp = requests.get(raw_url, headers=headers, timeout=10)
                if readme_resp.status_code == 200:
                    # Берем первые 600 символов описания
                    description = readme_resp.text[:600].replace('\n', ' ')
            
            # Собираем имена файлов (только .py)
            py_files = [f.split('/')[-1] for f in files if f.endswith('.py')]
            
            proj_info = f"### Проект: {folder}\nОписание: {description}\nФайлы: {', '.join(py_files)}"
            context_parts.append(proj_info)
            
    except Exception as e:
        return f"Ошибка при загрузке с GitHub: {e}"
        
    return "\n\n".join(context_parts)

@app.post("/search")
def search_portfolio(query: Query):
    print(f"Запрос контекста: {query.query}")
    context = get_portfolio_context()
    return {"context": context}