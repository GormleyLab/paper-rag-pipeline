FROM python:3.12-slim-bookworm

WORKDIR /app

# System dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY config/ config/

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    AWS_REGION=us-east-1

# Non-root user for security
RUN useradd -m -u 1000 apprunner
USER apprunner

# App Runner uses PORT env var (default 8080)
EXPOSE 8080

# Entry point - uses PORT from environment
CMD ["python", "-m", "src.mcp_http_server"]
