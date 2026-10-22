<p align="center">
  <img src="https://img.shields.io/badge/Nebius_x_NVIDIA-Global_AI_Hackathon-76b900?style=for-the-badge&logo=nvidia&logoColor=white" alt="Hackathon Badge"/>
  <br/>
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/SQLCipher-AES--256-red?style=flat-square&logo=sqlite&logoColor=white" alt="SQLCipher"/>
  <img src="https://img.shields.io/badge/Nemotron-Nano_30B_%7C_Ultra_550B-76b900?style=flat-square&logo=nvidia&logoColor=white" alt="Models"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License"/>
</p>

<h1 align="center">🧠 Private Personal Assistant with Persistent Memory</h1>

<p align="center">
  <strong>A personal AI assistant with persistent local memory, hybrid recall, voice controls, and a FastAPI web interface.</strong>
</p>

<p align="center">
  Built for the <strong>Nebius × NVIDIA Global AI Hackathon</strong> (Personal AI Track)
</p>

---

## 🎯 What Makes This Different?

Most AI assistants forget everything after each session. This one **doesn't**.

Every conversation is automatically analyzed, key facts are extracted with confidence scores, and everything is stored in an **AES-256 encrypted local database** — creating a growing personal knowledge graph that makes the assistant smarter over time.

> **Privacy note:** Memory is stored in the configured local database. Chat requests and any recalled context sent to the model are processed by the configured Nebius API; review its terms before using sensitive information. Browser speech recognition may also use the browser vendor's service.

---

## ✨ Key Features

### 🧠 Persistent Memory System
- **Hybrid 3-way recall** — combines semantic vector search (sqlite-vec), full-text BM25 (FTS5), and temporal filtering
- **Automatic fact extraction** — LLM analyzes every conversation and extracts structured facts with confidence scores
- **Multi-turn context** — follow up on previous messages without repeating yourself; the assistant remembers your entire session
- **Provenance tracking** — every memory tagged as `user_said` or `tool_output` with full audit log

### 🔐 Privacy-First Architecture
- **SQLCipher encryption** — AES-256 with 256K KDF iterations on all stored data
- **Hard delete** — cryptographically erases data from row, vector index, and FTS simultaneously
- **Local memory storage** — the database path is configurable; model requests use the Nebius API
- **Verified deletion** — post-delete verification ensures data is gone from all indices

### 🎙️ Advanced Voice Interface
- **Continuous listening** with **3.5-second silence auto-detection** — speak naturally without premature cutoffs
- **Real-time speech modulation** — adjust speed (0.5x–2.0x) and pitch (0.5–1.5) *while the assistant is speaking*
- **Reactive audio waveform visualizer** — live canvas animation (green for listening, purple for speaking)
- **Synthesized earcon chimes** — subtle audio feedback on mic start/stop
- **Hindi, Hinglish & English** — full multilingual voice I/O with automatic language detection

### 📊 One-Click Data Exports
- **📋 Copy Table** → paste directly into Excel, Google Sheets, or Notion (TSV format)
- **📥 Download CSV** → UTF-8 BOM encoded for full Hindi/Devanagari support in Excel
- **📄 Download PDF** → professional A4 document with branded header, styled table, and footer

### 🤖 Dual-Model Intelligence
| Model | Use Case | Specs |
|-------|----------|-------|
| **Nano** (fast) | Daily chat, quick answers | NVIDIA Nemotron-3 Nano 30B |
| **Ultra** (smart) | Complex reasoning, analysis | NVIDIA Nemotron-3 Ultra 550B |

Switch between models per-message with a single click.

### ☀️ Executive Morning Briefing
- Auto-scheduled daily at 8 AM (configurable)
- Also available on-demand via one-click button
- Synthesizes recent facts and conversations into a concise personal summary
- Reads aloud via TTS when voice reply is enabled

### 🛠️ Extensible Skill Engine
| Skill | Triggers | What It Does |
|-------|----------|-------------|
| **Recall** | "remember", "what did I say" | Searches memory with scored results |
| **Notes** | "note", "save this", "write down" | Creates and manages personal notes |
| **Calendar** | "schedule", "meeting", "appointment" | Manages events with confirmation gates |
| **Files** | "file", "read", "write" | Sandboxed file I/O with path traversal protection |

Destructive actions require explicit user confirmation before executing.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Web Browser                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Chat UI  │  │ Voice.js │  │ PDF/CSV  │  │ Briefing│ │
│  │ panel.js │  │ STT/TTS  │  │ Export   │  │ Button  │ │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └────┬────┘ │
│       │              │                           │      │
└───────┼──────────────┼───────────────────────────┼──────┘
        │              │                           │
        ▼              ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                        │
│                                                          │
│  /chat ──► Skill Engine ──► LLM Router ──► Nebius API   │
│              │                   │                       │
│              ▼                   ▼                       │
│         tools/*            Nemotron Nano 30B             │
│         (notes,            Nemotron Ultra 550B           │
│          calendar,         Qwen3 Embedding 8B            │
│          files)                                          │
│              │                   │                       │
│              ▼                   ▼                       │
│  ┌──────────────────────────────────────────┐            │
│  │        Memory Layer (memory/)            │            │
│  │                                          │            │
│  │  ┌──────────┐ ┌────────┐ ┌───────────┐  │            │
│  │  │ Semantic  │ │Keyword │ │ Temporal  │  │            │
│  │  │ (vec0)   │ │(FTS5)  │ │ (date)    │  │            │
│  │  └──────────┘ └────────┘ └───────────┘  │            │
│  │         ▼          ▼          ▼          │            │
│  │      Hybrid Recall (deduplicated)        │            │
│  └──────────────────────────────────────────┘            │
│                       │                                  │
│                       ▼                                  │
│  ┌──────────────────────────────────────────┐            │
│  │  SQLCipher Encrypted Database (AES-256)  │            │
│  │  memories │ episodes │ provenance_log    │            │
│  └──────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

### Project Structure

```
project/
├── app.py                  # FastAPI routes & chat pipeline
├── llm.py                  # Nebius API client & model router
├── skills.py               # Skill engine with keyword routing
├── jobs.py                 # APScheduler morning brief & cron jobs
├── config/
│   └── models.yaml         # Model IDs & API config (single source of truth)
├── memory/
│   ├── db.py               # SQLCipher schema, encryption, hard delete
│   ├── extract.py          # LLM-powered fact/episode extraction
│   └── recall.py           # Hybrid recall (semantic + keyword + temporal)
├── tools/
│   ├── notes.py            # Personal notes CRUD
│   ├── calendar.py         # Calendar event management
│   ├── files.py            # Sandboxed file operations
│   └── sandbox.py          # Abstract tool adapter (extensible)
├── ui/
│   ├── index.html          # Single-page application shell
│   ├── panel.js            # Chat logic, PDF/CSV export, memory panel
│   ├── voice.js            # Full STT/TTS with visualizer (800 lines)
│   ├── style.css           # Dark theme UI (NVIDIA green accent)
│   ├── marked.min.js       # Markdown renderer for tables
│   └── html2pdf.bundle.min.js  # Client-side PDF generation
├── tests/                  # 33 tests across 6 test files
│   ├── conftest.py         # Pytest config with temp DB & env setup
│   ├── test_chat_smoke.py  # Chat endpoint smoke tests
│   ├── test_db.py          # Database CRUD, FTS sync, hard delete
│   ├── test_llm.py         # Model router & API key validation
│   ├── test_recall.py      # Hybrid recall strategy tests
│   ├── test_sandbox.py     # Tool adapter tests
│   └── test_skills.py      # Skill routing & confirmation tests
├── start.bat               # Windows one-click launcher
├── start.ps1               # PowerShell startup with env restore
├── Dockerfile              # Docker deployment
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── LICENSE                 # MIT License
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Nebius API key** — [Get one free here](https://studio.nebius.com/)
- **Google Chrome** or **Microsoft Edge** (for voice features)

### 1. Clone & Install

```bash
git clone https://github.com/Ansh00031/Private-Personal-Assistant-with-Persistent-Memory.git
cd Private-Personal-Assistant-with-Persistent-Memory

# Create virtual environment
python -m venv venv

# Activate
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example env file
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Required | Description |
|----------|----------|-------------|
| `NEBIUS_API_KEY` | ✅ | Your Nebius Token Factory API key |
| `MEMORY_ENCRYPTION_KEY` | ✅ | 64 hex chars — generate with `openssl rand -hex 32` |
| `MEMORY_DB_PATH` | ❌ | Database path (default: `data/memory.db`) |
| `SANDBOX_ROOT` | ❌ | File sandbox root (default: `data/sandbox`) |

### 3. Run

**Option A — One-click (Windows):**
```
Double-click start.bat
```

**Option B — Manual:**
```bash
# Linux/macOS
export NEBIUS_API_KEY="your-api-key"
export MEMORY_ENCRYPTION_KEY=$(openssl rand -hex 32)
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Windows PowerShell
$env:NEBIUS_API_KEY="your-api-key"
$env:MEMORY_ENCRYPTION_KEY="your-64-hex-char-key"
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

**Option C — Docker:**
```bash
docker build -t private-assistant .
docker run -p 8000:8000 \
  -e NEBIUS_API_KEY="your-key" \
  -e MEMORY_ENCRYPTION_KEY="your-key" \
  -v $(pwd)/data:/app/data \
  private-assistant
```

### 4. Open

Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser. 🎉

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the Web UI |
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Main chat with memory retrieval & skill routing |
| `POST` | `/morning-brief` | Generate on-demand morning briefing |
| `DELETE` | `/memory/{id}` | Hard delete a memory (row + vector + FTS) |
| `GET` | `/memories?limit=50&offset=0` | List memories with pagination |
| `GET` | `/stats` | System stats (memory count, cost estimate) |

<details>
<summary><strong>📨 Chat Request / Response Examples</strong></summary>

**Request:**
```json
{
  "message": "Add biology class at 2pm to my timetable",
  "model": "nano",
  "history": [
    { "role": "user", "content": "Make my college timetable from 9am to 4pm" },
    { "role": "assistant", "content": "| Time | Subject |\n|---|---|\n| 09:00 | Mathematics |" }
  ]
}
```

**Response:**
```json
{
  "response": "Here is your updated timetable:\n\n| Time | Subject |\n|---|---|\n| 09:00 - 10:00 | Mathematics |\n| 14:00 - 15:00 | Biology |",
  "model_used": "nano",
  "memories_retrieved": [
    { "id": 42, "content": "User's college schedule", "score": 0.89 }
  ],
  "skill_used": null,
  "requires_confirmation": false
}
```
</details>

---

## 🎙️ Voice Features

The assistant includes a full voice pipeline built entirely with browser Web Speech APIs:

| Feature | Details |
|---------|---------|
| **Speech-to-Text** | Continuous listening with 3.5s silence auto-send |
| **Text-to-Speech** | Adjustable speed (0.5x–2.0x) and pitch (0.5–1.5) in real-time |
| **Languages** | English (US), English/Hinglish (India), Hindi (हिंदी) |
| **Visualizer** | Reactive canvas waveform — green when listening, purple when speaking |
| **Keyboard Shortcuts** | `Ctrl+Space` toggle mic, `Escape` cancel |
| **Auto-detect** | Devanagari script → Hindi voice, Roman → selected voice |

### 🔒 Voice Privacy

- **No audio is ever stored** in the local database
- Browser STT may transmit audio to the browser vendor (Google/Microsoft/Apple) for transcription
- All text memories remain **encrypted at rest** with SQLCipher
- For air-gapped privacy, use text chat only

---

## 🧪 Testing

```bash
# Run all 33 tests
pytest tests/ -v

# Run specific test file
pytest tests/test_db.py -v
```

Test coverage includes:
- ✅ Chat endpoint smoke tests (nano/ultra/multi-turn/morning-brief)
- ✅ Database CRUD, FTS5 trigger sync, hard delete verification
- ✅ Model router initialization & API key validation
- ✅ Hybrid recall strategies (semantic/keyword/temporal/dedup)
- ✅ Skill routing & confirmation gate flow
- ✅ Sandbox tool adapter patterns

---

## 🛡️ Security

| Layer | Protection |
|-------|-----------|
| **Data at Rest** | SQLCipher encryption is available when the optional `sqlcipher3` package and system library are installed; verify your runtime before storing sensitive data |
| **Hard Delete** | Removes data from row, vector index, and FTS simultaneously |
| **Provenance** | Full audit log of all memory operations |
| **File I/O** | Sandboxed with path traversal protection |
| **Tool Execution** | Destructive actions require explicit user confirmation |
| **External services** | Chat prompts and recalled context are sent to the configured Nebius API; browser speech recognition may contact its provider |

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **LLM Provider** | Nebius AI (OpenAI-compatible API) |
| **Models** | NVIDIA Nemotron-3 Nano 30B, Ultra 550B |
| **Embeddings** | Qwen3 Embedding 8B (1024 dims) |
| **Database** | SQLite + FTS5; optional SQLCipher support when installed |
| **Scheduler** | APScheduler (BackgroundScheduler) |
| **Frontend** | Vanilla JS, Web Speech API, Web Audio API |
| **PDF Export** | html2pdf.js (client-side) |
| **Markdown** | marked.js |
| **Containerization** | Docker (Python 3.11-slim) |

---

## 📜 License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built with ❤️ for the Nebius × NVIDIA Global AI Hackathon</strong>
  <br/>
  <em>Because your AI assistant should remember you — without anyone else knowing.</em>
</p>
