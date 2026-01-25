"""
Application settings using Pydantic Settings.
Loads from environment variables with optional .env file support.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database (PostgreSQL with pgvector)
    database_url: str = "postgresql+asyncpg://localhost:5432/paper_rag"

    # AWS S3 for PDF storage
    s3_bucket: str = "paper-rag-pdfs"
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # OpenAI Embeddings
    openai_api_key: str
    embedding_model: str = "text-embedding-3-large"
    # Using 1536 dimensions (reduced from 3072) because pgvector on RDS
    # limits indexes to 2000 dimensions. text-embedding-3-large supports
    # native dimension reduction via the API.
    vector_dimension: int = 1536
    batch_size: int = 100

    # Chunking settings
    max_chunk_tokens: int = 1000
    chunk_overlap: int = 150

    # Metadata extraction
    crossref_email: Optional[str] = None

    # Server settings
    server_name: str = "paper-rag"
    server_port: int = 8000
    log_level: str = "INFO"

    # API Key Authentication (for App Runner deployment)
    paperrag_api_key: Optional[str] = None

    # Bibliography
    default_bib_output: str = "./references.bib"
    bibtex_entry_type: str = "article"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
