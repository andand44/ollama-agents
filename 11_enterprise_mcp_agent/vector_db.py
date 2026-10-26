from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_core.documents import Document
import config

# Настройка эмбеддингов через Ollama
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=config.OLLAMA_URL
)

client = QdrantClient(url=config.QDRANT_URL)
collection_name = "knowledge_base"

# Явно проверяем, существует ли коллекция, и создаем её при необходимости
try:
    client.get_collection(collection_name)
except Exception:
    # Модель nomic-embed-text выдает векторы размерностью 768
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
    )

# Инициализируем хранилище
vector_store = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embeddings,
)

def add_text_to_knowledge_base(text: str, metadata: dict = None):
    """Добавляет текст в векторную базу."""
    doc = Document(page_content=text, metadata=metadata or {})
    vector_store.add_documents([doc])

def search_knowledge_base(query: str, k: int = 2) -> str:
    """Ищет похожие по смыслу куски текста."""
    try:
        docs = vector_store.similarity_search(query, k=k)
        if not docs:
            return "В базе знаний ничего не найдено."
        return "\n\n".join([d.page_content for d in docs])
    except Exception as e:
        return f"Ошибка поиска в базе: {e}"