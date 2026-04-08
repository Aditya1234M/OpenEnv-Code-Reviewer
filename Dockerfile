FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY server ./server
COPY data ./data
COPY README.md ./

RUN pip install --upgrade pip && pip install -e .

EXPOSE 7860

CMD ["sh", "-c", "python -m uvicorn src.server:app --host 0.0.0.0 --port ${PORT}"]
