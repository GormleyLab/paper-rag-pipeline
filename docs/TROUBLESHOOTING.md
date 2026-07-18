# Troubleshooting Guide

## Common Issues and Solutions

### Database Connection Issues

**Issue**: `Connection refused` or `could not connect to server`

**Cause**: PostgreSQL server is not running, connection details are incorrect, or SSH tunnel is not active.

**Solution**:

**For local PostgreSQL:**
1. Verify PostgreSQL is running:
   ```bash
   pg_isready -h localhost -p 5432
   ```
2. Check DATABASE_URL in `.env`

**For AWS RDS via SSH tunnel:**
1. Check if tunnel is running:
   ```bash
   ps aux | grep ssh | grep 15432
   ```
2. Verify DATABASE_URL uses tunnel port:
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:15432/paper_rag
   ```
3. Restart tunnel if needed (see [SSH Tunnel Issues](#ssh-tunnel-issues) below)

### pgvector Extension Missing

**Issue**: `type "vector" does not exist`

**Cause**: The pgvector extension is not installed or enabled.

**Solution**:
```sql
-- Connect to your database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

For RDS, ensure you're using a version that supports pgvector (PostgreSQL 15+).

### pgvector Dimension Limit

**Issue**: `column cannot have more than 2000 dimensions for hnsw index`

**Cause**: AWS RDS pgvector (v0.7.x) limits HNSW and IVFFlat indexes to 2000 dimensions.

**Solution**: This project uses 1536-dimensional embeddings (text-embedding-3-large with reduced dimensions) to stay under the limit. If you modified the dimensions, ensure `vector_dimension` in settings.py is ≤2000.

### SSH Tunnel Issues

**Issue**: `Connection refused` on localhost:15432

**Cause**: SSH tunnel to bastion host is not running.

**Solution**:
1. Check if tunnel is active:
   ```bash
   ps aux | grep ssh | grep 15432
   ```
2. Start the tunnel with keepalive options:
   ```bash
   ssh -i ~/.ssh/your-bastion-key.pem \
       -o ServerAliveInterval=60 \
       -o ServerAliveCountMax=3 \
       -L 15432:YOUR_RDS_ENDPOINT:5432 \
       ec2-user@BASTION_PUBLIC_IP -N -f
   ```
3. Verify bastion EC2 instance is running in AWS Console

---

**Issue**: SSH tunnel drops after idle period or overnight

**Cause**: Network timeouts, Mac sleep, or missing keepalive configuration.

**Solution**:
1. Use `ServerAliveInterval=60` in SSH command (sends keepalive every 60 seconds)
2. For overnight runs, prevent Mac sleep:
   ```bash
   caffeinate -i python scripts/initial_setup.py /path/to/pdfs
   ```
3. If bastion was stopped, restart it and note the new public IP

---

**Issue**: Wrong DATABASE_URL for environment

**Cause**: Using direct RDS endpoint locally or tunnel endpoint in AWS.

**Solution**:
| Environment | DATABASE_URL Host |
|-------------|-------------------|
| Local development | `localhost:15432` (via tunnel) |
| AWS deployment | Direct RDS endpoint |

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

---

**Issue**: Script hangs on specific PDF during metadata extraction

**Cause**: The `pdf2bib` library can hang indefinitely when fetching metadata from external APIs (CrossRef, etc.) for certain PDFs.

**Solution**: The system has a **60-second timeout** for pdf2bib. If it times out:
1. The system automatically falls back to alternative extraction methods (CrossRef via DOI, arXiv, PDF metadata, text parsing)
2. A warning is logged: `pdf2bib timed out after 60s for {filename}`
3. The paper is still processed using fallback methods

If you see repeated hangs on the same PDF:
1. Move the problematic PDF temporarily: `mv problem.pdf /tmp/`
2. Re-run the import script
3. Add the PDF back later or process it manually

---

**Issue**: Import script interrupted, need to resume

**Cause**: Script was stopped (Ctrl+C, system sleep, tunnel drop, etc.)

**Solution**: Simply re-run the same command:
```bash
python scripts/initial_setup.py /path/to/your/pdfs
```
The script detects already-processed papers by PDF hash and skips them automatically.

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

### MCP Client Cannot Connect

**Issue**: Claude Desktop or external MCP client cannot connect to server

**Cause**: The MCP server is running locally with an SSH tunnel to RDS, which only works for local clients.

**Solution**: For external client access, you must deploy the MCP server to AWS:
- The server needs to run inside the VPC to access RDS directly
- Deploy via AWS AgentCore, ECS, or EC2
- See [setup.md](setup.md#aws-agentcore-deployment) for deployment instructions

**For local testing only**: Use curl or local scripts to interact with `http://localhost:8000/mcp`

### AWS App Runner Deployment Issues

**Issue**: 401 Unauthorized on all requests

**Cause**: Missing or invalid API key in Authorization header.

**Solution**:
1. Verify API key is set in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id paperrag/api-key --query SecretString
   ```
2. Include `Authorization: Bearer <key>` header in requests
3. Check App Runner service has `PAPERRAG_API_KEY` in RuntimeEnvironmentSecrets

---

**Issue**: App Runner service fails to start

**Cause**: Database connection, missing secrets, or VPC configuration issues.

**Solution**:
1. Check App Runner service logs in AWS Console
2. Verify VPC Connector is correctly configured with subnets that can reach RDS
3. Ensure security groups allow traffic from App Runner to RDS on port 5432
4. Verify all secrets are accessible (DATABASE_URL, OPENAI_API_KEY, PAPERRAG_API_KEY)

---

**Issue**: Cold start taking too long (>10 seconds)

**Cause**: Container initialization overhead.

**Solution**:
1. This is normal for scale-to-zero; first request after idle has ~2-3s cold start
2. For lower latency, configure minimum instances in App Runner (increases cost)
3. Consider using health check pings to keep warm if needed

---

**Issue**: 502 Bad Gateway after deployment

**Cause**: Health check failing or application crash on startup.

**Solution**:
1. Check that health endpoint `/health` is accessible (no auth required)
2. Verify PORT environment variable is used (default 8080)
3. Check CloudWatch logs for Python errors
4. Test container locally first:
   ```bash
   docker run -p 8080:8080 -e PORT=8080 -e DATABASE_URL=... your-image
   curl http://localhost:8080/health
   ```

---

### AWS AgentCore Deployment Issues

**Issue**: Container fails to start with `-32603` internal error and mismatched JSON-RPC ID

**Possible Causes**:

1. **Port mismatch**: FastMCP configured with wrong port
   - AWS AgentCore expects port 8000 (default)
   - Check `mcp_http_server.py` doesn't specify `port=8080` or other non-default port
   - FastMCP constructor should be: `FastMCP("paper-rag", stateless_http=True, host="0.0.0.0")`

2. **pdf2bib permission error**: Container runs as non-root user
   - The `pdf2bib` library tries to write `settings.ini` on import
   - This fails with `PermissionError` in containerized environments
   - Check CloudWatch logs for: `PermissionError: [Errno 13] Permission denied: .../pdf2bib/settings.ini`

**Solution**: The codebase handles these issues:
- Port defaults to 8000 (matches Dockerfile EXPOSE and AgentCore)
- pdf2bib import is lazy and catches PermissionError gracefully
- Metadata extraction falls back to other methods if pdf2bib is unavailable

**Debugging tips**:
1. Check CloudWatch logs: `/aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT`
2. Look for runtime-logs stream (not just otel-rt-logs)
3. If ID mismatch in error response, the issue is before the container starts
4. Test locally first: `python -m src.mcp_http_server`

---

**Issue**: AgentCore shows READY but invocations fail

**Cause**: Container crashes on startup before processing any requests.

**Solution**:
1. Check CloudWatch logs for Python tracebacks
2. Verify environment variables are set in Dockerfile (DATABASE_URL, OPENAI_API_KEY, S3_BUCKET)
3. Test container locally if possible
4. Re-deploy with `agentcore deploy --auto-update-on-conflict`

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

### "no pg_hba.conf entry ... no encryption" from DB-backed tools

**Issue**: `search_papers`, `database_stats`, etc. fail with:
```
no pg_hba.conf entry for host "10.0.x.x", user "...", database "paper_rag", no encryption
```

**Cause**: This error is usually a red herring. asyncpg defaults to `sslmode=prefer`: it first
attempts an SSL connection, and if that attempt fails with an authorization error (including a
wrong password), it silently retries **without SSL**. RDS enforces `rds.force_ssl=1`, so the
plaintext retry is rejected with the "no encryption" error above — masking the real failure.
Check the RDS server log for the paired error:
```bash
aws rds download-db-log-file-portion --db-instance-identifier geppetto-production-db \
  --log-file-name error/postgresql.log.$(date -u +%Y-%m-%d-%H) --starting-token 0 --output text
```
A preceding `password authentication failed for user ...` line means the `paperrag/database-url`
secret is stale (e.g., the DB master password was rotated but only
`geppetto-production/database-url` was updated). Update the secret and run
`aws apprunner start-deployment` — App Runner only resolves secrets at instance launch.

The engine now pins `connect_args={"ssl": "require"}` (`src/core/database.py`) so the plaintext
fallback cannot mask the underlying error again.

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
