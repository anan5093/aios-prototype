# System Design Document
## AIOS Prototype — AI-as-Middleware Architecture

---

| Field | Detail |
|---|---|
| **Document Version** | 1.0.0 |
| **Date** | June 2026 |
| **Project** | AI-Native Operating System (AIOS) Prototype |
| **Author** | Anand Raj |
| **Email** | anand.ar1806@gmail.com |
| **GitHub** | [github.com/anan5093](https://github.com/anan5093) |
| **LinkedIn** | [linkedin.com/in/anand-raj-006a41217](https://www.linkedin.com/in/anand-raj-006a41217/) |
| **Medium** | [medium.com/@anand.ar1806](https://medium.com/@anand.ar1806) |
| **Zenodo** | [zenodo.org/me/uploads](https://zenodo.org/me/uploads?q=&f=shared_with_me%3Afalse&l=list&p=1&s=10&sort=newest) |

---

## Table of Contents

1. [Architecture Philosophy](#1-architecture-philosophy)
   - 1.1 [The AI-as-Middleware Concept](#11-the-ai-as-middleware-concept)
   - 1.2 [Why Not In-Kernel AI?](#12-why-not-in-kernel-ai)
   - 1.3 [The Intent-Validate-Execute Pipeline](#13-the-intent-validate-execute-pipeline)
2. [Four-Layer System Architecture](#2-four-layer-system-architecture)
   - 2.1 [Layer Overview](#21-layer-overview)
   - 2.2 [Full Architecture Diagram](#22-full-architecture-diagram)
3. [The Hybrid Compute Topology](#3-the-hybrid-compute-topology)
   - 3.1 [End-to-End Request Lifecycle](#31-end-to-end-request-lifecycle)
   - 3.2 [Data Flow Diagram](#32-data-flow-diagram)
   - 3.3 [Component Interfaces & Port Map](#33-component-interfaces--port-map)
4. [Component Deep Dives](#4-component-deep-dives)
   - 4.1 [Python AI Daemon](#41-python-ai-daemon)
   - 4.2 [RAG Memory Pipeline](#42-rag-memory-pipeline)
   - 4.3 [Prompt Construction Engine](#43-prompt-construction-engine)
   - 4.4 [Kaggle Inference Client](#44-kaggle-inference-client)
   - 4.5 [Deterministic Control Plane](#45-deterministic-control-plane-simulated-ebpf)
   - 4.6 [Express Management API](#46-express-management-api)
   - 4.7 [React Dashboard](#47-react-dashboard)
5. [Security & Privacy Framework](#5-security--privacy-framework)
   - 5.1 [Tunnel Security](#51-tunnel-security)
   - 5.2 [Telemetry Sanitisation Pipeline](#52-telemetry-sanitisation-pipeline)
   - 5.3 [Role-Based Access Control](#53-role-based-access-control)
   - 5.4 [Audit Trail Design](#54-audit-trail-design)
6. [Database Schema Design](#6-database-schema-design)
   - 6.1 [MongoDB Atlas — system_logs Collection](#61-mongodb-atlas--system_logs-collection)
   - 6.2 [SQLite — aios_audit Table](#62-sqlite--aios_audit-table)
   - 6.3 [FAISS Index Structure](#63-faiss-index-structure)
7. [API Contract Reference](#7-api-contract-reference)
   - 7.1 [REST Endpoints](#71-rest-endpoints)
   - 7.2 [WebSocket Events](#72-websocket-events)
8. [Directory Structure](#8-directory-structure)
9. [Technology Stack Summary](#9-technology-stack-summary)
10. [Future Scope — Path to the Kernel](#10-future-scope--path-to-the-kernel)

---

## 1. Architecture Philosophy

### 1.1 The AI-as-Middleware Concept

The fundamental architectural decision of AIOS is to position the AI **not within the kernel**, but as a highly privileged daemon in **user space** — acting as an intelligent middleware layer between the user interface and the OS execution plane.

This design separates the system into two philosophically distinct worlds:

| World | Nature | Example |
|---|---|---|
| **AI Middleware (User Space)** | Probabilistic, context-aware, adaptive | LLM generates a `suggest_renice` intent with 0.91 confidence |
| **OS Execution (Kernel Space)** | Deterministic, guaranteed, atomic | Kernel executes `setpriority()` syscall with exact value |

The AI world and the OS world are connected by a **one-way validated gate**: the Deterministic Control Plane. AI outputs flow downward as intents; they can never bypass validation to touch the execution layer directly.

---

### 1.2 Why Not In-Kernel AI?

Embedding a neural network directly into the Linux kernel is architecturally unsound for three reasons:

1. **Non-determinism:** LLMs are probabilistic. A kernel function that might return different values on identical inputs would violate the fundamental contract of an OS scheduler. Race conditions, priority inversions, and deadlocks would become unpredictable.

2. **Memory Safety:** The Linux kernel runs in a protected memory space. An LLM model (even Gemma-2B Q4 at ~1.5 GB) cannot be safely loaded into kernel address space without catastrophic memory pressure and potential privilege escalation vectors.

3. **Fault Isolation:** A crash in user space kills a process. A crash in kernel space causes a kernel panic. The AI daemon *will* encounter edge cases, hallucinations, and malformed outputs. These must be containable within user space.

**Conclusion:** The AI must remain a user-space citizen, communicating with the kernel only through well-defined, validated, read-only-safe interfaces.

---

### 1.3 The Intent-Validate-Execute Pipeline

Every AI-driven action in AIOS follows a strict three-phase pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                  INTENT-VALIDATE-EXECUTE                     │
│                                                             │
│  Phase 1: INTEND                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  LLM generates structured JSON intent               │   │
│  │  { action_type, target_resource,                    │   │
│  │    proposed_value, confidence_score,                │   │
│  │    reasoning_summary }                              │   │
│  └────────────────────────┬────────────────────────────┘   │
│                            │                                │
│  Phase 2: VALIDATE                                          │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │  Deterministic Control Plane                         │  │
│  │  ✓ Schema validation (Pydantic)                      │  │
│  │  ✓ Allowlist check (action_type ∈ permitted set)     │  │
│  │  ✓ Confidence gating (score ≥ 0.75)                  │  │
│  │  ✓ Human approval gate (Operator/Admin role)         │  │
│  │  ✓ Audit log write (append-only SQLite)              │  │
│  └───────────┬──────────────────────────┬───────────────┘  │
│    REJECTED  │                          │ APPROVED          │
│              ▼                          ▼                   │
│         Log + Notify              Phase 3: EXECUTE          │
│                              ┌────────────────────────┐     │
│                              │  Simulated Execution   │     │
│                              │  Write to             │     │
│                              │  simulation_state.json │     │
│                              └────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Four-Layer System Architecture

### 2.1 Layer Overview

| Layer | Name | Trust Level | Technology | Responsibility |
|---|---|---|---|---|
| **Layer 1** | User Application & UI | User-trusted | React 18 + TypeScript + Vite | Visualises AI reasoning, metrics, RAG retrievals, and audit log. Communicates exclusively with the Express API. |
| **Layer 2** | AIOS Middleware | System-trusted | Python 3.11 + asyncio + Node.js 20 | The intelligence layer. Runs entirely in user space. Orchestrates RAG, LLM inference, intent parsing, and WebSocket broadcasting. |
| **Layer 3** | Deterministic Control Plane | Kernel-adjacent | Python rule engine (simulated eBPF) | Validates all AI intents against allowlists and confidence thresholds. The only path from Layer 2 to Layer 4. |
| **Layer 4** | OS Execution Layer | Kernel | Linux Kernel (simulated in v1.0) | Manages actual processes, CPU scheduling, VFS, and memory. Receives only deterministic, validated instructions. |

---

### 2.2 Full Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════╗
║  LAYER 1 — USER APPLICATION & UI                                     ║
║                                                                      ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │           Web-Based AIOS Dashboard (React Frontend)            │  ║
║  │  ┌──────────────┐ ┌────────────┐ ┌──────────┐ ┌───────────┐  │  ║
║  │  │ReasoningTrace│ │ RAGViewer  │ │ Metrics  │ │ AuditLog  │  │  ║
║  │  │(WS stream)   │ │(similarity)│ │ Panel    │ │(RBAC)     │  │  ║
║  │  └──────────────┘ └────────────┘ └──────────┘ └───────────┘  │  ║
║  └───────────────────────┬────────────────────────────────────────┘  ║
║                          │ REST + JWT / WebSocket                    ║
╠══════════════════════════╪═══════════════════════════════════════════╣
║  LAYER 2 — AIOS MIDDLEWARE (USER SPACE)                              ║
║                          │                                           ║
║  ┌───────────────────────▼────────────────────────────────────────┐  ║
║  │             Express Management API (Node.js :5000)             │  ║
║  └───────────────────────┬────────────────────────────────────────┘  ║
║                          │ IPC / localhost socket                    ║
║  ┌───────────────────────▼────────────────────────────────────────┐  ║
║  │                Python AI Daemon (asyncio)                       │  ║
║  │  ┌────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │  ║
║  │  │ Monitoring │  │  RAG Pipeline   │  │  Inference Client   │ │  ║
║  │  │   Loop     │  │ FAISS + Atlas   │  │  Kaggle/ngrok +     │ │  ║
║  │  │(watchdog)  │  │ Hybrid Retrieval│  │  Local Fallback     │ │  ║
║  │  └────────────┘  └─────────────────┘  └─────────────────────┘ │  ║
║  │  ┌────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │  ║
║  │  │ Embedding  │  │ Prompt Builder  │  │  Intent Parser +    │ │  ║
║  │  │(MiniLM CPU)│  │ (XML context    │  │  Sanitiser          │ │  ║
║  │  │            │  │  blocks)        │  │                     │ │  ║
║  │  └────────────┘  └─────────────────┘  └─────────────────────┘ │  ║
║  └───────────────────────┬────────────────────────────────────────┘  ║
║                          │                                           ║
║  ┌────────────────────── │ ─────────────┐  ┌─────────────────────┐  ║
║  │  FAISS Local Index    │              │  │  MongoDB Atlas      │  ║
║  │  (recent 1hr context) │              │  │  (persistent memory)│  ║
║  └───────────────────────│──────────────┘  └─────────────────────┘  ║
║                          │ HTTPS (ngrok)                             ║
║           ┌──────────────▼─────────────────┐                        ║
║           │  Kaggle Notebook (T4/P100 GPU)         │                        ║
║           │  Ollama → Gemma-2B-Q4 / Llama3-8B-Q4  │                        ║
║           └────────────────────────────────┘                        ║
╠══════════════════════════╪═══════════════════════════════════════════╣
║  LAYER 3 — DETERMINISTIC CONTROL PLANE                               ║
║                          │                                           ║
║  ┌───────────────────────▼────────────────────────────────────────┐  ║
║  │  Rule Engine (simulated eBPF)                                  │  ║
║  │  Allowlist Check → Confidence Gate → Human Approval → Audit   │  ║
║  └───────────────────────┬────────────────────────────────────────┘  ║
╠══════════════════════════╪═══════════════════════════════════════════╣
║  LAYER 4 — OS EXECUTION LAYER (SIMULATED IN V1.0)                   ║
║                          │                                           ║
║  ┌───────────────────────▼────────────────────────────────────────┐  ║
║  │  Deterministic Linux Kernel                                    │  ║
║  │  [ Manages Processes ] [ CPU Scheduler ] [ VFS ] [ Memory ]   │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 3. The Hybrid Compute Topology

### 3.1 End-to-End Request Lifecycle

The following describes the complete data flow for a user-initiated AI query (e.g., *"Why is the system showing high memory pressure?"*):

| Step | Actor | Action |
|---|---|---|
| **1** | User (Dashboard) | Submits natural language query via React UI form. Dashboard sends `POST /api/query` to Express API with JWT in `Authorization` header. |
| **2** | Express API | Authenticates JWT, validates request body schema, rate-limits if necessary, forwards query to Python daemon via localhost socket. |
| **3** | Python Daemon | Receives query string. Triggers **parallel hybrid RAG retrieval**: `asyncio.gather(faiss_search(query), atlas_search(query))`. |
| **4** | FAISS Store | Embeds query using `all-MiniLM-L6-v2` (CPU, ~200ms). Performs cosine similarity search on local index. Returns top-5 recent chunks with scores. |
| **5** | Atlas Store | Sends `$vectorSearch` aggregation query to MongoDB Atlas. Returns top-5 historical chunks with scores. Atlas latency ~300–700ms. |
| **6** | Retriever | Deduplicates results by `chunk_id`. Re-ranks by combined score. Selects top-8 unique chunks. |
| **7** | Prompt Builder | Constructs context-enriched prompt: System Role Prompt + XML-formatted RAG context blocks + sanitised user query. Total prompt ≤ 3,000 tokens. |
| **8** | Telemetry Sanitiser | Applies three-stage sanitisation filter to the outbound prompt payload before transmission. |
| **9** | Inference Client | Sends `POST /api/generate` to the **Kaggle Ollama endpoint via ngrok static domain** (`your-name.ngrok-free.app`) with `streaming=true`. Opens async SSE stream for token-by-token response. No URL lookup — endpoint is permanent. |
| **10** | Kaggle GPU (T4/P100) | Runs quantised model inference with full CUDA acceleration (`OLLAMA_GPU_LAYERS=100`). Streams tokens back via Server-Sent Events. Average throughput: ~30–60 tokens/second. Model weights pre-cached in 20 GB persistent storage — no cold-download delay after first session. |
| **11** | Daemon | Streams tokens to React dashboard via WebSocket (`ws://localhost:5000/stream`) in real time as they arrive. |
| **12** | Intent Parser | On stream completion, applies regex extraction to find JSON intent block. Validates against Pydantic schema. Retries once on parse failure. |
| **13** | Control Plane | Validates intent: allowlist check → confidence gate → writes to `aios_audit.db`. Assigns status: `APPROVED`, `REJECTED`, or `PENDING_REVIEW`. |
| **14** | WebSocket | Broadcasts validation result event to dashboard. Audit log updates in real time. If `PENDING_REVIEW`, Approve/Reject buttons appear. |
| **15** | User (Operator) | Reviews intent in Audit Log. Clicks Approve. Dashboard sends `PUT /api/intents/:id/approve` with Operator JWT. |
| **16** | Control Plane | Updates `aios_audit.db` record: `execution_status = SIMULATED_EXECUTED`, `approved_by = operator@aios`. Writes to `data/simulation_state.json`. |

---

### 3.2 Data Flow Diagram

```
User Query
    │
    ▼
┌─────────────────────┐
│   React Dashboard   │──────────────────────────────────────────────────┐
│   POST /api/query   │                                         WS Stream │
└─────────────────────┘                                                   │
    │ JWT Auth                                                             │
    ▼                                                                     │
┌─────────────────────┐                                                   │
│    Express API      │                                                   │
│    :5000            │                                                   │
└─────────────────────┘                                                   │
    │ IPC                                                                  │
    ▼                                                                     │
┌─────────────────────────────────────────────────────────────┐          │
│                    Python AI Daemon                          │          │
│                                                             │          │
│  ┌──────────────────┐    ┌───────────────────────────────┐ │          │
│  │  Hybrid Retrieval │    │      Prompt Builder           │ │          │
│  │                  │    │  [System Role]                 │ │          │
│  │  ┌─────────────┐ │    │  <context>                    │ │          │
│  │  │ FAISS local │ │───►│    [RAG chunks + metadata]    │ │          │
│  │  └─────────────┘ │    │  </context>                   │ │          │
│  │  ┌─────────────┐ │    │  [User Query]                 │ │          │
│  │  │ Atlas cloud │ │    └───────────────┬───────────────┘ │          │
│  └──────────────────┘                    │                 │          │
│                                          │ Sanitise        │          │
│                                          ▼                 │          │
│                              ┌───────────────────────┐     │          │
│                              │   Inference Client    │     │          │
│                              │                       │     │          │
│                              │  Primary:             │     │◄─────────┘
│                              │  ngrok static domain  │     │  Token stream
│                              │  → Kaggle GPU         │     │  via WebSocket
│                              │                       │     │
│                              │  Fallback:            │     │
│                              │  localhost Ollama     │     │
│                              └──────────┬────────────┘     │
│                                         │                  │
│                              ┌──────────▼────────────┐     │
│                              │   Intent Parser       │     │
│                              │   Pydantic Schema     │     │
│                              └──────────┬────────────┘     │
│                                         │                  │
│                              ┌──────────▼────────────┐     │
│                              │  Control Plane        │     │
│                              │  Validate → Audit     │     │
│                              └──────────┬────────────┘     │
└─────────────────────────────────────────│──────────────────┘
                                          │
                                          ▼
                               simulation_state.json
                               aios_audit.db
```

---

### 3.3 Component Interfaces & Port Map

| Service | Host | Port | Protocol | Auth |
|---|---|---|---|---|
| React Dashboard | localhost | 3000 | HTTP | None (browser) |
| Express Management API | localhost | 5000 | REST / HTTP | JWT Bearer |
| WebSocket Stream | localhost | 5000 | WebSocket (`/stream`) | JWT query param |
| Python Daemon IPC | localhost | 8765 | HTTP (internal only) | None (localhost-only) |
| Ollama (Local Fallback) | localhost | 11434 | HTTP | None |
| Ollama (Kaggle via ngrok) | `your-name.ngrok-free.app` | 443 | HTTPS | Basic Auth |
| MongoDB Atlas | `cluster0.*.mongodb.net` | 27017 | MongoDB Wire / TLS | Connection string + user/pass |
| FAISS Index | Local filesystem | — | Python library | Filesystem permissions |

---

## 4. Component Deep Dives

### 4.1 Python AI Daemon

The daemon (`daemon/main.py`) is an `asyncio`-based long-running process and the central nervous system of AIOS. It is composed of five concurrent subsystems:

#### Monitoring Loop
```
watchdog FileSystemEventHandler
    │
    ├── on_modified(syslog)   → queue_chunk(content)
    ├── on_modified(kern.log) → queue_chunk(content)
    └── on_modified(bash_history) → queue_chunk(content)

Poll interval: 5s fallback if watchdog misses events
```

#### Embedding Worker
```
background thread (ThreadPoolExecutor)
    │
    └── consume embedding_queue
            │
            ├── chunk_text(raw_log, size=512, overlap=50)
            ├── model.encode(chunks)  ← all-MiniLM-L6-v2 CPU
            ├── faiss_store.ingest(chunks, embeddings, metadata)
            └── atlas_store.ingest_batch(documents)
```

#### Query Handler
```
async handle_query(query_string)
    │
    ├── embeddings = embed(query_string)
    ├── faiss_chunks, atlas_chunks = await asyncio.gather(
    │       faiss_store.search(embedding, k=5),
    │       atlas_store.vector_search(embedding, k=5)
    │   )
    ├── chunks = deduplicate_and_rerank(faiss_chunks + atlas_chunks)[:8]
    ├── prompt = prompt_builder.build(query_string, chunks)
    ├── sanitised_prompt = sanitiser.clean(prompt)
    ├── async for token in inference_client.stream(sanitised_prompt):
    │       await ws_broadcaster.send(token)
    ├── intent = intent_parser.parse(full_completion)
    └── control_plane.validate_and_log(intent)
```

#### WebSocket Broadcaster
- Maintains a set of active WebSocket connections
- Broadcasts token events, system events (circuit breaker, fallback activation), and control plane results to all connected clients

#### Health Monitor
- Polls Kaggle ngrok static endpoint every 30 seconds via `GET /api/tags`
- Updates circuit-breaker state
- No URL re-discovery needed — static domain is permanent; daemon simply waits for the endpoint to respond after a Kaggle session restart

---

### 4.2 RAG Memory Pipeline

#### Ingestion Pipeline

```
Raw Log Entry
      │
      ▼
┌─────────────────────────────────────────────┐
│  Sanitisation Filter                         │
│  (strip PII, mask secrets)                  │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  RecursiveCharacterTextSplitter              │
│  chunk_size = 512 tokens                    │
│  chunk_overlap = 50 tokens                  │
│  separators = ["\n\n", "\n", " ", ""]       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  all-MiniLM-L6-v2 Encoder (CPU)             │
│  Output: 384-dimensional float32 vectors    │
│  Batch size: 32 chunks                      │
└──────────┬──────────────────┬───────────────┘
           │                  │
           ▼                  ▼
   FAISS IndexFlatIP    MongoDB Atlas
   (cosine similarity)  ($vectorSearch)
   Local file persist   Persistent cloud
```

#### Retrieval Strategy

```
Query String
      │
      ▼
  embed(query)  →  384-dim vector
      │
      ├──────────────────────────────────┐
      │                                  │
      ▼                                  ▼
FAISS search(k=5)              Atlas $vectorSearch(k=5)
Recent context                 Historical context
(last 1hr window)              (full history)
      │                                  │
      └──────────────┬───────────────────┘
                     │
                     ▼
           Merge & Deduplicate
           (by chunk_id)
                     │
                     ▼
           Re-rank by combined score
           score = 0.6 * faiss_score + 0.4 * atlas_score
                     │
                     ▼
           Top-8 unique chunks
           with full metadata
```

**Metadata stored per chunk:**

```json
{
  "chunk_id": "sha256_of_content[:16]",
  "source_file": "kern.log",
  "timestamp": "2026-06-04T10:23:41Z",
  "log_level": "ERROR",
  "severity": 3,
  "host_id": "HOST_ANON_001",
  "content": "Out of memory: Kill process 1847 ...",
  "embedding": [0.023, -0.118, ...],
  "ingested_at": "2026-06-04T10:23:45Z"
}
```

---

### 4.3 Prompt Construction Engine

The prompt builder constructs a fully structured prompt that guides the LLM to produce a JSON-formatted intent:

```
[SYSTEM ROLE]
You are the AIOS Intelligence Daemon. Your task is to analyse the provided
system context and generate a structured optimisation intent in JSON format.
You must ONLY suggest actions from the permitted set:
{suggest_renice, suggest_swap_adjust, suggest_log_rotate, suggest_cgroup_limit}

You MUST respond with a JSON block matching this exact schema:
{
  "action_type": "<permitted action>",
  "target_resource": "<process name or system parameter>",
  "proposed_value": "<specific recommended value>",
  "confidence_score": <float 0.0–1.0>,
  "reasoning_summary": "<1-2 sentence explanation citing context>"
}

[SYSTEM MEMORY CONTEXT]
<context>
  <chunk id="1" source="kern.log" timestamp="2026-06-04T10:23:41Z"
         score="0.91" log_level="ERROR">
    Out of memory: Kill process 1847 (chrome) score 823 or sacrifice child
  </chunk>
  <chunk id="2" source="syslog" timestamp="2026-06-04T10:18:22Z"
         score="0.85" log_level="WARN">
    Memory pressure detected. Available: 312MB / 7930MB
  </chunk>
  ...
</context>

[USER QUERY]
Why is the system showing high memory pressure?
```

---

### 4.4 Kaggle Inference Client

The inference client (`daemon/inference_client.py`) manages all communication with the Kaggle-hosted Ollama backend. The key architectural simplification vs. a Colab-based approach: **no URL discovery logic**. The ngrok static domain is set once in `.env` and never changes, even across Kaggle session restarts.

#### Kaggle Notebook Setup (runs in `/kaggle/working/`)
```python
# Environment configured in the Kaggle notebook before Ollama starts:
os.environ['CUDA_HOME'] = '/usr/local/cuda'
os.environ['OLLAMA_GPU_LAYERS'] = '100'    # all layers on GPU
os.environ['OLLAMA_SCHED_SPREAD'] = '1'    # spread across T4×2 if selected

# Static domain — set once, lives forever in .env
# OLLAMA_ENDPOINT=https://your-name.ngrok-free.app
# Model weights cached in Kaggle's 20GB persistent storage after first pull
```

#### Simplified Startup (no URL polling needed)
```python
# On daemon startup — just health-check the static endpoint:
async def _health_check(self) -> bool:
    try:
        r = await self.client.get(
            f"{self.endpoint}/api/tags",
            headers={"Authorization": f"Basic {self.b64_creds}"},
            timeout=5.0
        )
        return r.status_code == 200
    except Exception:
        return False
# No _discover_url(), no Google Drive polling, no ngrok_url.txt
```

#### Circuit Breaker State Machine

```
         ┌────────────────────────────────────────┐
         │                                        │
    ┌────▼─────┐   3 failures      ┌─────────────▼──────┐
    │  CLOSED  │──────────────────►│      OPEN           │
    │ (normal) │                   │  (using fallback)   │
    └──────────┘                   └─────────────────────┘
         ▲                                   │
         │ success                           │ 30s timeout
         │                      ┌────────────▼──────────┐
         └──────────────────────│    HALF-OPEN           │
                                │  (probe one request)  │
                                └───────────────────────┘

Recovery note: When Kaggle session restarts, the same static domain
resumes on the same port. Circuit breaker transitions HALF-OPEN → CLOSED
on the first successful probe. No manual intervention required.
```

#### Streaming Request
```python
async def stream_inference(prompt: str) -> AsyncGenerator[str, None]:
    endpoint = os.getenv("OLLAMA_ENDPOINT")  # static ngrok domain
    b64_creds = base64.b64encode(
        f"{NGROK_AUTH_USER}:{NGROK_AUTH_PASS}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", f"{endpoint}/api/generate",
            json={"model": MODEL_NAME, "prompt": prompt, "stream": True},
            headers={"Authorization": f"Basic {b64_creds}"},
            timeout=30.0
        ) as response:
            async for line in response.aiter_lines():
                data = json.loads(line)
                yield data["response"]  # single token
                if data.get("done"):
                    break
```

#### Model Selection by Kaggle GPU Tier

| Kaggle Accelerator | VRAM | Recommended Model | Intent Quality |
|---|---|---|---|
| T4 ×1 | 16 GB | `gemma:2b-instruct-q4_K_M` | Good — sufficient for structured JSON |
| P100 | 16 GB HBM2 | `llama3:8b-instruct-q4_K_M` (~5 GB) | Better — stronger reasoning |
| T4 ×2 | 32 GB combined | `llama3:8b-instruct-q4_K_M` | Best — largest free-tier option |

Configurable by changing `MODEL_NAME` in `.env` — no code changes required.

---

### 4.5 Deterministic Control Plane (Simulated eBPF)

The control plane (`daemon/control_plane.py`) simulates the validation semantics of a real eBPF-based kernel enforcer:

#### Intent Schema (Pydantic)
```python
class AIIntent(BaseModel):
    action_type: str
    target_resource: str
    proposed_value: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str

PERMITTED_ACTIONS = {
    "suggest_renice",
    "suggest_swap_adjust",
    "suggest_log_rotate",
    "suggest_cgroup_limit"
}
```

#### Validation Logic
```
Receive raw LLM completion string
    │
    ▼
Extract JSON block via regex: r'\{[^{}]+\}'
    │
    ├─ Parse failure → retry once → PARSE_ERROR → discard
    │
    ▼
Pydantic schema validation
    │
    ├─ Schema failure → SCHEMA_INVALID → reject + log
    │
    ▼
action_type ∈ PERMITTED_ACTIONS?
    │
    ├─ No → DISALLOWED_ACTION_TYPE → reject + log
    │
    ▼
confidence_score ≥ 0.75?
    │
    ├─ No → status = PENDING_REVIEW → log + notify dashboard
    │
    ▼
status = VALIDATED → write to aios_audit.db
    │
    ▼
Await human approval (Operator/Admin via dashboard)
    │
    ▼
status = SIMULATED_EXECUTED → write to simulation_state.json
```

---

### 4.6 Express Management API

The Express API (`api/server.js`) acts as the trusted gateway between the React dashboard and the Python daemon:

#### Route Structure
```
/api
 ├── POST   /auth/login          → Return JWT (seeded users)
 ├── GET    /health              → Service status object
 ├── GET    /metrics             → CPU, RAM, FAISS stats (psutil via Python)
 ├── GET    /session             → Current inference backend, circuit-breaker state
 ├── POST   /query               → Forward query to daemon [auth: any role]
 ├── GET    /intents             → Paginated audit log [auth: any role]
 ├── PUT    /intents/:id/approve → Approve PENDING_REVIEW intent [auth: operator+]
 ├── PUT    /intents/:id/reject  → Reject PENDING_REVIEW intent [auth: operator+]
 └── GET    /chunks/:query       → Preview RAG retrieval for a query [auth: any role]
```

#### Middleware Stack
```
Incoming Request
    │
    ▼
CORS (allow localhost:3000 only)
    │
    ▼
express.json() + body size limit (16KB)
    │
    ▼
JWT Verification (skip /auth/login, /health)
    │
    ▼
Role Authorization (per-route RBAC middleware)
    │
    ▼
Request Logging (morgan → file)
    │
    ▼
Route Handler
    │
    ▼
Error Handler (structured JSON error responses)
```

---

### 4.7 React Dashboard

The React dashboard (`frontend/src/`) is built with Vite + React 18 + TypeScript. It communicates with the Express API via REST and with the daemon's token stream via WebSocket.

#### Component Tree

```
App
 ├── AuthProvider (JWT context)
 ├── Header (user role, health bar, connection status)
 ├── MainLayout
 │    ├── QueryForm (submit natural-language query)
 │    ├── ReasoningTrace
 │    │    ├── TokenStream (WebSocket consumer)
 │    │    ├── InferenceSourceBadge (Kaggle GPU / Local Fallback)
 │    │    └── LatencyDisplay
 │    ├── RAGViewer
 │    │    ├── ChunkCard (similarity score colour-coded)
 │    │    └── ChunkExpander (full content on click)
 │    ├── MetricsPanel
 │    │    ├── CPUGauge
 │    │    ├── RAMGauge (warning at 75%)
 │    │    ├── FAISSIndexStats
 │    │    └── AtlasDocCount
 │    └── AuditLog
 │         ├── IntentTable (paginated)
 │         ├── StatusBadge (APPROVED / REJECTED / PENDING)
 │         └── ApprovalButtons (Operator/Admin only)
 └── ServiceHealthBar
      ├── FAISSStatus
      ├── AtlasStatus
      ├── KaggleTunnelStatus
      └── LocalOllamaStatus
```

---

## 5. Security & Privacy Framework

### 5.1 Tunnel Security

All traffic between the local daemon and the Kaggle inference backend traverses the ngrok tunnel:

| Control | Implementation |
|---|---|
| **Transport Encryption** | TLS 1.3 enforced by ngrok (cannot be downgraded) |
| **Authentication** | HTTP Basic Auth on every request: `Authorization: Basic base64(user:pass)` |
| **Credential Storage** | `NGROK_AUTH_USER` + `NGROK_AUTH_PASS` in `.env` only. Never in source code. |
| **Certificate Validation** | Daemon verifies ngrok's SSL certificate on every session start. |
| **Payload Size Limit** | Requests capped at 8 KB. Larger payloads are rejected before transmission. |
| **Prompt Injection Guard** | System role prompt is hardcoded and prepended server-side. User input cannot override the system prompt. |

---

### 5.2 Telemetry Sanitisation Pipeline

Before any data leaves the local machine, it passes through a three-stage filter implemented in `daemon/sanitiser.py`:

#### Stage 1 — Pattern Masking (Regex)

| Pattern | Regex | Replacement |
|---|---|---|
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `[AWS_KEY_REDACTED]` |
| AWS Secret Key | `[0-9a-zA-Z/+]{40}` | `[AWS_SECRET_REDACTED]` |
| JWT Token | `eyJ[A-Za-z0-9+/=]+\.[A-Za-z0-9+/=]+\.[A-Za-z0-9+/=_-]+` | `[JWT_REDACTED]` |
| Private IPv4 | `(10\|172\.(1[6-9]\|2\d\|3[01])\|192\.168)\.\d+\.\d+` | `[PRIVATE_IP]` |
| Generic Secret | `(password\|passwd\|secret\|token)\s*[=:]\s*\S+` | `[SECRET_REDACTED]` |
| Email Address | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | `[EMAIL_REDACTED]` |

#### Stage 2 — Entity Anonymisation

- Real hostname (read from `socket.gethostname()` at startup) → `AIOS_HOST`
- Real username (read from `os.getenv("USER")` at startup) → `AIOS_USER`
- Paths containing the real username → replace with `/home/sandbox/`

#### Stage 3 — Schema Validation

The sanitised payload must conform to a strict JSON schema. Any field not in the schema is dropped (`additionalProperties: false`). This prevents accidental leakage of unexpected fields.

---

### 5.3 Role-Based Access Control

| Role | Login | View Dashboard | Submit Query | Approve Intents | Configure Daemon |
|---|---|---|---|---|---|
| `viewer` | `viewer@aios` | ✓ | ✗ | ✗ | ✗ |
| `operator` | `operator@aios` | ✓ | ✓ | ✓ | ✗ |
| `admin` | `admin@aios` | ✓ | ✓ | ✓ | ✓ |

JWT payload structure:
```json
{
  "sub": "operator@aios",
  "role": "operator",
  "iat": 1748985600,
  "exp": 1749072000
}
```

---

### 5.4 Audit Trail Design

The SQLite `aios_audit` table is **append-only** — no UPDATE or DELETE operations are performed. Every record includes a SHA-256 hash for tamper evidence:

```sql
CREATE TABLE aios_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    intent_json     TEXT    NOT NULL,
    action_type     TEXT    NOT NULL,
    confidence_score REAL   NOT NULL,
    validation_result TEXT  NOT NULL,  -- APPROVED | REJECTED | PENDING_REVIEW
    rejection_reason  TEXT,
    execution_status  TEXT  NOT NULL,  -- PENDING | SIMULATED_EXECUTED | REJECTED
    approved_by     TEXT,
    approved_at     TEXT,
    record_hash     TEXT    NOT NULL   -- SHA-256(all fields except record_hash)
);
```

---

## 6. Database Schema Design

### 6.1 MongoDB Atlas — `system_logs` Collection

```json
{
  "_id": ObjectId,
  "chunk_id": "a3f8c2e1b0d74f9a",
  "source_file": "kern.log",
  "timestamp": ISODate("2026-06-04T10:23:41Z"),
  "log_level": "ERROR",
  "severity": 3,
  "host_id": "AIOS_HOST",
  "content": "Out of memory: Kill process 1847 ...",
  "embedding": [0.023, -0.118, 0.445, ...],  // 384 floats
  "ingested_at": ISODate("2026-06-04T10:23:45Z"),
  "session_id": "session_20260604_001"
}
```

**Vector Search Index Definition:**
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "log_level"
    },
    {
      "type": "filter",
      "path": "timestamp"
    }
  ]
}
```

---

### 6.2 SQLite — `aios_audit` Table

See [Section 5.4](#54-audit-trail-design) for full schema.

---

### 6.3 FAISS Index Structure

| Property | Value |
|---|---|
| **Index Type** | `IndexFlatIP` (Inner Product / cosine after L2 normalisation) |
| **Dimensions** | 384 |
| **Distance Metric** | Cosine similarity (vectors L2-normalised before insert) |
| **Persistence** | `data/faiss_index.bin` + `data/faiss_metadata.pkl` |
| **Metadata Store** | Python dict (in-memory), pickled alongside index |
| **Capacity** | ~50,000 vectors before performance degrades on local i5 |
| **Rebuild Strategy** | Full rebuild if `EMBEDDING_MODEL` env var changes |

---

## 7. API Contract Reference

### 7.1 REST Endpoints

#### `POST /api/auth/login`
```json
// Request
{ "email": "operator@aios", "password": "changeme" }

// Response 200
{ "token": "eyJ...", "role": "operator", "expires_in": 86400 }
```

#### `GET /api/metrics`
```json
// Response 200
{
  "cpu_percent": 23.4,
  "ram_used_gb": 1.24,
  "ram_total_gb": 7.74,
  "ram_percent": 16.0,
  "faiss_vector_count": 12450,
  "atlas_doc_count": 48320,
  "daemon_uptime_s": 3612
}
```

#### `POST /api/query`
```json
// Request
{ "query": "Why is CPU load high?" }

// Response 202 (query accepted, tokens stream via WebSocket)
{ "query_id": "qry_20260604_abc123", "status": "streaming" }
```

#### `GET /api/intents?page=1&limit=20`
```json
// Response 200
{
  "total": 47,
  "page": 1,
  "intents": [
    {
      "id": 23,
      "created_at": "2026-06-04T10:25:00Z",
      "action_type": "suggest_renice",
      "target_resource": "chrome",
      "proposed_value": "10",
      "confidence_score": 0.89,
      "validation_result": "APPROVED",
      "execution_status": "PENDING"
    }
  ]
}
```

#### `PUT /api/intents/:id/approve`
```json
// Response 200
{ "id": 23, "execution_status": "SIMULATED_EXECUTED", "approved_by": "operator@aios" }
```

---

### 7.2 WebSocket Events

All events are JSON objects sent over `ws://localhost:5000/stream`:

| Event Type | Payload | Description |
|---|---|---|
| `token` | `{"type":"token","data":"word","query_id":"..."}` | Single inference token from LLM stream |
| `stream_done` | `{"type":"stream_done","query_id":"...","latency_ms":2341}` | Stream complete; includes total latency |
| `intent_parsed` | `{"type":"intent_parsed","intent":{...}}` | Parsed intent object after completion |
| `validation_result` | `{"type":"validation_result","result":"APPROVED","intent_id":23}` | Control plane decision |
| `circuit_breaker` | `{"type":"circuit_breaker","state":"OPEN","fallback":"local"}` | Circuit breaker state change |
| `rag_retrieved` | `{"type":"rag_retrieved","chunks":[...],"query_id":"..."}` | RAG retrieval results for dashboard |
| `metrics_update` | `{"type":"metrics_update","cpu":23.4,"ram":1.24,...}` | Periodic system metrics push |

---

## 8. Directory Structure

```
aios-root/
├── .env                          # All secrets and config (gitignored)
├── .env.example                  # Template with placeholder values
├── .gitignore
├── README.md
│
├── daemon/                       # Python AI Daemon
│   ├── main.py                   # asyncio entry point
│   ├── embedder.py               # all-MiniLM-L6-v2 embedding service
│   ├── faiss_store.py            # FAISS index wrapper
│   ├── atlas_store.py            # MongoDB Atlas vector store wrapper
│   ├── retriever.py              # Hybrid retrieval + deduplication
│   ├── prompt_builder.py         # Prompt construction engine
│   ├── sanitiser.py              # Three-stage telemetry sanitisation
│   ├── inference_client.py       # Kaggle/ngrok static domain + local Ollama client
│   ├── intent_parser.py          # JSON intent extraction + Pydantic schema
│   ├── control_plane.py          # Deterministic validation + audit log
│   ├── ws_broadcaster.py         # WebSocket event broadcaster
│   └── requirements.txt
│
├── api/                          # Express Management API
│   ├── server.js                 # Entry point
│   ├── routes/
│   │   ├── auth.js
│   │   ├── query.js
│   │   ├
<truncated 5043 bytes>

NOTE: The output was truncated because it was too long. Use a more targeted query or a smaller range to get the information you need.
