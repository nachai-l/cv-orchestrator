# Dockerfile

# 1) Base image
FROM python:3.11-slim AS base

# 2) Environment setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Optional: avoid lengthy DNS delays in some environments
ENV UVICORN_WORKERS=1

# 3) Workdir
WORKDIR /app

# 4) Install system deps (if needed, keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# 5) Install Python deps
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 6) Copy source code
COPY . .

# 7) Expose port (Cloud Run will map it)
EXPOSE 8080

# 8) Default command: run FastAPI with uvicorn
# Cloud Run expects the service to listen on $PORT (default 8080)
ENV PORT=8080

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
