from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
import redis
from qdrant_client import QdrantClient
import config
import memory
import vector_db
import agent  # Импортируем наш граф

app = FastAPI(title="Enterprise MCP Agent")

class KnowledgeAdd(BaseModel):
    text: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.get("/health")
def health_check():
    status = {"api": "ok", "redis": "unknown", "qdrant": "unknown"}
    try:
        redis.from_url(config.REDIS_URL).ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = str(e)
    try:
        QdrantClient(url=config.QDRANT_URL).get_collections()
        status["qdrant"] = "ok"
    except Exception as e:
        status["qdrant"] = str(e)
    return status

@app.post("/add_knowledge")
def add_knowledge(data: KnowledgeAdd):
    vector_db.add_text_to_knowledge_base(data.text)
    return {"status": "added", "text_length": len(data.text)}

@app.post("/chat")
async def chat(req: ChatRequest):  # Обрати внимание на async
    history_data = memory.get_history(req.session_id)
    
    from langchain_core.messages import HumanMessage, AIMessage
    langchain_history = []
    for msg in history_data:
        if msg["role"] == "user":
            langchain_history.append(HumanMessage(content=msg["content"]))
        else:
            langchain_history.append(AIMessage(content=msg["content"]))
            
    langchain_history.append(HumanMessage(content=req.message))
    
    inputs = {"messages": langchain_history}
    # Используем ainvoke вместо invoke
    final_state = await agent.app_graph.ainvoke(inputs)
    
    final_answer = final_state["messages"][-1].content
    
    memory.save_message(req.session_id, "user", req.message)
    memory.save_message(req.session_id, "assistant", final_answer)
    
    return {"answer": final_answer}