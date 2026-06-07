<p align="center">
  <img src="https://img.shields.io/badge/AIOS-AI%20Native%20Operating%20System-blueviolet?style=for-the-badge&logo=linux&logoColor=white" alt="AIOS Badge"/>
</p>

<h1 align="center">AIOS — AI-Native Operating System Prototype</h1>

<p align="center">
  <em>A privileged user-space AI middleware daemon for Linux that monitors system telemetry, performs hybrid RAG retrieval, generates structured optimisation intents via LLM, and gates all execution through a Deterministic Control Plane with human-in-the-loop approval.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-brightgreen?style=flat-square" alt="Version" />
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/node.js-20_LTS-339933?style=flat-square&logo=node.js&logoColor=white" alt="Node.js" />
  <img src="https://img.shields.io/badge/react-18.3-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/tests-56%20passed-success?style=flat-square" alt="Tests" />
  <img src="https://img.shields.io/badge/OS-Ubuntu%2022.04-E95420?style=flat-square&logo=ubuntu&logoColor=white" alt="Ubuntu" />
</p>

<p align="center">
  <a href="https://github.com/anan5093"><img src="https://img.shields.io/badge/GitHub-anan5093-181717?style=flat-square&logo=github" alt="GitHub" /></a>
  <a href="https://www.linkedin.com/in/anand-raj-006a41217/"><img src="https://img.shields.io/badge/LinkedIn-Anand%20Raj-0A66C2?style=flat-square&logo=linkedin" alt="LinkedIn" /></a>
  <a href="https://medium.com/@anand.ar1806"><img src="https://img.shields.io/badge/Medium-@anand.ar1806-000000?style=flat-square&logo=medium" alt="Medium" /></a>
  <a href="https://zenodo.org/me/uploads?q=&f=shared_with_me%3Afalse&l=list&p=1&s=10&sort=newest"><img src="https://img.shields.io/badge/Zenodo-Research%20Archive-1682D4?style=flat-square&logo=zenodo" alt="Zenodo" /></a>
</p>

---

## 📸 Live Dashboard Screenshots

<table>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/01_admin_renice_query.png" alt="Admin Dashboard — suggest_renice intent validated with RAG context" />
      <p align="center"><strong>Admin View</strong> — AI suggests <code>renice</code> for nginx (86.4% confidence)</p>
    </td>
    <td width="50%">
      <img src="docs/screenshots/02_viewer_rbac_blocked.png" alt="Viewer role blocked from submitting queries by RBAC" />
      <p align="center"><strong>Viewer RBAC</strong> — Read-only access, query submission blocked</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/03_operator_cgroup_limit.png" alt="Operator Dashboard — suggest_cgroup_limit for postgres at 95% confidence" />
      <p align="center"><strong>Operator View</strong> — AI suggests cgroup limit for postgres (95% confidence)</p>
    </td>
    <td width="50%">
      <img src="docs/screenshots/04_operator_log_rotate.png" alt="Operator Dashboard — suggest_log_rotate for syslog at 90% confidence" />
      <p align="center"><strong>Operator View</strong> — AI suggests log rotation for syslog (90% confidence)</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/06_login_portal_metrics.png" alt="Sleek login portal with metrics and demo operator quick-fill" />
      <p align="center"><strong>Sleek Login Portal</strong> — Dual-column layout with live metrics and profile quick-fill</p>
    </td>
    <td width="50%">
      <img src="docs/screenshots/07_register_pam_verification.png" alt="Operator registration with admin PAM verification check" />
      <p align="center"><strong>Admin PAM Verification</strong> — Register locked behind administrator sudo checks</p>
    </td>
  </tr>
</table>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [AI Query Pipeline](#-ai-query-pipeline)
- [Security & Safety Model](#-security--safety-model)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Configuration](#-configuration)
- [Running the System](#-running-the-system)
- [Default Credentials](#-default-credentials)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Performance Optimisations](#-performance-optimisations)
- [Troubleshooting](#-troubleshooting)
- [Blog & Research](#-blog--research)
- [Author](#-author)
- [License](#-license)

---

## 🧠 Overview

AIOS is a research prototype that demonstrates **AI as a privileged user-space middleware layer** on Linux. Rather than modifying the kernel, it operates entirely in user space — monitoring system telemetry via log files, searching historical context through a hybrid FAISS + MongoDB Atlas retrieval system, forwarding structured prompts to a cloud-hosted LLM (Llama 3 on Kaggle GPU via Ngrok), and gating all generated actions through a fail-safe Deterministic Control Plane that requires explicit human approval before simulated execution.

> **Core Philosophy:** _AI advises, humans decide._ No action is ever executed autonomously.

---

## ✨ Key Features

| Category | Feature | Description |
|----------|---------|-------------|
| 🤖 **AI Intelligence** | Hybrid RAG Retrieval | Parallel FAISS (local) + MongoDB Atlas (cloud) vector search with weighted score fusion |
| 🤖 **AI Intelligence** | Structured Intent Generation | LLM outputs constrained to 4 permitted actions in strict JSON schema |
| 🤖 **AI Intelligence** | Evidence-Based Reasoning | Every recommendation cites specific log entries and timestamps |
| 🛡️ **Safety** | Deterministic Control Plane | 4-stage fail-fast validation: null check → allowlist → confidence gate → approval |
| 🛡️ **Safety** | Tamper-Evident Audit Log | SHA-256 hashed, append-only SQLite ledger for every intent |
| 🛡️ **Safety** | Human-in-the-Loop | No action simulated without explicit operator approval |
| 🔐 **Security** | 3-Stage Data Sanitisation | 10 regex patterns + entity anonymisation + schema filtering before any data egress |
| 🔐 **Security** | JWT + RBAC | Role hierarchy (`admin > operator > viewer`) with token-based authentication |
| 📊 **Observability** | Real-Time Dashboard | React 18 + Vite with live WebSocket streaming of metrics and AI reasoning traces |
| 📊 **Observability** | Service Health Monitoring | Continuous health checks for FAISS, Atlas, Ollama, and Daemon subsystems |
| ☁️ **Cloud Hybrid** | Zero-Cost GPU Inference | Kaggle T4/P100 GPU + Ngrok tunnel for free LLM inference at scale |
| ⚡ **Performance** | Eager Model Preloading | 0-second cold start via concurrent startup initialisation |
| ⚡ **Performance** | Optimised RAG Context | 60%+ latency reduction through intelligent context trimming |

---

## 🏗️ System Architecture

### High-Level Topology

```
┌───────────────────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE (i5-1135G7, 8 GB RAM)               │
│                                                                       │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐    │
│   │   React 18   │◄──►│  Express 5   │◄──►│   Python Daemon      │    │
│   │  Dashboard   │ WS │  REST API    │IPC │   (asyncio + aiohttp)│    │
│   │  :3000       │    │  :5000       │    │   :8765              │    │
│   └─────────────┘    └──────────────┘    └──────┬───────────────┘    │
│                                                  │                    │
│                              ┌───────────────────┼────────────────┐  │
│                              │                   │                │  │
│                    ┌─────────▼──────┐  ┌─────────▼──────────┐    │  │
│                    │  FAISS Index   │  │  Embedding Model   │    │  │
│                    │  (601 vectors) │  │  (all-MiniLM-L6-v2)│    │  │
│                    └────────────────┘  └────────────────────┘    │  │
│                              │                                   │  │
│                              │         ┌─────────────────────┐   │  │
│                              │         │  SQLite Audit DB    │   │  │
│                              │         │  (SHA-256 hashed)   │   │  │
│                              │         └─────────────────────┘   │  │
│                              │                                   │  │
├──────────────────────────────┼───────────────────────────────────┘  │
│                              │  Ngrok Encrypted Tunnel               │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                       │
│   ┌──────────────────────────▼────────────────────────────────┐     │
│   │           CLOUD COMPUTE (Kaggle GPU Runtime)              │     │
│   │                                                            │     │
│   │   ┌──────────────┐    ┌──────────────────────┐            │     │
│   │   │  Ollama LLM  │    │  Llama 3 (8B params) │            │     │
│   │   │  Server       │◄──►│  Tesla P100 16GB     │            │     │
│   │   └──────────────┘    └──────────────────────┘            │     │
│   └───────────────────────────────────────────────────────────┘     │
│                                                                       │
│   ┌───────────────────────────────────────────────────────────┐     │
│   │           CLOUD MEMORY (MongoDB Atlas, ap-south-1)        │     │
│   │           601 documents · Vector Search Index             │     │
│   └───────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```mermaid
sequenceDiagram
    participant U as 👤 Operator
    participant D as 🖥️ Dashboard
    participant A as ⚙️ Express API
    participant P as 🐍 Python Daemon
    participant F as 📦 FAISS
    participant M as ☁️ MongoDB Atlas
    participant L as 🤖 Ollama LLM
    participant C as 🛡️ Control Plane

    U->>D: Submit natural language query
    D->>A: POST /api/query (JWT auth)
    A->>P: Forward via IPC (:8765)
    
    par Parallel Retrieval
        P->>F: Vector search (local)
        P->>M: Vector search (cloud)
    end
    
    F-->>P: Top-k chunks (FAISS)
    M-->>P: Top-k chunks (Atlas)
    P->>P: Merge, deduplicate, re-rank
    P->>P: Build structured prompt
    P->>L: Stream generate (Ngrok tunnel)
    L-->>P: JSON intent (streamed tokens)
    P->>P: Parse intent (2-attempt extraction)
    P->>C: Validate intent
    
    alt VALIDATED (confidence ≥ 0.75)
        C-->>P: ✅ VALIDATED
        P-->>D: Stream result via WebSocket
        D-->>U: Show intent + "Approve" button
        U->>D: Click "Approve"
        D->>A: PUT /api/intents/:id/approve
        A->>P: Forward approval
        P->>C: Log SIMULATED_EXECUTED
    else REJECTED
        C-->>P: ❌ REJECTED (reason logged)
        P-->>D: Stream rejection via WebSocket
    else PENDING_REVIEW
        C-->>P: ⏳ PENDING_REVIEW
        P-->>D: Stream for manual review
    end
```

---

## 🔄 AI Query Pipeline

The core intelligence pipeline processes a query through six stages:

```
┌──────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐
│ 1. EMBED │──►│ 2. SEARCH │──►│ 3. BUILD  │──►│ 4. INFER  │──►│ 5. PARSE │──►│ 6. GATE  │
│          │   │           │   │   PROMPT   │   │           │   │          │   │          │
│ Query →  │   │ FAISS +   │   │ System    │   │ Ollama    │   │ Regex +  │   │ Allowlist│
│ Vector   │   │ Atlas     │   │ role +    │   │ Llama 3   │   │ Pydantic │   │ + Audit  │
│ (384-dim)│   │ parallel  │   │ RAG ctx + │   │ streaming │   │ v2 valid │   │ + SHA256 │
│          │   │ hybrid    │   │ query     │   │           │   │          │   │          │
└──────────┘   └───────────┘   └───────────┘   └───────────┘   └──────────┘   └──────────┘
```

### Permitted Actions

The LLM is constrained to output exactly one of these four action types:

| Action | Target | Example Value | Use Case |
|--------|--------|--------------|----------|
| `suggest_renice` | Process name + PID | `"10"` | Reduce priority of CPU-hogging process |
| `suggest_swap_adjust` | `vm.swappiness` | `"40"` | Tune virtual memory paging behaviour |
| `suggest_log_rotate` | Log file path | `"/var/log/syslog"` | Rotate and compress bloated log files |
| `suggest_cgroup_limit` | Process/group name | `"2048M"` | Cap memory/CPU for runaway process |

---

## 🛡️ Security & Safety Model

### Defence-in-Depth Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: Data Sanitisation (before any egress)             │
│  ├── 10 regex patterns (AWS keys, JWTs, IPs, PEM keys...)  │
│  ├── Entity anonymisation (hostname → AIOS_HOST)            │
│  └── Schema-based key filtering for structured payloads     │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: Authentication & Authorisation                    │
│  ├── JWT Bearer tokens (24h expiry, bcrypt-12 passwords)    │
│  └── RBAC: admin(3) > operator(2) > viewer(1)              │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3: Deterministic Control Plane                       │
│  ├── Null check → REJECTED (PARSE_ERROR)                    │
│  ├── Allowlist check → REJECTED (DISALLOWED_ACTION_TYPE)    │
│  ├── Confidence gate (< 0.75) → PENDING_REVIEW             │
│  └── All pass → VALIDATED (awaits human approval)           │
├─────────────────────────────────────────────────────────────┤
│  LAYER 4: Tamper-Evident Audit Log                          │
│  ├── Append-only SQLite with SHA-256 record hashing         │
│  └── Every intent logged regardless of validation outcome   │
├─────────────────────────────────────────────────────────────┤
│  LAYER 5: User-Space Isolation                              │
│  ├── No kernel writes, no raw syscalls, no sysctl           │
│  └── All actions are simulated, never executed on real OS   │
└─────────────────────────────────────────────────────────────┘
```

### Role-Based Access Control

| Role | Level | Submit Queries | Approve Intents | View Audit Log | View Metrics |
|------|-------|---------------|-----------------|----------------|-------------|
| `viewer` | 1 | ❌ | ❌ | ✅ | ✅ |
| `operator` | 2 | ✅ | ✅ | ✅ | ✅ |
| `admin` | 3 | ✅ | ✅ | ✅ | ✅ |

---

## 🛠️ Technology Stack

### Backend — Python Daemon

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Runtime | Python | 3.11+ | Async middleware orchestrator |
| Async Framework | asyncio + aiohttp | — | Non-blocking HTTP/WS server |
| Embedding | sentence-transformers | latest | all-MiniLM-L6-v2 text→vector |
| Local Vector DB | faiss-cpu | latest | HNSW approximate nearest neighbour |
| Cloud Vector DB | motor (async MongoDB) | latest | Atlas vector search driver |
| LLM Client | httpx | ≥0.27.0 | Streaming HTTP to Ollama |
| Intent Validation | Pydantic v2 | ≥2.0 | Structured AI output parsing |
| File Watching | watchdog | ≥4.0 | Real-time log file monitoring |
| System Metrics | psutil | ≥5.9 | CPU, memory, disk telemetry |
| Audit Database | sqlite3 (stdlib) | — | Tamper-evident intent ledger |

### Backend — Express API

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Express | 5.0.1 | REST + middleware pipeline |
| WebSocket | ws | 8.17.1 | Real-time event streaming |
| Auth | jsonwebtoken + bcryptjs | 9.x / 2.x | JWT issuance + password hashing |
| HTTP Client | node-fetch | 2.7.0 | Daemon IPC proxy |
| Logging | morgan | 1.10.0 | HTTP request logging |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | React | 18.3.1 | Component-based UI |
| Build Tool | Vite | 8.x | HMR + production bundling |
| Language | TypeScript | 5.4.5 | Type-safe components |
| HTTP Client | axios | 1.6.8 | API communication |
| Routing | react-router-dom | 6.23.1 | SPA navigation |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM Runtime | Ollama + Llama 3 | 8B-parameter language model |
| GPU Compute | Kaggle (Tesla P100 / T4) | Free cloud GPU inference |
| Tunnel | Ngrok (static domain) | Encrypted local↔cloud bridge |
| Cloud Database | MongoDB Atlas (M0, ap-south-1) | Vector search + long-term memory |

---

## 📁 Project Structure

```
AIOS-Prototype_Rag/
├── daemon/                          # Python AI middleware daemon
│   ├── main.py                      # Entry point — async HTTP server (:8765)
│   ├── inference_client.py          # Streaming Ollama client (httpx)
│   ├── intent_parser.py             # 2-attempt JSON extraction + Pydantic validation
│   ├── control_plane.py             # Deterministic safety gate + SQLite audit
│   ├── prompt_builder.py            # System role + RAG context → structured prompt
│   ├── retriever.py                 # Hybrid FAISS + Atlas parallel retriever
│   ├── embedder.py                  # SentenceTransformer embedding service
│   ├── faiss_store.py               # FAISS index management + persistence
│   ├── atlas_store.py               # MongoDB Atlas async vector search
│   ├── sanitiser.py                 # 3-stage telemetry data sanitisation
│   ├── ws_broadcaster.py            # WebSocket event relay to Express API
│   └── requirements.txt             # Python dependencies
│
├── api/                             # Node.js Express management API
│   ├── server.js                    # Express 5 + WebSocket + daemon polling
│   ├── middleware/
│   │   ├── auth.js                  # JWT Bearer token verification
│   │   └── rbac.js                  # Role-based access control factory
│   └── routes/
│       ├── auth.js                  # POST /api/auth/login (3 seed users)
│       ├── query.js                 # POST /api/query (operator+ only)
│       ├── intents.js               # GET /api/intents, PUT .../approve
│       ├── metrics.js               # GET /api/metrics + /history
│       └── health.js                # GET /api/health (subsystem checks)
│
├── frontend/                        # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── App.tsx                  # Main application shell
│   │   ├── main.tsx                 # React DOM entry point
│   │   ├── index.css                # Global styles (dark theme)
│   │   ├── components/
│   │   │   ├── QueryForm.tsx        # Natural language query input
│   │   │   ├── ReasoningTrace.tsx   # AI reasoning + parsed intent display
│   │   │   ├── RAGViewer.tsx        # Retrieved context chunks viewer
│   │   │   ├── AuditLog.tsx         # Paginated control plane audit log
│   │   │   ├── MetricsPanel.tsx     # System metrics cards (CPU/RAM/disk)
│   │   │   └── ServiceHealthBar.tsx # Subsystem status indicators
│   │   ├── context/                 # React context providers
│   │   └── hooks/                   # Custom React hooks
│   ├── index.html                   # HTML entry point
│   ├── vite.config.ts               # Vite configuration
│   └── tsconfig.json                # TypeScript configuration
│
├── scripts/                         # Utility scripts
│   ├── generate_mock_logs.py        # Synthetic syslog, kern.log, bash_history
│   ├── ingest_mock_logs.py          # Chunk + embed + store to FAISS & Atlas
│   ├── inject_panic.py              # Simulate kernel panic scenarios
│   └── clean_pycache.py             # Cleanup __pycache__ directories
│
├── kaggle_kernel/                   # Kaggle GPU deployment script
│   ├── task.py                      # Ollama + Ngrok auto-setup on Kaggle
│   └── kernel-metadata.json         # Kaggle kernel configuration
│
├── tests/                           # Automated test suite (56 tests)
│   ├── conftest.py                  # Shared fixtures + path bootstrap
│   ├── test_control_plane.py        # Safety gate validation tests
│   ├── test_embedder.py             # Embedding service tests
│   ├── test_faiss_store.py          # FAISS index CRUD tests
│   ├── test_atlas_store.py          # MongoDB Atlas mock tests
│   ├── test_cached_mongodb.py       # Connection caching tests
│   ├── test_inference_client.py     # Ollama streaming client tests
│   ├── test_prompt_builder.py       # Prompt construction tests
│   ├── test_retriever.py            # Hybrid retriever merge/dedup tests
│   └── test_sanitiser.py            # Data sanitisation coverage
│
├── mock_logs/                       # Generated synthetic log files
│   ├── syslog                       # ~600 lines: memory pressure, services
│   ├── kern.log                     # ~500 lines: OOM killer, CPU lockup
│   └── bash_history                 # ~400 lines: operator command history
│
├── data/                            # Runtime data (gitignored)
│   ├── faiss.index                  # Persisted FAISS vector index
│   ├── faiss_metadata.json          # Chunk metadata for FAISS vectors
│   ├── aios_audit.db                # SQLite audit log database
│   └── simulation_state.json        # Last approved intent state
│
├── docs/                            # Documentation
│   ├── Design.md                    # Detailed design specification
│   ├── Requirements.md              # Functional & non-functional requirements
│   ├── Task.md                      # Development task tracking
│   ├── blog_self_healing_computer.md # Published blog post
│   ├── walkthrough.md               # Change walkthrough
│   └── screenshots/                 # Dashboard proof-of-concept images
│
├── .env.example                     # Configuration template
├── .gitignore                       # Git exclusion rules
└── README.md                        # ← You are here
```

---

## 📦 Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.11+ | Daemon runtime |
| **Node.js** | 20 LTS+ | Express API + React frontend |
| **npm** | 10+ | Package management |
| **Kaggle Account** | Free tier | GPU runtime for LLM inference |
| **MongoDB Atlas Account** | Free M0 | Cloud vector search cluster |
| **Ngrok Account** | Free tier | Tunnel authentication + static domain |

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/anan5093/AIOS-Prototype_Rag.git
cd AIOS-Prototype_Rag
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials (see Configuration section below)
```

### 3. Set Up Python Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r daemon/requirements.txt
```

### 4. Install Node.js Dependencies

```bash
# Express API
cd api && npm install && cd ..

# React Frontend
cd frontend && npm install && cd ..
```

### 5. Generate Synthetic Logs

```bash
python scripts/generate_mock_logs.py
```

### 6. Ingest Logs into Vector Databases

```bash
python scripts/ingest_mock_logs.py
```
> This creates the local FAISS index (`data/faiss.index`) and uploads chunks to MongoDB Atlas.

### 7. Deploy LLM on Kaggle GPU

```bash
# Push the Kaggle kernel (requires kaggle CLI configured)
kaggle kernels push -p kaggle_kernel
```
> Copy the Ngrok tunnel URL from the kernel output into your `.env` file.

---

## ⚙️ Configuration

Edit your `.env` file with the following variables:

```env
# ── Inference ──────────────────────────────────────────
OLLAMA_ENDPOINT=https://YOUR-STATIC-DOMAIN.ngrok-free.dev
MODEL_NAME=llama3
FALLBACK_MODEL=llama3
LOCAL_OLLAMA=http://localhost:11434

# ── ngrok Tunnel Auth ──────────────────────────────────
NGROK_AUTH_USER=aios
NGROK_AUTH_PASS=your_strong_password

# ── MongoDB Atlas ──────────────────────────────────────
ATLAS_URI=mongodb+srv://USERNAME:PASSWORD@cluster0.xxxxx.mongodb.net/
ATLAS_DB=aios_memory
ATLAS_COLLECTION=system_logs

# ── Embedding ──────────────────────────────────────────
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ── Express API ────────────────────────────────────────
JWT_SECRET=your_jwt_secret_minimum_32_characters
PORT=5000

# ── Logging ────────────────────────────────────────────
LOG_LEVEL=INFO
```

---

## ▶️ Running the System

Start all three services in separate terminals:

### Terminal 1 — Python AI Daemon

```bash
source .venv/bin/activate
python -m daemon.main
```

Expected output:
```
[INFO] AIOS Daemon starting up…
[INFO] Overriding default LOCAL_OLLAMA with OLLAMA_ENDPOINT: https://...
[INFO] Loaded FAISS index with 601 vectors from disk
[INFO] Model 'all-MiniLM-L6-v2' loaded eagerly (0-second cold start)
[INFO] Serving on 0.0.0.0:8765
```

### Terminal 2 — Express API Server

```bash
cd api && npm start
```

Expected output:
```
[AIOS API] Listening on port 5000
[WS] Client connected. Total: 1
```

### Terminal 3 — React Dashboard

```bash
cd frontend && npm run dev
```

Expected output:
```
VITE v8.x ready in 500ms
➜ Local: http://localhost:3000/
```

### Open the Dashboard

Navigate to **http://localhost:3000** in your browser.

---

## 🔑 Default Credentials

| Email | Password | Role | Query Access | Approve Access |
|-------|----------|------|:------------:|:--------------:|
| `admin@aios` | `admin123` | Admin | ✅ | ✅ |
| `operator@aios` | `operator123` | Operator | ✅ | ✅ |
| `viewer@aios` | `viewer123` | Viewer | ❌ | ❌ |

> ⚠️ **Security Note:** These are seed credentials for development. Replace with a database-backed user store for production deployments.

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Auth | Body | Response |
|--------|----------|------|------|----------|
| `POST` | `/api/auth/login` | None | `{ email, password }` | `{ token, role, expires_in }` |

### Queries

| Method | Endpoint | Auth | Min Role | Body | Response |
|--------|----------|------|----------|------|----------|
| `POST` | `/api/query` | JWT | `operator` | `{ query }` | `{ query_id, status: "streaming" }` |

### Intents

| Method | Endpoint | Auth | Min Role | Description |
|--------|----------|------|----------|-------------|
| `GET` | `/api/intents?page=1&limit=20` | JWT | `viewer` | Paginated audit log |
| `PUT` | `/api/intents/:id/approve` | JWT | `operator` | Approve a VALIDATED intent |

### System

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/health` | None | Subsystem health status |
| `GET` | `/api/metrics` | JWT | Live daemon metrics |
| `GET` | `/api/metrics/history` | JWT | Last 100 metric snapshots |

### WebSocket

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `/stream` | `ws://localhost:5000/stream` | Real-time event stream (metrics, tokens, intents) |

---

## 🧪 Testing

### Run the Full Test Suite

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short
```

### Expected Output

```
tests/test_atlas_store.py       ✓✓✓✓✓✓✓ (7 passed)
tests/test_cached_mongodb.py    ✓✓✓ (3 passed)
tests/test_control_plane.py     ✓✓✓✓✓✓✓✓ (8 passed)
tests/test_embedder.py          ✓✓✓✓✓✓ (6 passed)
tests/test_faiss_store.py       ✓✓✓✓✓✓✓ (7 passed)
tests/test_inference_client.py  ✓✓✓✓ (4 passed)
tests/test_prompt_builder.py    ✓✓✓✓✓✓ (6 passed)
tests/test_retriever.py         ✓✓✓✓✓✓ (6 passed)
tests/test_sanitiser.py         ✓✓✓✓✓✓✓✓✓ (9 passed)

======================== 56 passed in 12.34s ========================
```

### Test Coverage

| Module | Tests | Coverage Focus |
|--------|-------|----------------|
| `control_plane.py` | 8 | Validation chain, audit log integrity, hash verification |
| `sanitiser.py` | 9 | AWS keys, JWTs, IPs, emails, PEM keys, MongoDB URIs |
| `faiss_store.py` | 7 | Insert, search, persistence, edge cases |
| `atlas_store.py` | 7 | Vector search, connection caching, error handling |
| `retriever.py` | 6 | Deduplication, weighted scoring, result cap |
| `embedder.py` | 6 | Embedding dimensions, batch processing, normalisation |
| `prompt_builder.py` | 6 | Word count limits, chunk trimming, XML formatting |
| `inference_client.py` | 4 | Streaming, timeout handling, ngrok headers |
| `cached_mongodb.py` | 3 | Connection pooling, lazy init, reuse |

---

## ⚡ Performance Optimisations

| Optimisation | Before | After | Improvement |
|-------------|--------|-------|-------------|
| **Cold Start Latency** | 45s (lazy model load) | < 2s (eager preload) | **95% reduction** |
| **Prompt Eval Time** | 30s+ (10 chunks, 2000+ words) | 12s (6 chunks, ~1000 words) | **60%+ reduction** |
| **Subprocess Stability** | Crashes after ~2h (pipe deadlock) | Indefinite runtime (DEVNULL) | **∞ improvement** |
| **Stream Read Timeout** | 30s (default) | 300s (tuned for GPU cold start) | **No false timeouts** |
| **Health Check Speed** | 5s timeout | 2.5s daemon / 4s API | **Faster failure detection** |

---

## 🔧 Troubleshooting

### Common Issues

<details>
<summary><strong>🔴 503 Service Unavailable from Ollama</strong></summary>

**Cause:** The Kaggle GPU session has expired or the Ngrok tunnel is down.

**Fix:**
1. Check if the Kaggle kernel is still running in the Kaggle web UI
2. If expired, stop the old session and push a new kernel: `kaggle kernels push -p kaggle_kernel`
3. Update `OLLAMA_ENDPOINT` in `.env` with the new Ngrok URL
4. Restart the Python daemon
</details>

<details>
<summary><strong>🔴 ERR_NGROK_334 — Endpoint already online</strong></summary>

**Cause:** A previous Kaggle session is still running and holding the static Ngrok domain.

**Fix:**
1. Go to the Kaggle web UI
2. Navigate to your kernel's output page
3. Click "Cancel" or "Stop" on the running session
4. Wait 30 seconds, then redeploy
</details>

<details>
<summary><strong>🔴 Daemon freezes after a few hours</strong></summary>

**Cause:** Subprocess pipe buffer overflow (64KB limit). Occurs when Ollama's stdout/stderr fills the pipe.

**Fix:** Ensure `task.py` uses `subprocess.DEVNULL` for stdout and stderr:
```python
subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```
</details>

<details>
<summary><strong>🟡 First query is slow (~45 seconds)</strong></summary>

**Cause:** Embedding model loaded lazily on first query.

**Fix:** The daemon should eagerly preload models at startup. Check that `main.py` calls the embedder's `preload()` method during initialisation.
</details>

<details>
<summary><strong>🟡 All intents show REJECTED with 0% confidence</strong></summary>

**Cause:** The LLM is returning empty or malformed responses (often due to Ngrok's browser warning page intercepting API calls).

**Fix:** Ensure `ngrok-skip-browser-warning: true` header is set in `inference_client.py`.
</details>

---

## 📖 Blog & Research

| Resource | Link |
|----------|------|
| **Blog Post** | [The Self-Healing Computer: Why Operating Systems Are Getting an AI Brain](docs/blog_self_healing_computer.md) |
| **Design Document** | [docs/Design.md](docs/Design.md) |
| **Requirements Specification** | [docs/Requirements.md](docs/Requirements.md) |
| **Zenodo Research Archive** | [zenodo.org/anand-raj](https://zenodo.org/me/uploads?q=&f=shared_with_me%3Afalse&l=list&p=1&s=10&sort=newest) |

---

## 👤 Author

<table>
  <tr>
    <td><strong>Anand Raj</strong></td>
    <td>Developer & Researcher</td>
  </tr>
  <tr>
    <td>GitHub</td>
    <td><a href="https://github.com/anan5093">github.com/anan5093</a></td>
  </tr>
  <tr>
    <td>LinkedIn</td>
    <td><a href="https://www.linkedin.com/in/anand-raj-006a41217/">linkedin.com/in/anand-raj-006a41217</a></td>
  </tr>
  <tr>
    <td>Medium</td>
    <td><a href="https://medium.com/@anand.ar1806">medium.com/@anand.ar1806</a></td>
  </tr>
  <tr>
    <td>Zenodo</td>
    <td><a href="https://zenodo.org/me/uploads?q=&f=shared_with_me%3Afalse&l=list&p=1&s=10&sort=newest">Research Archive</a></td>
  </tr>
</table>

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>⭐ Star this repository if you find it useful! ⭐</strong>
  <br/>
  <em>Built with 🧠 AI + 🐧 Linux + ❤️ Passion</em>
</p>
