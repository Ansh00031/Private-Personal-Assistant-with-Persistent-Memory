# Deployment & Operations Guide

Production deployment guide for the **Private Personal Assistant with Persistent Memory** for the Nebius x NVIDIA Global AI Hackathon (Personal AI track).

---

## 1. Architecture & Persistence Overview

The application runs as a containerized FastAPI web service with SQLCipher-encrypted SQLite storage at rest. 

### Data Volumes & Encryption
- **Encrypted Database**: Stored at `/app/data/memory.db`.
- **KDF Salt File**: Stored at `/app/data/memory.db.salt` (generated on first boot using 16 bytes of cryptographically secure randomness).
- **Tool Sandbox**: Stored at `/app/data/sandbox` for file manipulation operations.
- **Persistent Volume Mount**: In production containers, `/app/data` must be mounted as an external persistent volume so that encryption keys, memories, notes, and calendar events persist across container restarts.

---

## 2. Configuration & Demo Mode

### Environment Variables (`.env`)
Create `.env` based on `.env.example`:

```bash
# 1. Nebius Token Factory API Key
NEBIUS_API_KEY=v1.C...

# 2. Database Passphrase (Used by scrypt KDF for SQLCipher AES-256)
MEMORY_PASSPHRASE=demo-judge-passphrase-2026

# 3. Encryption Mode ('on' strictly enforces SQLCipher)
MEMORY_ENCRYPTION=on

# 4. Storage paths
MEMORY_DB_PATH=data/memory.db
SANDBOX_ROOT=data/sandbox

# 5. Judge Credit & Abuse Protection
DAILY_COST_CAP_USD=5.00
RATE_LIMIT_RPM=30
```

### Seeding Demo Data for Judges
Before giving judges access, seed fictitious sample memories, episodes, notes, and events:
```bash
python seed_demo.py
```
> [!NOTE]
> `seed_demo.py` contains strictly fictitious sample data (daily routines, coding goals, sample events) and contains no real personal info.

---

## 3. Local & Containerized Run

### Local Docker Build & Execution
```bash
# Build production image
docker build -t personal-assistant:latest .

# Run container with persistent data volume mounted
docker run -d \
  --name personal-assistant \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  personal-assistant:latest
```

### Health Verification Endpoint
The container includes a built-in health probe:
```bash
curl -s http://localhost:8000/health
```
Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "encryption": "on",
  "models": {
    "nano": "nvidia/nemotron-mini-4b-instruct",
    "ultra": "nvidia/nemotron-3-8b-instruct",
    "embedding": "Qwen/Qwen3-Embedding-8B"
  },
  "daily_cost_usd": 0.0,
  "daily_cost_cap_usd": 5.0
}
```

---

## 4. Nebius Serverless AI Deployment

*Nebius Serverless AI Reference Docs:*
- Endpoints Documentation: [docs.nebius.com/serverless-ai/endpoints](https://docs.nebius.com/serverless-ai/endpoints/)
- Jobs Documentation: [docs.nebius.com/serverless-ai/jobs](https://docs.nebius.com/serverless-ai/jobs/)

### Step 4.1: Push Container Image to Registry
Tag and push your image to your container registry (e.g. Nebius Container Registry or Docker Hub):
```bash
docker tag personal-assistant:latest <REGISTRY_PATH>/personal-assistant:latest
docker push <REGISTRY_PATH>/personal-assistant:latest
```

### Step 4.2: Deploy App Endpoint (`nebius ai endpoint create`)
Deploy the persistent FastAPI web application:
```bash
nebius ai endpoint create \
  --name personal-assistant-app \
  --image <REGISTRY_PATH>/personal-assistant:latest \
  --platform cpu-d3 \
  --preset 2vcpu-8gb \
  --container-port 8000 \
  --public \
  --env NEBIUS_API_KEY="<YOUR_KEY>" \
  --env MEMORY_PASSPHRASE="demo-judge-passphrase-2026" \
  --env MEMORY_ENCRYPTION="on" \
  --env DAILY_COST_CAP_USD="5.00" \
  --env RATE_LIMIT_RPM="30"
```
*Nebius automatically provisions an HTTPS ingress URL for `--public` endpoints.*

### Step 4.3: Deploy Morning Brief Batch Job (`nebius ai job create`)
Run the scheduled morning brief aggregation as a batch job:
```bash
nebius ai job create \
  --name morning-brief-cron \
  --image <REGISTRY_PATH>/personal-assistant:latest \
  --platform cpu-d3 \
  --preset 2vcpu-8gb \
  --container-command "python" \
  --args "-c 'from jobs import morning_brief; import asyncio; asyncio.run(morning_brief())'" \
  --env NEBIUS_API_KEY="<YOUR_KEY>" \
  --env MEMORY_PASSPHRASE="demo-judge-passphrase-2026"
```

---

## 5. Operations & Judging Runbook

### 1. Devpost Judging Dates
- **Submission Deadline**: October 30, 2026, 10:00 AM PDT (10:30 PM IST).
- **Judging Period**: December 1, 2026 – December 15, 2026.
- **Winners Announced**: ~January 11, 2027.
- Always check the Devpost hackathon updates tab for any organizer timeline announcements.

### 2. Credit Balance Monitoring
- **Nebius Console**: Monitor credit balances directly at `https://tokenfactory.nebius.com/` under Billing / Usage.
- **In-App Spending Guard**: The backend router tracks daily API costs and auto-downgrades reasoning queries from Ultra to Nano once `DAILY_COST_CAP_USD` ($5.00 default) is exceeded.
- Check live spend anytime via `GET /health` (`daily_cost_usd` field).

### 3. Restarting the Demo
- **Local / Docker**:
  ```bash
  docker restart personal-assistant
  ```
- **Nebius Serverless**:
  Use `nebius ai endpoint get --name personal-assistant-app` to inspect status, or update/restart using the CLI or Nebius Web Console.

### 4. Public HTTPS Verification
To verify the demo is reachable over HTTPS from an external machine / cellular network without local LAN biases:
```bash
curl -I https://<YOUR-NEBIUS-ENDPOINT-URL>/health
```
Ensure HTTP `200 OK` is returned with SSL handshake completing cleanly and `/ui/index.html` loading in a browser incognito window.
