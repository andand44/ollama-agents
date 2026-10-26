import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5433/agent_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")