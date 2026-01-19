# Troubleshooting Guide

## Common Issues and Solutions

### Database Connection Issues

**Issue**: `Connection refused` or `could not connect to server`

**Cause**: PostgreSQL server is not running or connection details are incorrect.

**Solution**:
1. Verify PostgreSQL is running:
   ```bash
   pg_isready -h localhost -p 5432
   ```
2. Check DATABASE_URL in `.env`:
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
   ```
3. Verify the database exists and user has access

### pgvector Extension Missing

**Issue**: `type "vector" does not exist`

**Cause**: The pgvector extension is not installed or enabled.

**Solution**:
```sql
-- Connect to your database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

For RDS, ensure you're using a version that supports pgvector (PostgreSQL 15+).

### Migration Errors

**Issue**: Alembic migrations fail

**Solution**:
1. Check the database connection:
   ```bash
   alembic current
   ```
2. If stuck, check alembic_version table:
   ```sql
   SELECT * FROM paper_rag.alembic_version;
   ```
3. Reset migrations if needed (WARNING: destroys data):
   ```sql
   DROP SCHEMA paper_rag CASCADE;
   ```
   Then run: `alembic upgrade head`

### S3 Connection Issues

**Issue**: `NoCredentialsError` or `AccessDenied`

**Cause**: AWS credentials are not configured or insufficient permissions.

**Solution**:
1. Check credentials in `.env`:
   ```bash
   AWS_ACCESS_KEY_ID=your-key
   AWS_SECRET_ACCESS_KEY=your-secret
   AWS_REGION=us-east-1
   ```
2. Or use IAM role (recommended for EC2/ECS)
3. Verify S3 bucket exists and policy allows access

### S3 Bucket Not Found

**Issue**: `NoSuchBucket`

**Solution**:
1. Verify bucket name in `.env`:
   ```bash
   S3_BUCKET=paper-rag-pdfs
   ```
2. Check bucket exists in correct region
3. Create bucket if needed:
   ```bash
   aws s3 mb s3://paper-rag-pdfs --region us-east-1
   ```

### OpenAI API Key Not Found

**Issue**: `OpenAI API key not found in environment`

**Solution**: Ensure `OPENAI_API_KEY` is set in your `.env` file:
```bash
OPENAI_API_KEY=sk-your-key-here
```

### OpenAI Rate Limits

**Issue**: `RateLimitError` during embedding generation

**Solution**:
1. Reduce batch_size in settings
2. The system has automatic retry with exponential backoff
3. Consider upgrading your OpenAI tier for higher limits

### PDF Processing Errors

**Issue**: Papers fail to process

**Common Causes**:
- Encrypted/password-protected PDFs (not supported)
- Corrupted PDF files
- Very large PDFs (>100MB)

**Solution**:
1. Check server logs for specific error
2. Verify PDF opens in a standard viewer
3. Try re-downloading the PDF
4. Large PDFs may need more memory

### Multiprocessing Resource Tracker Warning

**Issue**: Warning about leaked semaphore objects at shutdown

```
resource_tracker: There appear to be 1 leaked semaphore objects to clean up at shutdown
```

**Cause**: Docling's `DocumentConverter` uses multiprocessing internally.

**Impact**: This is a **non-critical warning**. Python cleans up resources automatically.

**Solution**: The warning is suppressed in the codebase. If you see it, it doesn't affect functionality.

### Server Won't Start

**Issue**: MCP HTTP server fails to start

**Common Causes**:
1. Port 8000 already in use
2. Missing environment variables
3. Database connection failure

**Solution**:
1. Check port availability:
   ```bash
   lsof -i :8000
   ```
2. Kill existing process or use different port
3. Verify all required environment variables are set
4. Check database connectivity

### Search Returns No Results

**Issue**: `search_papers` returns empty results

**Possible Causes**:
1. Database is empty
2. Query doesn't match indexed content
3. Filter parameters too restrictive

**Solution**:
1. Check database stats:
   ```json
   {"name": "database_stats", "arguments": {}}
   ```
2. Try a broader query without filters
3. Verify papers were indexed successfully

### Duplicate Paper Detection

**Issue**: Paper not being added (silently skipped)

**Cause**: PDF hash matches an existing paper.

**Solution**: This is expected behavior. The system detects duplicates by PDF content hash. If you need to re-index, delete the paper first:
```json
{"name": "delete_paper", "arguments": {"bibtex_key": "Smith2024"}}
```

## Logging

Server logs are written to stdout. For detailed debugging:

1. Set LOG_LEVEL=DEBUG in environment
2. Check stdout/stderr for specific error messages
3. For batch processing, logs are written to stdout

## Getting Help

1. Check stdout/stderr for specific error messages
2. Review [CLAUDE.md](CLAUDE.md) for developer documentation
3. File issues on the project repository
