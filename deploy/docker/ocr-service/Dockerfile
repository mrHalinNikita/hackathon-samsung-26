FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    tesseract-ocr-osd \
    libgl1 \
    libglib2.0-0 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-ocr.txt .
RUN pip install --no-cache-dir -r requirements-ocr.txt

COPY src/services/ocr ./src/services/ocr
COPY src/config ./src/config
COPY src/core ./src/core

RUN mkdir -p /tmp/ocr_cache && chmod 777 /tmp/ocr_cache

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.services.ocr.main:app", "--host", "0.0.0.0", "--port", "8000"]