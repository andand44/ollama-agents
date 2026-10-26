FROM python:3.15-slim

# Устанавливаем системные зависимости (компилятор gcc и другие)
# Они нужны, потому что некоторые новые библиотеки еще не имеют готовых бинарников для Python 3.15
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]