# Bastion Host Cleanup Guide

This guide walks you through reversing the AWS infrastructure changes made for RDS access via SSH tunnel. Items are ordered by **priority** (cost and security impact).

---

## Priority 1: Stop/Terminate EC2 Bastion Instance (HIGH)

**Why:** Running EC2 instances incur hourly charges (~$8.50/month for t2.micro after free tier).

**Option A: Stop (Recommended if you'll need it again)**
1. EC2 Console → Instances → select `geppetto-bastion`
2. Instance state → **Stop instance**
3. Cost: $0 while stopped (only EBS storage ~$0.80/month for 8GB)

**Option B: Terminate (Permanent removal)**
1. EC2 Console → Instances → select `geppetto-bastion`
2. Instance state → **Terminate instance**
3. Cost: $0 (everything deleted)

**Note:** If you stop the instance, the public IP will change when you restart it. Update your SSH tunnel command accordingly.

---

## Priority 2: Revert Local .env File (MEDIUM)

**Why:** Your local `.env` points to `localhost:15432` which requires the SSH tunnel. If you deploy to AWS or the tunnel isn't running, the app won't connect.

**Action:** Edit `/Users/joe/python/paper-rag-pipeline/.env`:

```bash
# Change FROM (tunnel):
DATABASE_URL=postgresql+asyncpg://geppetto_admin:...@localhost:15432/paper_rag

# Change TO (direct RDS - for AWS deployment):
DATABASE_URL=postgresql+asyncpg://geppetto_admin:...@geppetto-production-db.cu58600ig5br.us-east-1.rds.amazonaws.com:5432/paper_rag
```

**When to revert:**
- Before deploying to AWS (Lambda, ECS, AgentCore)
- If you won't be doing local development against RDS

---

## Priority 3: Delete Bastion Security Group (LOW)

**Why:** Unused security groups have no cost, but clutter your console and could be mistakenly attached to other resources.

**Prerequisites:** Must terminate (not just stop) the bastion instance first.

**Action:**
1. EC2 Console → Security Groups
2. Select `geppetto-bastion-sg`
3. Actions → **Delete security group**

---

## Priority 4: Remove RDS Security Group Inbound Rule (LOW)

**Why:** Leaving the rule doesn't cost anything, but it's good hygiene to remove unused rules. The rule only allows traffic from the bastion security group, so it's harmless if the bastion is terminated.

**Action:**
1. EC2 Console → Security Groups → `geppetto-production-rds-sg`
2. Edit inbound rules
3. Delete the rule: PostgreSQL (5432) from `geppetto-bastion-sg`
4. Save rules

---

## Priority 5: Delete EC2 Key Pair (OPTIONAL)

**Why:** Key pairs have no cost. Keep it if you might create another bastion later.

**Action (AWS Console):**
1. EC2 Console → Key Pairs
2. Select `geppetto-bastion-key`
3. Actions → **Delete**

**Action (Local):**
```bash
rm ~/.ssh/geppetto-bastion-key.pem
```

---

## Quick Reference: What Costs Money

| Resource | Running Cost | Stopped Cost |
|----------|-------------|--------------|
| EC2 t2.micro | ~$8.50/month | $0 |
| EBS volume (8GB) | — | ~$0.80/month |
| Security Groups | $0 | $0 |
| Key Pairs | $0 | $0 |
| RDS (already existed) | unchanged | unchanged |

---

## Resuming Development Later

If you stopped (not terminated) the bastion and want to use it again:

1. **Start the instance:**
   - EC2 Console → Instances → select `geppetto-bastion` → Instance state → Start

2. **Get the new public IP** (it changes after stop/start)

3. **Update and run the SSH tunnel:**
   ```bash
   ssh -i ~/.ssh/geppetto-bastion-key.pem -L 15432:geppetto-production-db.cu58600ig5br.us-east-1.rds.amazonaws.com:5432 ec2-user@NEW_PUBLIC_IP -N -f
   ```

4. **Update .env** back to localhost:15432 if needed

---

## Full Cleanup Checklist

Use this if you want to completely remove everything:

- [ ] Terminate EC2 instance `geppetto-bastion`
- [ ] Delete security group `geppetto-bastion-sg`
- [ ] Remove inbound rule from `geppetto-production-rds-sg`
- [ ] Delete key pair `geppetto-bastion-key` (AWS Console)
- [ ] Delete local key: `rm ~/.ssh/geppetto-bastion-key.pem`
- [ ] Revert `.env` to use direct RDS endpoint
