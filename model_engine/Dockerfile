FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN mkdir -p /workspace /artifacts /cache

COPY . /app/model_engine

CMD ["python", "-m", "unittest", "discover", "-s", "/app/model_engine/tests", "-v"]
