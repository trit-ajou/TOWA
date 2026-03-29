FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN mkdir -p /workspace /artifacts /cache

COPY requirements-base.txt /app/model_engine/requirements-base.txt

# The base image stays small so contract tests can run quickly in CI and local dev.
RUN python3 -m pip install --no-cache-dir -r /app/model_engine/requirements-base.txt

COPY . /app/model_engine

CMD ["python3", "-m", "unittest", "discover", "-s", "/app/model_engine/tests", "-v"]
