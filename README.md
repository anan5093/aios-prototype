# AIOS — AI-Native Operating System Prototype

**Version:** 1.0.0 | **Author:** Anand Raj | **Target OS:** Ubuntu 22.04 LTS

---

## Architecture Summary
The AIOS (AI-Native Operating System) Prototype demonstrates AI as a privileged user-space middleware daemon on Linux, integrated with a hybrid cloud compute topology and a React transparency dashboard. The Python daemon runs entirely in user space as a privileged middleware layer, monitoring system telemetry via mock logs, performing hybrid RAG retrieval (FAISS local + MongoDB Atlas cloud), forwarding prompts to a Google Colab T4 via an ngrok tunnel, parsing AI responses into structured intents, and gating all execution through a Deterministic Control Plane that requires human approval before any simulated action is logged to `data/simulation_state.json`.

```
┌─────────────────────────────────────────────────────────────────┐
│                LOCAL MACHINE (i5-1135G7, 8GB RAM)               │
│                                                                  │
│  React Dashboard :3000  ←→  Express API :5000  ←→  Python Daemon │
│                                                         ↕        │
│                           FAISS (local)   Embedding (all-MiniLM) │
│                                  ↕                               │
│          ┌──────────────────────────────────────────────┐        │
│          │  CLOUD INFERENCE: Google Colab T4 → Ollama   │        │
│          │                → ngrok tunnel                │        │
│          ├──────────────────────────────────────────────┤        │
│          │  CLOUD MEMORY:  MongoDB Atlas Vector Search   │        │
│          │                → ap-south-1 region           │        │
│          └──────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites
- **Python 3.11**
- **Node.js 20 LTS**
- **Google Colab Account** (for free T4 GPU runtime access)
- **MongoDB Atlas Account** (for free M0 vector search cluster)
- **ngrok Account** (for free-tier tunnel authentication)

---

## Quick Start
1. `git clone <repo> && cd AIOS-Prototype_Rag`
2. Copy the configuration template: `cp .env.example .env` and fill in the required API keys and connection strings.
3. Set up a Python virtual environment: `python -m venv .venv && source .venv/bin/activate`
4. Install daemon requirements: `pip install -r daemon/requirements.txt`
5. Generate synthetic test logs: `python scripts/generate_mock_logs.py`
6. Ingest logs to vector databases: `python scripts/ingest_mock_logs.py` (after configuring your MongoDB Atlas URI in `.env`)
7. Open `scripts/aios_colab_server.ipynb` in Google Colab, run all cells, and copy the generated ngrok endpoint URL into your local `.env`.
8. Start the Python AI Daemon: `python daemon/main.py`
9. Start the Express Management API: `cd api && npm install && npm run dev`
10. Start the React transparency dashboard: `cd ../frontend && npm install && npm run dev`
11. Open `http://localhost:3000` in your browser and log in with the credentials:
    - **Username:** `operator@aios`
    - **Password:** `operator123`

---

## Services Map

| Service | Technology | Port | Description |
|---------|-----------|------|-------------|
| React Dashboard | React 18 + Vite | 3000 | Transparency UI with live streaming |
| Express API | Node.js + Express 5 | 5000 | REST + WebSocket management API |
| Python Daemon | Python asyncio + aiohttp | 8765 | AI middleware orchestrator (IPC) |
| Ollama (Cloud) | Google Colab T4 + ngrok | dynamic | LLM inference (gemma:2b) |
| Ollama (Local) | Ollama | 11434 | Fallback LLM inference |
| MongoDB Atlas | motor (async) | 27017 | Cloud vector store |

---

## Security & Safety Guarantees
- **No Kernel Space Interaction:** The AI daemon runs entirely in user space. No kernel writes, raw syscalls, or `sysctl` modifications are made.
- **Human-in-the-Loop Gatekeeping:** The Deterministic Control Plane validates all generated AI intents. Any action requires explicit operator approval before execution simulation.
- **Data Sanitisation:** A three-stage sanitisation engine scrubs all telemetry payloads for secrets (AWS keys, JWTs, IPs, and passwords) before egress.
- **Append-only Audit Log:** System audit logs are written to a local SQLite database and protected with SHA-256 tamper-evident record hashing.

---

## Running Tests
To run the automated Python test suite:
```bash
python -m pytest tests/ -v --tb=short
```
