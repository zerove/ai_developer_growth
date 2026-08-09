# Multi-stage Dockerfile for AI Developer Growth Framework & MCP Server

FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . /app

EXPOSE 8000 5000

ENV PYTHONUNBUFFERED=1

CMD ["python", "ai-dev-framework/core/jcode_ai_native_workflow.py"]
