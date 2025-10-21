# Neo4j Backup Strategies for Fly.io Deployment

## Overview

This document outlines comprehensive backup strategies for Neo4j deployed on Fly.io, from simple to enterprise-grade approaches. Choose the strategy that matches your reliability and complexity requirements.

## Executive Summary

**For production AI agent knowledge bases, you need automated backups.** Manual backup processes are unreliable and don't scale. This guide covers three automated approaches:

| Strategy | Automation | Recovery Window | Offsite | Complexity | Cost |
|----------|-----------|-----------------|---------|-----------|------|
| **Option 1: Fly Snapshots Only** | Automatic | 5 days | No | Low | Included |
| **Option 2: Local Backups + Snapshots** ✅ | Automatic | 30 days | No | Low-Medium | Included |
| **Option 3: S3 Backups + Snapshots** | Automatic | 90 days | Yes | Medium-High | +$1-5/mo |

---

## Option 1: Fly.io Volume Snapshots Only

### How It Works

Fly.io automatically creates daily snapshots of all volumes with a default 5-day retention period.

```bash
# View available snapshots
fly volumes snapshots list <volume-id>

# Restore from snapshot
fly volumes create <new-volume-name> \
  --snapshot-id <snapshot-id> \
  --size 10
```

### Automated Behavior

- ✅ Enabled by default
- ✅ Daily snapshots
- ✅ Configurable retention (1-60 days)
- ✅ Zero manual work
- ✅ Incremental storage (only changes consume space)

### Limitations & Risks

❌ **Single copy risk**: "If the host fails, any data stored between snapshot and failure is lost"
- Data written between backup (e.g., 2am) and failure (e.g., 4pm) = lost
- Not suitable as sole backup strategy

❌ **Short recovery window**: 5 days default
- If you don't notice corruption for 6 days, all snapshots are gone
- No 30-day restore points

❌ **Single point of failure**: Everything on Fly.io infrastructure
- If Fly data center fails, snapshots are inaccessible
- No offsite disaster recovery

❌ **Point-in-time recovery only**:
- Can only restore to snapshot moments (daily)
- Can't restore to arbitrary points during the day

### Recommendation

**Use as safety net only, not primary backup strategy.** Fly snapshots are good for:
- Hardware failures at the host level
- Quick recovery from infrastructure issues

They're insufficient for:
- Data corruption recovery (need multiple daily restore points)
- Disaster recovery (all data on one provider)
- Production knowledge bases with high reliability needs

---

## Option 2: Neo4j Local Backups + Fly Snapshots ✅ RECOMMENDED FOR MOST USERS

### How It Works

1. **Neo4j automated backup script** runs daily (via cron in container)
2. **Each backup stored locally** in persistent volume `/data/backups`
3. **30 daily backups retained** locally
4. **Fly snapshots** provide additional safety net
5. **Zero manual intervention** required

### Architecture

```
Fly.io Volume (10GB)
├── /data/databases/     (Neo4j active database)
├── /data/logs/          (Neo4j operational logs)
└── /data/backups/       (Daily backup chain)
    ├── neo4j_20251020_020000.backup
    ├── neo4j_20251019_020000.backup
    ├── neo4j_20251018_020000.backup
    └── ... (30 days of backups)

Daily Fly Snapshots (5 most recent)
├── snapshot_id_xyz1
├── snapshot_id_xyz2
└── ... (5 snapshots, oldest = 5 days)
```

### Implementation

#### Step 1: Create Backup Script

Create `neo4j-backup.sh` in your project:

```bash
#!/bin/sh
# neo4j-backup.sh - Daily Neo4j backup script
# Designed to run inside Neo4j container via cron

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/data/backups"
BACKUP_FILE="$BACKUP_DIR/neo4j_$TIMESTAMP.backup"
LOG_FILE="/data/logs/backup_$TIMESTAMP.log"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Run consistency check and backup
echo "[$(date)] Starting Neo4j backup..." >> "$LOG_FILE"

neo4j-admin database backup neo4j \
  --to-path="$BACKUP_FILE" \
  --check-consistency=true >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup successful: $BACKUP_FILE" >> "$LOG_FILE"
else
    echo "[$(date)] Backup failed!" >> "$LOG_FILE"
    exit 1
fi

# Cleanup: Keep only last 30 days of backups
echo "[$(date)] Cleaning old backups (keeping 30 days)..." >> "$LOG_FILE"
find "$BACKUP_DIR" -name "neo4j_*.backup" -mtime +30 -exec rm -rf {} \; >> "$LOG_FILE" 2>&1

echo "[$(date)] Backup routine complete" >> "$LOG_FILE"
```

#### Step 2: Create Dockerfile

Create `Dockerfile.neo4j`:

```dockerfile
FROM neo4j:5.25.0

# Install cron and curl for health checks
RUN apt-get update && apt-get install -y \
    dcron \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backup script
COPY neo4j-backup.sh /etc/cron.daily/neo4j-backup
RUN chmod +x /etc/cron.daily/neo4j-backup

# Run cron in foreground alongside Neo4j
CMD ["sh", "-c", "crond -f -l 2 & exec /docker-entrypoint.sh neo4j"]
```

#### Step 3: Configure Fly.toml

Add Neo4j service to `fly.toml`:

```toml
app = "rag-memory"

# Existing MCP Server service...

[[services]]
  name = "neo4j"
  internal_port = 7687
  processes = ["neo4j"]

  [services.tcp_checks]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"

# Persistent volume for Neo4j data + backups
[[mounts]]
  source = "neo4j_data"
  destination = "/data"
  initial_size = "10GB"

# Environment variables
[env]
  NEO4J_AUTH = "neo4j/change-me-to-secure-password"
  NEO4J_PLUGINS = '["apoc"]'  # Optional: Add APOC procedures
```

#### Step 4: Create Volume and Deploy

```bash
# Create persistent volume (if not exists)
fly volumes create neo4j_data \
  --size 10 \
  --region iad \
  --app rag-memory

# Deploy Neo4j service
fly deploy
```

### Automation Details

**Backup Timing:**
- Runs daily at 2:00 AM UTC (cron default)
- Execution time: ~5-10 minutes depending on database size
- Backup file size: ~200MB-1GB per backup (typical knowledge graphs)

**Retention Policy:**
- 30 daily backups = 30 days of restore points
- Oldest backup automatically deleted when 31st backup created
- Total disk usage: ~10-30GB for 30 backups

**Restoration Process:**

```bash
# SSH into Neo4j machine
fly ssh console -s neo4j

# List available backups
ls -lah /data/backups/

# Restore from backup (Neo4j must be stopped)
neo4j-admin database restore neo4j \
  --from-path=/data/backups/neo4j_20251015_020000.backup \
  --overwrite-existing=true

# Restart Neo4j
neo4j stop
neo4j start
```

### Advantages

✅ **Fully automated** - Zero manual intervention
✅ **30-day recovery window** - Can restore to any of last 30 days
✅ **Multiple restore points** - Not limited to snapshot moments
✅ **Simple implementation** - Single Dockerfile addition
✅ **Low cost** - No additional services
✅ **Fast recovery** - Backups are local (minutes to restore)
✅ **Data corruption recovery** - Can restore to pre-corruption state
✅ **Fly snapshots as safety net** - Extra layer of protection

### Disadvantages

❌ **All backups on same volume** - If volume hardware fails, backups are lost
❌ **Requires disk space** - ~10-30GB for 30 backups
❌ **Single provider risk** - Everything on Fly.io infrastructure
❌ **No offsite disaster recovery** - Fly.io data center failure = data inaccessible

### Monitoring & Alerting

Monitor backup health by checking logs:

```bash
# SSH into container
fly ssh console -s neo4j

# Check backup logs
tail -f /data/logs/backup_*.log

# Verify backup files exist
ls -lh /data/backups/ | tail -5
```

### When Backups Fail

**Common issues & solutions:**

1. **"Insufficient space"**
   - Increase volume size: `fly volumes extend neo4j_data --size 15`
   - Or reduce retention: Change `mtime +30` to `mtime +7` in backup script

2. **"Lock timeout"**
   - Neo4j database locked by active processes
   - Increase timeout in backup script or schedule backup during low usage

3. **Cron not running**
   - Verify cron is started: `ps aux | grep cron`
   - Check cron logs: `cat /var/log/syslog | grep CRON`

---

## Option 3: Neo4j Backups to AWS S3 + Fly Snapshots

### How It Works

1. **Neo4j backup script** runs daily (via cron)
2. **Each backup uploaded to AWS S3** immediately
3. **90 days of backups retained in S3** (long-term recovery)
4. **Local backups pruned to 3 days** (save disk space)
5. **Fly snapshots** provide quick local recovery
6. **S3 provides offsite disaster recovery**

### Architecture

```
Fly.io Volume (10GB + local backups only)
└── /data/backups/ (3 most recent backups only)

AWS S3 Bucket (Offsite, long-term storage)
├── neo4j/neo4j_20251020_020000.backup
├── neo4j/neo4j_20251019_020000.backup
└── ... (90 days of backups)

Recovery Options:
- Last 3 days: Restore from local backup (minutes)
- 4-90 days: Download from S3, restore (minutes-hours)
- Fly snapshots: Instant local recovery (seconds)
```

### Implementation

#### Step 1: Create AWS S3 Bucket

```bash
# Create S3 bucket for backups
aws s3 mb s3://rag-memory-neo4j-backups --region us-east-1

# Enable versioning (optional, for extra protection)
aws s3api put-bucket-versioning \
  --bucket rag-memory-neo4j-backups \
  --versioning-configuration Status=Enabled

# Setup lifecycle policy to delete backups after 90 days
aws s3api put-bucket-lifecycle-configuration \
  --bucket rag-memory-neo4j-backups \
  --lifecycle-configuration '{
    "Rules": [{
      "Id": "DeleteOldBackups",
      "Status": "Enabled",
      "Prefix": "neo4j/",
      "Expiration": {"Days": 90}
    }]
  }'
```

#### Step 2: Create IAM Credentials

```bash
# Create IAM user for backups
aws iam create-user --user-name neo4j-backup-bot

# Create access key
aws iam create-access-key --user-name neo4j-backup-bot

# Create policy for S3 access
cat > neo4j-backup-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::rag-memory-neo4j-backups",
        "arn:aws:s3:::rag-memory-neo4j-backups/*"
      ]
    }
  ]
}
EOF

# Attach policy to user
aws iam put-user-policy \
  --user-name neo4j-backup-bot \
  --policy-name S3BackupAccess \
  --policy-document file://neo4j-backup-policy.json
```

#### Step 3: Create S3 Backup Script

Create `neo4j-backup-s3.sh`:

```bash
#!/bin/sh
# neo4j-backup-s3.sh - Daily Neo4j backup to S3

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/data/backups"
BACKUP_FILE="$BACKUP_DIR/neo4j_$TIMESTAMP.backup"
LOG_FILE="/data/logs/backup_s3_$TIMESTAMP.log"

S3_BUCKET="rag-memory-neo4j-backups"
S3_KEY="neo4j/$TIMESTAMP.backup"
S3_REGION="us-east-1"

# Setup AWS credentials (from environment or ~/.aws/credentials)
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Neo4j backup to S3..." >> "$LOG_FILE"

# Take local backup
neo4j-admin database backup neo4j \
  --to-path="$BACKUP_FILE" \
  --check-consistency=true >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] Local backup successful: $BACKUP_FILE" >> "$LOG_FILE"
else
    echo "[$(date)] Local backup failed!" >> "$LOG_FILE"
    exit 1
fi

# Upload to S3
echo "[$(date)] Uploading to S3..." >> "$LOG_FILE"
aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/$S3_KEY" \
  --region "$S3_REGION" \
  --sse AES256 \
  --region "$S3_REGION" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] S3 upload successful" >> "$LOG_FILE"
else
    echo "[$(date)] S3 upload failed!" >> "$LOG_FILE"
    exit 1
fi

# Cleanup: Keep only last 3 days locally (save disk space)
echo "[$(date)] Cleaning old local backups (keeping 3 days)..." >> "$LOG_FILE"
find "$BACKUP_DIR" -name "neo4j_*.backup" -mtime +3 -exec rm -rf {} \; >> "$LOG_FILE" 2>&1

# S3 cleanup is handled by lifecycle policy
echo "[$(date)] Backup and S3 upload complete" >> "$LOG_FILE"
```

#### Step 4: Update Dockerfile

```dockerfile
FROM neo4j:5.25.0

# Install tools
RUN apt-get update && apt-get install -y \
    dcron \
    curl \
    awscli \
    && rm -rf /var/lib/apt/lists/*

# Copy backup script
COPY neo4j-backup-s3.sh /etc/cron.daily/neo4j-backup
RUN chmod +x /etc/cron.daily/neo4j-backup

# AWS credentials will be passed via Fly secrets
CMD ["sh", "-c", "crond -f -l 2 & exec /docker-entrypoint.sh neo4j"]
```

#### Step 5: Configure Fly.toml with Secrets

```toml
[[services]]
  name = "neo4j"
  internal_port = 7687
  processes = ["neo4j"]

# AWS credentials as Fly secrets (not in plain text)
```

Set secrets via command line:

```bash
fly secrets set \
  AWS_ACCESS_KEY_ID="your-access-key" \
  AWS_SECRET_ACCESS_KEY="your-secret-key" \
  --app rag-memory
```

### Restoration from S3

```bash
# List available backups in S3
aws s3 ls s3://rag-memory-neo4j-backups/neo4j/

# Download specific backup
aws s3 cp s3://rag-memory-neo4j-backups/neo4j/neo4j_20251015_020000.backup \
  ./neo4j_backup.backup

# Copy to machine
scp neo4j_backup.backup user@machine:/tmp/

# SSH and restore
fly ssh console -s neo4j
neo4j-admin database restore neo4j \
  --from-path=/tmp/neo4j_backup.backup \
  --overwrite-existing=true
```

### Advantages

✅ **Fully automated** - Zero manual work
✅ **90-day recovery window** - Long-term restore capability
✅ **Offsite storage** - AWS S3, completely separate infrastructure
✅ **Disaster recovery** - If Fly.io fails, data in S3
✅ **Scalable** - Backups don't consume Fly.io disk space
✅ **Cost-effective** - S3 storage is ~$1-5/month
✅ **Enterprise-grade** - Production-ready approach
✅ **Multiple safety layers** - Local backups + S3 + Fly snapshots

### Disadvantages

❌ **More complex setup** - AWS account + IAM credentials required
❌ **Additional cost** - AWS S3 (~$1-5/month for typical usage)
❌ **Slower long-term recovery** - Must download from S3 first
❌ **AWS dependency** - Requires AWS availability for disaster recovery
❌ **Credentials management** - Need to securely store AWS keys

### S3 Cost Estimation

For typical knowledge graph backups:

```
Backup size per day: ~500MB (typical)
Days retained: 90
Total storage: 45GB
S3 storage cost: 45GB × $0.023/GB/month = ~$1.04/month
Request costs: ~$0.10/month (minimal)
Total: ~$1.15/month
```

---

## Choosing Your Strategy

### Use Option 2 (Local Backups + Snapshots) IF:

✅ You want to get started quickly
✅ Your knowledge graph is <50GB
✅ 30-day recovery window is sufficient
✅ You don't need offsite disaster recovery
✅ You want minimal complexity
✅ Cost is a primary concern

**Cost: $0 (included in Fly.io machine cost)**

### Use Option 3 (S3 Backups) IF:

✅ You need 90+ day recovery window
✅ Knowledge graph is mission-critical
✅ You want true offsite disaster recovery
✅ You can accept additional ~$1-5/month cost
✅ You're familiar with AWS

**Cost: Fly.io + S3 (~$1-5/month for backups)**

### Never Use Option 1 (Snapshots Only) FOR:

❌ Production knowledge bases
❌ If data corruption recovery is needed
❌ If you need recovery points beyond 5 days
❌ As sole backup strategy

---

## Transition Strategy

**Start with Option 2:**
1. Deploy Neo4j with local backup script
2. Monitor backups for 1-2 weeks
3. Verify backup integrity

**Upgrade to Option 3 when:**
1. Knowledge graph becomes mission-critical
2. You want 90-day recovery window
3. Budget allows for S3 costs

---

## Disaster Recovery Runbook

### Scenario 1: Data Corruption (Agent Screwed Up)

**Detection:** Application reports missing/invalid data
**Recovery Time:** 5-10 minutes

```bash
# Determine date to restore to
fly ssh console -s neo4j
ls -lah /data/backups/

# Restore to pre-corruption backup
neo4j-admin database restore neo4j \
  --from-path=/data/backups/neo4j_20251019_020000.backup \
  --overwrite-existing=true

# Restart and verify
neo4j restart
```

### Scenario 2: Fly.io Machine Failure

**Detection:** Service unavailable
**Recovery Time:** 1-2 minutes (Fly auto-restarts), or 5-10 minutes (manual restore)

```bash
# Option A: Fly auto-restarts machine, volume reattaches
# (Data intact from last Fly snapshot or Fly replication)

# Option B: Manual restore from backup
fly volumes create neo4j_data_restore --snapshot-id <snapshot-id>
fly machines update <machine-id> --mount neo4j_data_restore:/data
```

### Scenario 3: Complete Fly.io Outage (Option 3 Only)

**Detection:** Fly.io infrastructure down
**Recovery Time:** 1-2 hours (download backup from S3, setup new instance)

```bash
# Download backup from S3
aws s3 cp s3://rag-memory-neo4j-backups/neo4j/latest.backup \
  ./neo4j_backup.backup

# Setup new Neo4j instance (any provider)
docker run -v /data:/data neo4j:5.25.0

# Restore
neo4j-admin database restore neo4j \
  --from-path=/data/neo4j_backup.backup \
  --overwrite-existing=true
```

---

## Monitoring & Maintenance

### Weekly Checks

```bash
# Verify recent backups
fly ssh console -s neo4j
ls -lah /data/backups/ | head -10

# Check backup logs
tail -20 /data/logs/backup_*.log

# Verify database health
cypher-shell -u neo4j -p <password> \
  "CALL dbms.diagnostics.report('HTML') YIELD content RETURN content LIMIT 1"
```

### Monthly Tasks

- Review S3 backup costs (if Option 3)
- Test restore procedure (dry run)
- Update documentation with changes

---

## References

- [Neo4j Official Backup Documentation](https://neo4j.com/docs/operations-manual/current/backup-restore/)
- [Fly.io Volume Snapshots](https://fly.io/docs/volumes/snapshots/)
- [AWS S3 Backup Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/BestPractices.html)
- [Financial-Times Neo4j Backup Docker Image](https://github.com/Financial-Times/coco-neo4j-backup)

