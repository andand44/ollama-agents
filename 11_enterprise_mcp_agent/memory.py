import redis
import json
import config

# decode_responses=True автоматически конвертирует байты в строки
r = redis.from_url(config.REDIS_URL, decode_responses=True)

def save_message(session_id: str, role: str, content: str):
    """Сохраняет сообщение в историю и обрезает её до 10 последних."""
    msg = json.dumps({"role": role, "content": content})
    r.rpush(f"chat:{session_id}", msg)
    # Оставляем только последние 10 сообщений (5 пар вопрос-ответ), чтобы не переполнять контекст
    r.ltrim(f"chat:{session_id}", -10, -1)

def get_history(session_id: str) -> list[dict]:
    """Возвращает историю диалога."""
    msgs = r.lrange(f"chat:{session_id}", 0, -1)
    return [json.loads(m) for m in msgs]