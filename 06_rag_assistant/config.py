MODEL_NAME = 'qwen2.5:3b'
NUM_CTX = 3072   # Чуть больше, чем в 5-м проекте — 3 чанка + вопрос
TEMPERATURE = 0.2
MIN_SCORE = 0.0   # Порог отсечения для RAG