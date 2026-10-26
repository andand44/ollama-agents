from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app)

# Мокаем функцию оценки, чтобы тест не зависел от Ollama
@patch("llm_judge.evaluate_answer")
def test_evaluate_endpoint(mock_evaluate):
    # Говорим моку: "когда тебя вызовут, верни оценку 9.5 и вот такой текст"
    mock_evaluate.return_value = (9.5, "Отличный ответ, факты совпадают.")
    
    payload = {
        "question": "2+2?",
        "expected_answer": "4",
        "actual_answer": "4"
    }
    
    response = client.post("/evaluate", json=payload)
    
    # Проверяем, что API ответил успешно (200)
    assert response.status_code == 200
    data = response.json()
    
    # Проверяем, что данные сохранились и вернулись корректно
    assert data["score"] == 9.5
    assert data["reasoning"] == "Отличный ответ, факты совпадают."
    assert "id" in data


def test_evaluate_validation_error():
    # Проверяем, что API не упадет, если прислать неполные данные
    payload = {"question": "2+2?"} # Забыли expected_answer и actual_answer
    
    response = client.post("/evaluate", json=payload)
    
    # FastAPI должен вернуть 422 (Ошибка валидации)
    assert response.status_code == 422