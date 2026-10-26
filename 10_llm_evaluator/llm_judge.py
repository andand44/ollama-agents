import ollama
import json
import re

def evaluate_answer(question: str, expected: str, actual: str) -> tuple[float, str]:
    # Добавляем few-shot пример, чтобы модель поняла задачу
    prompt = f"""
    Ты программа для сравнения текста. Твоя задача — сравнить два ответа на один вопрос.
    Не используй свои знания о мире, просто сравни строки.
    
    Пример 1:
    Вопрос: Столица России?
    Эталон: Москва
    Ответ: Москва
    Результат: {{"score": 10.0, "reasoning": "Ответы полностью совпадают."}}

    Пример 2:
    Вопрос: Столица России?
    Эталон: Санкт-Петербург
    Ответ: Москва
    Результат: {{"score": 1.0, "reasoning": "Ответы не совпадают."}}

    Теперь твоя очередь:
    Вопрос: {question}
    Эталон: {expected}
    Ответ: {actual}
    Результат:
    """
    
    try:
        client = ollama.Client(host='http://host.docker.internal:11434')
        response = client.chat(
            model='qwen3.5:2b',
            messages=[{'role': 'user', 'content': prompt}],
            # Убрали format='json', чтобы модель не зависала на генерации пустоты
            options={'temperature': 0, 'num_ctx': 2048}
        )
        
        content = response['message']['content']
        
        print(f"DEBUG: Сырой ответ от Ollama: '{content}'", flush=True)
        
        if not content or not content.strip():
            return 0.0, "Модель вернула пустую строку."
            
        # Ищем JSON в тексте
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            json_str = match.group(0)
            result = json.loads(json_str)
            return float(result.get('score', 0.0)), result.get('reasoning', '')
        else:
            return 0.0, f"Модель не вернула JSON. Ответ: {content}"
            
    except Exception as e:
        print(f"Ошибка при вызове Ollama: {e}")
        return 0.0, f"Ошибка оценки: {str(e)}"