# Dockerfile for Paper RAG Pipeline - RunPod Serverless Deployment
# GPU-enabled with CUDA support for accelerated PDF processing

# Use RunPod's PyTorch base image with CUDA support
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV DOCLING_DEVICE=cuda
ENV HF_HOME=/runpod-volume/cache/huggingface
ENV TRANSFORMERS_CACHE=/runpod-volume/cache/huggingface

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PDF processing
    poppler-utils \
    # OCR support
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    # Image processing
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    # Utilities
    curl \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements files first (for Docker layer caching)
COPY requirements.txt requirements-runpod.txt ./

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-runpod.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY handler.py ./

# Pre-cache Docling models to avoid download at runtime
# This significantly reduces cold start time
RUN python -c "from docling.document_converter import DocumentConverter; print('Docling models cached')" || true

# Pre-cache tokenizer
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); print('Tokenizer cached')" || true

# Create necessary directories (will be overridden by volume mounts)
RUN mkdir -p /app/data/lancedb /app/data/pdfs /app/data/bibs /app/data/logs

# Set default config path for RunPod
ENV CONFIG_PATH=/app/config/config-runpod.yaml

# Expose port for HTTP server
EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command - start the RunPod handler
# The handler will start the HTTP server in serverless mode
CMD ["python", "handler.py"]
