FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN useradd --system --no-create-home agent
COPY --from=builder /opt/venv /opt/venv
COPY app/ app/
COPY utils/ utils/

USER agent
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import os, urllib.request; port = os.getenv('PORT') or '8000'; urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).close()"]

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
