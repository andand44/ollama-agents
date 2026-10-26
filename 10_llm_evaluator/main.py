from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import database
import models
import llm_judge

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="LLM Evaluator Service")

class EvaluationCreate(BaseModel):
    question: str
    expected_answer: str
    actual_answer: str

@app.get("/")
def read_root():
    return {"message": "LLM Evaluator is running"}

@app.post("/evaluate")
def create_evaluation(evaluation: EvaluationCreate, db: Session = Depends(database.get_db)):
    # 1. Вызываем нашего судью из Ollama
    score, reasoning = llm_judge.evaluate_answer(
        evaluation.question, 
        evaluation.expected_answer, 
        evaluation.actual_answer
    )
    
    # 2. Сохраняем в PostgreSQL
    db_eval = models.Evaluation(
        question=evaluation.question,
        expected_answer=evaluation.expected_answer,
        actual_answer=evaluation.actual_answer,
        score=score,
        judge_reasoning=reasoning
    )
    db.add(db_eval)
    db.commit()
    db.refresh(db_eval)
    
    # 3. Возвращаем результат пользователю
    return {
        "id": db_eval.id,
        "score": db_eval.score,
        "reasoning": db_eval.judge_reasoning
    }
    
def evaluate_answer(question: str, expected: str, actual: str) -> tuple[float, str]:
    prompt = f"""
    Ты строгий эксперт по оценке качества ИИ. 
    Оцени фактическую точность и релевантность ответа.
    
    Вопрос: {question}
    Эталонный ответ: {expected}
    Ответ модели: {actual}
    
    Верни ответ СТРОГО в формате JSON без каких-либо других слов:
    {{"score": 8.5, "reasoning": "Краткое объяснение почему такая оценка"}}
    """
    
    try:
        client = ollama.Client(host='http://host.docker.internal:11434')
        response = client.chat(
            model='qwen3.5:2b',
            messages=[{'role': 'user', 'content': prompt}],
            format='json',
            options={'temperature': 0, 'num_ctx': 2048} # Уменьшили контекст для стабильности
        )
        
        content = response['message']['content']
        
        # Защита от галлюцинаций: вырезаем JSON из любого текста
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