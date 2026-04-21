# ── Stage 1: Base image ───────────────────────────────────────────────────────
# Python 3.11 slim — smaller image, same Python version as your local install
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Prevents Python from writing .pyc files (not needed in containers)
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures print statements and logs appear immediately (no buffering)
ENV PYTHONUNBUFFERED=1

# ── Stage 2: Install dependencies ────────────────────────────────────────────
# Copy requirements first — Docker caches this layer
# If requirements.txt hasn't changed, Docker skips the pip install on rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 3: Copy application code ───────────────────────────────────────────
COPY app/ ./app/

# ── Stage 4: Run the server ───────────────────────────────────────────────────
# uvicorn is the ASGI server that runs FastAPI
# --host 0.0.0.0 makes it reachable from outside the container
# --port 8000 is the internal port (mapped to host in docker-compose.yml)
# --reload enables auto-restart when code changes (development only)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
