"""
AWS S3 service for PDF storage.
Handles upload, download, and pre-signed URL generation.
"""

import logging
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service for managing PDF files in AWS S3.

    Provides methods for:
    - Uploading PDFs from local files or bytes
    - Downloading PDFs as bytes
    - Generating pre-signed URLs for direct access
    - Deleting PDFs
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Initialize S3 service.

        Args:
            bucket: S3 bucket name (defaults to settings.s3_bucket)
            region: AWS region (defaults to settings.aws_region)
        """
        settings = get_settings()

        self.bucket = bucket or settings.s3_bucket
        self.region = region or settings.aws_region

        # Initialize S3 client
        # Uses environment variables or IAM role for credentials
        self._client = boto3.client(
            "s3",
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        logger.info(f"S3Service initialized: bucket={self.bucket}, region={self.region}")

    def _generate_s3_key(self, bibtex_key: str) -> str:
        """
        Generate S3 object key for a paper.

        Args:
            bibtex_key: BibTeX citation key

        Returns:
            S3 object key (e.g., "pdfs/Smith2024.pdf")
        """
        return f"pdfs/{bibtex_key}.pdf"

    async def upload_pdf_from_file(
        self,
        file_path: Path,
        bibtex_key: str,
    ) -> str:
        """
        Upload a PDF file to S3.

        Args:
            file_path: Local path to the PDF file
            bibtex_key: BibTeX citation key (used for S3 key)

        Returns:
            S3 key where the file was stored

        Raises:
            FileNotFoundError: If the local file doesn't exist
            ClientError: If S3 upload fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        s3_key = self._generate_s3_key(bibtex_key)

        try:
            self._client.upload_file(
                str(file_path),
                self.bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": "application/pdf",
                    "Metadata": {
                        "bibtex_key": bibtex_key,
                    },
                },
            )
            logger.info(f"Uploaded PDF to s3://{self.bucket}/{s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"Failed to upload PDF to S3: {e}")
            raise

    async def upload_pdf_from_bytes(
        self,
        pdf_bytes: bytes,
        bibtex_key: str,
    ) -> str:
        """
        Upload PDF bytes to S3.

        Args:
            pdf_bytes: PDF file content as bytes
            bibtex_key: BibTeX citation key (used for S3 key)

        Returns:
            S3 key where the file was stored

        Raises:
            ClientError: If S3 upload fails
        """
        s3_key = self._generate_s3_key(bibtex_key)

        try:
            self._client.put_object(
                Body=pdf_bytes,
                Bucket=self.bucket,
                Key=s3_key,
                ContentType="application/pdf",
                Metadata={
                    "bibtex_key": bibtex_key,
                },
            )
            logger.info(f"Uploaded PDF to s3://{self.bucket}/{s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"Failed to upload PDF to S3: {e}")
            raise

    async def download_pdf(self, s3_key: str) -> bytes:
        """
        Download a PDF from S3.

        Args:
            s3_key: S3 object key

        Returns:
            PDF content as bytes

        Raises:
            ClientError: If download fails (e.g., file not found)
        """
        try:
            response = self._client.get_object(
                Bucket=self.bucket,
                Key=s3_key,
            )
            pdf_bytes = response["Body"].read()
            logger.info(f"Downloaded PDF from s3://{self.bucket}/{s3_key} ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except ClientError as e:
            logger.error(f"Failed to download PDF from S3: {e}")
            raise

    async def download_pdf_by_key(self, bibtex_key: str) -> bytes:
        """
        Download a PDF by its BibTeX key.

        Args:
            bibtex_key: BibTeX citation key

        Returns:
            PDF content as bytes

        Raises:
            ClientError: If download fails
        """
        s3_key = self._generate_s3_key(bibtex_key)
        return await self.download_pdf(s3_key)

    async def get_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a pre-signed URL for direct PDF access.

        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL string

        Raises:
            ClientError: If URL generation fails
        """
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": s3_key,
                },
                ExpiresIn=expiration,
            )
            logger.debug(f"Generated presigned URL for {s3_key}")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def get_presigned_url_by_key(
        self,
        bibtex_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a pre-signed URL by BibTeX key.

        Args:
            bibtex_key: BibTeX citation key
            expiration: URL expiration time in seconds

        Returns:
            Pre-signed URL string
        """
        s3_key = self._generate_s3_key(bibtex_key)
        return await self.get_presigned_url(s3_key, expiration)

    async def delete_pdf(self, s3_key: str) -> bool:
        """
        Delete a PDF from S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if deletion was successful

        Raises:
            ClientError: If deletion fails
        """
        try:
            self._client.delete_object(
                Bucket=self.bucket,
                Key=s3_key,
            )
            logger.info(f"Deleted PDF from s3://{self.bucket}/{s3_key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete PDF from S3: {e}")
            raise

    async def delete_pdf_by_key(self, bibtex_key: str) -> bool:
        """
        Delete a PDF by its BibTeX key.

        Args:
            bibtex_key: BibTeX citation key

        Returns:
            True if deletion was successful
        """
        s3_key = self._generate_s3_key(bibtex_key)
        return await self.delete_pdf(s3_key)

    async def pdf_exists(self, s3_key: str) -> bool:
        """
        Check if a PDF exists in S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if the PDF exists
        """
        try:
            self._client.head_object(
                Bucket=self.bucket,
                Key=s3_key,
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    async def pdf_exists_by_key(self, bibtex_key: str) -> bool:
        """
        Check if a PDF exists by BibTeX key.

        Args:
            bibtex_key: BibTeX citation key

        Returns:
            True if the PDF exists
        """
        s3_key = self._generate_s3_key(bibtex_key)
        return await self.pdf_exists(s3_key)
