# Requirements Document
## AIOS Prototype — Hybrid Bounded-AI Architecture

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

1. [Executive Summary](#1-executive-summary)
2. [Hardware & Environment Constraints](#2-hardware--environment-constraints)
   - 2.1 [Local Hardware Specification](#21-local-hardware-specification)
   - 2.2 [The Hybrid Compute Topology — Mitigation Strategy](#22-the-hybrid-compute-topology--mitigation-strategy)
   - 2.3 [Environment Summary Diagram](#23-environment-summary-diagram)
3. [Functional Requirements](#3-functional-requirements)
   - 3.1 [System Monitoring & Telemetry](#31-system-monitoring--telemetry)
   - 3.2 [RAG Memory Pipeline](#32-rag-memory-pipeline)
   - 3.3 [AI Daemon & Cloud Inference](#33-ai-daemon--cloud-inference)
   - 3.4 [Deterministic Control Plane (Bounded Execution)](#34-deterministic-control-plane-bounded-execution)
   - 3.5 [Dashboard & Transparency UI](#35-dashboard--transparency-ui)
4. [Non-Functional Requirements](#4-non-functional-requirements)
   - 4.1 [Latency Requirements](#41-latency-requirements)
   - 4.2 [Resource Overhead Requirements](#42-resource-overhead-requirements)
   - 4.3 [Modularity & Configurability](#43-modularity--configurability)
   - 4.4 [Reliability & Graceful Degradation](#44-reliability--graceful-degradation)
   - 4.5 [Security Requirements](#45-security-requirements)
5. [Ethical & AI for Good (AI4G) Requirements](#5-ethical--ai-for-good-ai4g-requirements)
6. [Constraints & Assumptions](#6-constraints--assumptions)
7. [Glossary](#7-glossary)

---

## 1. Executive Summary

The **AI-Native Operating System (AIOS) Prototype** is a B.Tech capstone engineering project that demonstrates how Artificial Intelligence can be integrated into the operating system layer as a highly privileged middleware daemon — without compromising the deterministic safety guarantees of the Linux kernel.

Traditional OS schedulers and resource managers are **reactive**: they respond to system events using static, hand-coded heuristics. AIOS introduces a **predictive, context-aware intelligence layer** that continuously monitors system state, queries historical memory via Retrieval-Augmented Generation (RAG), and proposes optimised system configurations — all while remaining strictly bounded by a deterministic validation layer.

> **Design Axiom:**
> *The AI handles probabilistic orchestration. The kernel handles deterministic execution.*
> At no point does the AI model generate or execute raw system calls. All AI outputs are **intents** that must pass through a Deterministic Control Plane before any simulated action occurs.

The prototype targets severely resource-constrained consumer hardware and mitigates compute limitations through a **Hybrid Bounded-AI Architecture**: a local React/Node.js orchestration layer paired with cloud-offloaded LLM inference (Google Colab + ngrok) and cloud-hosted vector memory (MongoDB Atlas).

### Key Innovations

- **AI-as-Middleware**: The AI operates as a privileged user-space daemon — never touching kernel space directly.
- **Hybrid Compute**: Heavy LLM inference is offloaded to a free Colab T4 GPU; local machine handles only orchestration and lightweight embedding.
- **System RAG Memory**: Historical system logs are embedded and stored as vectors, giving the AI genuine long-term contextual memory.
- **Bounded Execution**: A simulated eBPF control plane validates every AI-generated intent before simulated execution.
- **Radical Transparency**: Every AI reasoning step, RAG retrieval, and intent is fully visible to the user in real time.

---

## 2. Hardware & Environment Constraints

### 2.1 Local Hardware Specification

The target development and deployment machine presents a significant compute bottleneck for on-device LLM inference:

| Component | Specification | Constraint Impact |
|---|---|---|
| **Processor** | 11th Gen Intel Core i5-1135G7 @ 2.40 GHz | 4 cores, 8 threads. No AVX-512. Adequate for orchestration, inadequate for 7B+ model inference. |
| **Installed RAM** | 8.00 GB (7.74 GB usable) | **Critical bottleneck.** A quantised 7B model alone requires ~5–6 GB VRAM/RAM. Leaves <2 GB for OS + daemon + browser. |
| **Graphics** | Intel Iris Xe Graphics (128 MB VRAM, UMA) | Shares system RAM. Cannot be used for GPU inference. Rules out local GPU acceleration entirely. |
| **Storage** | 1.14 TB NVMe (186 GB used) | Adequate. Model weights (~1.5 GB for Gemma-2B Q4) and FAISS index stored locally. |
| **NPU / Dedicated GPU** | None | Eliminates on-device neural acceleration. All ML inference must be CPU-only or offloaded. |
| **System Type** | 64-bit, x64-based | Ubuntu 22.04 LTS target for daemon; Windows 11 for development. |
| **Display Input** | No pen/touch | Desktop/keyboard-only interaction model for dashboard. |

**Bottom Line:** Running a capable LLM locally on this hardware would consume the entire usable RAM, leaving nothing for the OS, the Node.js API, the React dashboard, or the Python daemon. A cloud offloading strategy is not optional — it is architecturally mandatory.

---

### 2.2 The Hybrid Compute Topology — Mitigation Strategy

To overcome the local hardware ceiling while preserving a functional AIOS prototype, the following three-tier distributed topology is mandated:

#### Tier 1 — Local Orchestration (Always On)

Runs persistently on the developer's machine. Must stay within a **1.5 GB RAM budget**.

| Service | Technology | RAM Budget |
|---|---|---|
| React Dashboard | Vite + React 18 + TypeScript | ~150 MB (browser tab) |
| Express Management API | Node.js 20 + Express 5 | ~80 MB |
| Python AI Daemon | Python 3.11 + asyncio | ~300 MB |
| Embedding Model (CPU) | `all-MiniLM-L6-v2` via sentence-transformers | ~100 MB |
| FAISS Local Index | `faiss-cpu` library + index file | ~200 MB (50k vectors) |
| **Total** | | **~830 MB** |

#### Tier 2 — Cloud Inference (Kaggle Notebook + ngrok)

Offloads all heavy LLM inference to a free GPU session on Kaggle. Kaggle is chosen over Google Colab for three concrete reasons: **30 GPU hours/week** (vs Colab's ~15–30 unpredictable hours), **background execution** (session survives closing the browser tab), and **ngrok static domain support** (permanent endpoint URL — no re-discovery on restart).

| Component | Detail |
|---|---|
| **Runtime** | Kaggle Free Tier — Nvidia T4 (×1 or ×2) or P100 GPU (16 GB VRAM) |
| **LLM Server** | Ollama serving `gemma:2b-instruct-q4_K_M` (T4 ×1) or `llama3:8b-instruct-q4_K_M` (P100 / T4 ×2) |
| **Tunnel** | ngrok authenticated HTTPS tunnel on port 11434 with **static domain** |
| **URL Discovery** | **Not required** — ngrok static domain is permanent; set once in `.env` and never changes |
| **Session Limit** | Up to 12 hours per session; 30 GPU hours/week quota; background execution keeps session alive without browser tab |
| **Persistent Storage** | 20 GB across sessions — Ollama model weights cached; no re-download on restart |
| **Security** | TLS 1.3 enforced by ngrok; HTTP Basic Auth on all requests; CUDA fully configured via `OLLAMA_GPU_LAYERS=100` |
| **GPU Config** | `CUDA_HOME=/usr/local/cuda`, `OLLAMA_GPU_LAYERS=100`, `OLLAMA_SCHED_SPREAD=1` for dual-T4 spread |

#### Tier 3 — Cloud Memory (MongoDB Atlas)

Offloads long-term vector memory from local RAM to the cloud.

| Component | Detail |
|---|---|
| **Service** | MongoDB Atlas M0 Free Tier |
| **Database** | `aios_memory` → collection: `system_logs` |
| **Vector Index** | Atlas Vector Search on `embedding` field (384 dimensions, cosine similarity) |
| **Storage Limit** | 512 MB (M0 free tier) — sufficient for ~500k log chunks |
| **Cluster Region** | `ap-south-1` (Mumbai) — minimises round-trip latency from India |
| **Latency Target** | P95 query latency < 800ms |

---

### 2.3 Environment Summary Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE (i5, 8GB RAM)                      │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ React Dashboard│◄──│  Express API     │◄──│  Python Daemon   │  │
│  │  :3000        │    │  :5000           │    │  :8765           │  │
│  └──────────────┘    └──────────────────┘    └────────┬─────────┘  │
│                                                        │            │
│  ┌─────────────────────────┐              ┌───────────▼──────────┐ │
│  │  FAISS Local Index      │◄─────────────│  Embedding Service   │ │
│  │  (Recent 1hr context)   │              │  all-MiniLM-L6-v2    │ │
│  └─────────────────────────┘              └──────────────────────┘ │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTPS (TLS 1.3) + Basic Auth
                                 │ Static domain: your-name.ngrok-free.app
                    ┌────────────▼────────────────────────────────────┐
                    │        CLOUD INFERENCE TIER (Kaggle)            │
                    │  T4/P100 GPU → Ollama → ngrok static tunnel     │
                    │  30 GPU hrs/week · Background execution         │
                    │  20GB persistent storage (model weights cached) │
                    └─────────────────────────────────────────────────┘
                                 │ MongoDB Atlas SDK
                    ┌────────────▼────────────────────────────────────┐
                    │           CLOUD MEMORY TIER                     │
                    │  MongoDB Atlas → Vector Search → ap-south-1     │
                    └─────────────────────────────────────────────────┘
```

---

## 3. Functional Requirements

### 3.1 System Monitoring & Telemetry

| Req. ID | Priority | Description |
|---|---|---|
| `FR-MON-01` | **MUST** | The daemon SHALL read mock system log files (`/var/log/syslog`, `kern.log`, `bash_history`) at a configurable polling interval (default: 5 seconds) using `watchdog` file system events. |
| `FR-MON-02` | **MUST** | The daemon SHALL collect simulated CPU utilisation, RAM usage (used/total/percent), and I/O throughput metrics via `psutil` and expose them at `GET /api/metrics`. |
| `FR-MON-03` | **MUST** | All raw telemetry SHALL be sanitised (hostname anonymised, usernames replaced, credentials stripped) before transmission through the ngrok tunnel or ingestion into Atlas. See `ETH-03`. |
| `FR-MON-04` | **SHOULD** | The system SHALL support a mock **kernel panic log injector** (`scripts/inject_panic.py`) that inserts synthetic OOM killer events and driver fault entries for testing the RAG troubleshooting pipeline. |
| `FR-MON-05` | **SHOULD** | The daemon SHALL expose a `/api/health` endpoint reporting the live status of all dependent services: FAISS index, Atlas connection, Colab tunnel reachability, and local Ollama fallback. |

---

### 3.2 RAG Memory Pipeline

| Req. ID | Priority | Description |
|---|---|---|
| `FR-RAG-01` | **MUST** | The ingestion service SHALL chunk incoming log text using `RecursiveCharacterTextSplitter` with `chunk_size=512` tokens and `chunk_overlap=50` tokens, then embed each chunk using `all-MiniLM-L6-v2` (384-dimensional vectors). |
| `FR-RAG-02` | **MUST** | Embedded chunks SHALL be written to both FAISS (local, recent window) and MongoDB Atlas (cloud, persistent history) within 10 seconds of log entry creation. |
| `FR-RAG-03` | **MUST** | On an AI query, the daemon SHALL perform **hybrid retrieval**: FAISS for recent context (last 1 hour) and Atlas for long-term historical context, returning the top-5 chunks from each. |
| `FR-RAG-04` | **MUST** | Retrieved context chunks SHALL be deduplicated by `chunk_id` and re-ranked by combined similarity score, with the top-8 unique chunks injected into the LLM prompt as structured XML blocks. |
| `FR-RAG-05` | **MUST** | Each chunk stored in Atlas SHALL include metadata: `{source_file, timestamp, log_level, severity, host_id (anonymised), chunk_id}`. |
| `FR-RAG-06` | **SHOULD** | The FAISS index SHALL be persisted to `data/faiss_index.bin` after each ingestion batch and reloaded on daemon restart without re-embedding. |

---

### 3.3 AI Daemon & Cloud Inference

| Req. ID | Priority | Description |
|---|---|---|
| `FR-DAE-01` | **MUST** | The Python daemon SHALL forward sanitised, context-enriched prompts to the Kaggle/ngrok Ollama endpoint via `HTTP POST /api/generate` with streaming enabled and a configurable timeout (default: 30 seconds). The endpoint URL is a **static ngrok domain** set once in `.env` — no URL discovery logic required. |
| `FR-DAE-02` | **MUST** | The daemon SHALL implement a **circuit-breaker** pattern: after 3 consecutive failed requests to the Kaggle tunnel (timeout or connection error), it SHALL automatically fall back to the local Ollama instance (`http://localhost:11434`) and display a warning in the dashboard. |
| `FR-DAE-03` | **MUST** | The daemon SHALL parse LLM completions for a structured JSON intent block matching the schema: `{action_type, target_resource, proposed_value, confidence_score, reasoning_summary}`. Malformed outputs SHALL be retried once, then discarded with an error log entry. |
| `FR-DAE-04` | **MUST** | The daemon SHALL expose a WebSocket endpoint at `ws://localhost:5000/stream` for pushing streaming inference tokens and system events to all connected dashboard clients in real time. |
| `FR-DAE-05` | **SHOULD** | The daemon SHALL maintain a session state tracking the current inference backend (cloud/local), the static Kaggle endpoint health, and circuit-breaker status, exposed via `GET /api/session`. |
| `FR-DAE-06` | **REMOVED** | ~~URL auto-discovery from Google Drive~~ — **Not applicable.** The static ngrok domain eliminates the need for URL re-discovery. If the Kaggle session restarts, the same static domain resumes serving; the circuit breaker automatically recovers on the next successful health-check. |

---

### 3.4 Deterministic Control Plane (Bounded Execution)

| Req. ID | Priority | Description |
|---|---|---|
| `FR-BND-01` | **MUST** | Every AI-generated intent object SHALL be passed through the Deterministic Control Plane **before** any simulated execution occurs. Intents that bypass validation SHALL be treated as a critical system error. |
| `FR-BND-02` | **MUST** | The control plane SHALL enforce an **allowlist** of permitted `action_type` values for v1.0: `suggest_renice`, `suggest_swap_adjust`, `suggest_log_rotate`, `suggest_cgroup_limit`. All other action types SHALL be rejected with reason `DISALLOWED_ACTION_TYPE`. |
| `FR-BND-03` | **MUST** | Intents with `confidence_score < 0.75` SHALL be assigned status `PENDING_REVIEW` and SHALL NOT auto-execute under any circumstances, even in simulation. |
| `FR-BND-04` | **MUST** | All control plane decisions SHALL be logged to an immutable append-only SQLite database (`aios_audit.db`) with fields: `timestamp`, `intent_json`, `validation_result`, `rejection_reason`, `execution_status`, `approved_by`, `record_hash` (SHA-256 of the record for tamper evidence). |
| `FR-BND-05` | **MUST** | In the v1.0 prototype, "execution" SHALL be fully simulated: approved intents are written to `data/simulation_state.json` with their proposed changes. No real OS parameters SHALL be modified. |
| `FR-BND-06` | **SHOULD** | The control plane SHALL emit a WebSocket event for each validation decision so the dashboard audit log updates in real time. |

---

### 3.5 Dashboard & Transparency UI

| Req. ID | Priority | Description |
|---|---|---|
| `FR-UI-01` | **MUST** | The React dashboard SHALL display a **Live Reasoning Trace** panel that renders streaming inference tokens word-by-word as they arrive via WebSocket, clearly labelling the inference source (Kaggle GPU / Local Fallback) and displaying end-to-end latency. |
| `FR-UI-02` | **MUST** | The dashboard SHALL display a **RAG Retrieval Viewer** showing all context chunks used for the most recent query: source file, timestamp, similarity score (colour-coded: green ≥ 0.8, amber 0.6–0.79, red < 0.6), and expandable chunk content. |
| `FR-UI-03` | **MUST** | The dashboard SHALL display a **System Metrics Panel** polling `GET /api/metrics` every 2 seconds, showing live CPU%, RAM used/total, FAISS index vector count, Atlas document count, and a RAM warning indicator when usage exceeds 75%. |
| `FR-UI-04` | **MUST** | The dashboard SHALL include an **Audit Log Viewer** showing all intents from `aios_audit.db` with pagination: timestamp, action type, proposed value, confidence score, validation result, execution status. |
| `FR-UI-05` | **MUST** | The Audit Log viewer SHALL display **Approve / Reject buttons** on `PENDING_REVIEW` intents, visible only to users with Operator or Admin role. Approval triggers `PUT /api/intents/:id/approve` and updates the UI in real time. |
| `FR-UI-06` | **MUST** | The dashboard SHALL enforce **Role-Based Access Control** via JWT: `Viewer` (read-only), `Operator` (can approve intents), `Admin` (full configuration access). The active user's role SHALL be displayed in the header. |
| `FR-UI-07` | **SHOULD** | The dashboard SHALL display a **Service Health Bar** showing the live status (✓/✗) of: FAISS index, Atlas connection, Kaggle ngrok tunnel, and local Ollama fallback. |
| `FR-UI-08` | **SHOULD** | The dashboard SHALL include an **Intent Submission Form** allowing Operator/Admin users to manually type a natural-language query and submit it to the daemon pipeline. |

---

## 4. Non-Functional Requirements

### 4.1 Latency Requirements

| NFR ID | Metric | Target | Rationale |
|---|---|---|---|
| `NFR-LAT-01` | End-to-end query latency (first token) | < 3 seconds (Kaggle session warm) | User-facing responsiveness threshold |
| `NFR-LAT-02` | End-to-end query latency (Kaggle session cold start) | < 15 seconds | Model weights cached in Kaggle's 20 GB persistent storage — faster than Colab cold start |
| `NFR-LAT-03` | FAISS retrieval (50k vectors) | < 100 ms | Must not become the retrieval bottleneck |
| `NFR-LAT-04` | Atlas vector search (P95) | < 800 ms | M0 free tier shared compute constraint |
| `NFR-LAT-05` | Embedding generation (512-token chunk) | < 500 ms on local i5 | CPU-only `all-MiniLM-L6-v2` performance target |
| `NFR-LAT-06` | Dashboard metrics panel refresh | ≤ 2 seconds | Live feel without excessive API load |

---

### 4.2 Resource Overhead Requirements

| NFR ID | Constraint | Target |
|---|---|---|
| `NFR-OVH-01` | Combined daemon + FAISS + Node API steady-state RAM | ≤ 1.5 GB |
| `NFR-OVH-02` | Peak RAM during embedding batch (100 chunks) | ≤ 1.8 GB |
| `NFR-OVH-03` | Daemon CPU usage at idle (no active query) | ≤ 5% average |
| `NFR-OVH-04` | FAISS index file size (50k vectors × 384 dims) | ≤ 80 MB |
| `NFR-OVH-05` | Atlas storage consumption | ≤ 400 MB (within M0 512 MB limit) |

---

### 4.3 Modularity & Configurability

| NFR ID | Requirement |
|---|---|
| `NFR-MOD-01` | Each subsystem (ingestion, daemon, API, dashboard) SHALL be independently startable, stoppable, and testable in isolation with a single command. |
| `NFR-MOD-02` | The LLM backend SHALL be fully configurable via a single `.env` file: `OLLAMA_ENDPOINT` (static ngrok domain), `MODEL_NAME`, `FALLBACK_MODEL`, `NGROK_AUTH_TOKEN`, `NGROK_STATIC_DOMAIN`, `ATLAS_URI`. No code changes required to switch models or endpoints. |
| `NFR-MOD-03` | The embedding model SHALL be swappable by changing a single environment variable `EMBEDDING_MODEL`. The FAISS index SHALL be automatically rebuilt on model change. |
| `NFR-MOD-04` | All inter-service communication SHALL use documented, versioned REST or WebSocket contracts so any component can be replaced without breaking others. |

---

### 4.4 Reliability & Graceful Degradation

| NFR ID | Requirement |
|---|---|
| `NFR-REL-01` | If Atlas is unreachable, the system SHALL fall back to FAISS-only retrieval and display a "Cloud Memory Unavailable — Local Only" warning in the dashboard. Query functionality SHALL be preserved. |
| `NFR-REL-02` | If the Kaggle/ngrok tunnel is unreachable (circuit breaker triggered), the system SHALL fall back to local Ollama and display a "Cloud Offline — Local Fallback Active" banner. Since the ngrok domain is static, recovery is automatic once the Kaggle session restarts and the tunnel resumes on the same URL. |
| `NFR-REL-03` | If local Ollama is also unavailable, the system SHALL return a structured error to the dashboard and log the failure. It SHALL NOT crash or hang. |
| `NFR-REL-04` | On daemon restart, the FAISS index SHALL be reloaded from disk (`data/faiss_index.bin`) within 5 seconds without re-embedding. |

---

### 4.5 Security Requirements

| NFR ID | Requirement |
|---|---|
| `NFR-SEC-01` | The ngrok tunnel SHALL require HTTP Basic Authentication (`Authorization: Basic <base64>`) on all requests. Credentials SHALL be loaded from environment variables, never hardcoded in source code. |
| `NFR-SEC-02` | The Express API SHALL use JWT (HS256, 24-hour expiry) for all non-public endpoints. The JWT secret SHALL be loaded from `JWT_SECRET` environment variable. |
| `NFR-SEC-03` | Outbound prompt payloads SHALL be capped at 8 KB to mitigate prompt injection via oversized inputs. |
| `NFR-SEC-04` | The daemon sandbox directory (`/aios-sandbox/`) SHALL be the only filesystem path accessible to simulated execution. All path operations SHALL be validated against this root. |
| `NFR-SEC-05` | The `.env` file SHALL be listed in `.gitignore`. The repository SHALL contain only a `.env.example` with placeholder values. |

---

## 5. Ethical & AI for Good (AI4G) Requirements

This system handles simulated representations of sensitive OS telemetry. The following ethical constraints are **mandatory and non-negotiable** for the v1.0 prototype. They encode the principles of **Responsible AI**, **User Sovereignty**, and **Transparency by Design**.

| ETH ID | Principle | Requirement |
|---|---|---|
| `ETH-01` | **Read-Only Prototype** | The AI daemon SHALL have **zero write access** to the live filesystem outside its designated sandbox directory (`/aios-sandbox/`). All "execution" is simulated. This is enforced at the filesystem level (daemon process runs as a restricted user with no write permissions outside the sandbox). |
| `ETH-02` | **Transparency Mandate** | Every AI decision, RAG retrieval, intent proposal, and control plane validation outcome SHALL be logged and displayed to the user in real time via the dashboard. **Black-box AI outputs are prohibited.** No AI action may occur without a visible, human-readable audit trail entry. |
| `ETH-03` | **Data Sanitisation Before Transmission** | Before any system telemetry is transmitted through the ngrok tunnel or stored in Atlas, a mandatory sanitisation filter SHALL strip or mask: (a) real hostnames, (b) usernames, (c) IP addresses, (d) strings matching common secret patterns (API keys, JWT tokens, AWS credentials, database URIs). |
| `ETH-04` | **Human-in-the-Loop** | **No AI intent SHALL auto-execute without explicit human approval** (Operator role or above) via the dashboard. This applies even to low-risk `suggest_log_rotate` actions. The human approval gate cannot be bypassed by any code path. |
| `ETH-05` | **Confidence Threshold Guardrail** | Responses with `confidence_score < 0.75` SHALL be marked **⚠ LOW CONFIDENCE** in the UI and quarantined with status `PENDING_REVIEW`. They SHALL NOT be surfaced as actionable intents until a human reviews and approves them. |
| `ETH-06` | **Explainability** | The dashboard SHALL display the retrieved RAG context chunks that informed each AI response, enabling the user to verify the factual basis of every suggestion. The AI SHALL NOT make suggestions that cannot be traced back to specific retrieved evidence. |
| `ETH-07` | **Data Residency & Privacy** | No real user PII SHALL be stored in MongoDB Atlas. Atlas collections SHALL contain only mock/synthetic log data or anonymised embeddings. The Atlas cluster SHALL be provisioned in a region consistent with applicable data protection regulations (ap-south-1 for India-based development). |
| `ETH-08` | **Fail-Safe Default** | In any ambiguous or error state (parse failure, schema violation, network timeout), the system SHALL default to **inaction** — logging the error and notifying the user — rather than attempting a best-effort execution that could produce unintended outcomes. |

---

## 6. Constraints & Assumptions

- **Colab Session Limit:** Google Colab free tier provides approximately 4–12 hours of T4 GPU runtime per session. The daemon must handle session expiry gracefully via the circuit-breaker and fallback mechanism.
- **Atlas Free Tier:** MongoDB Atlas M0 is limited to 512 MB storage and shared compute. Query latency may vary; the system targets P95 < 800ms but cannot guarantee this under Atlas load.
- **ngrok Free Tier:** ngrok free tier allows one active tunnel with a rotating public URL per session. The daemon must poll for URL changes on each Colab restart.
- **Mock Data Only:** The v1.0 prototype uses exclusively synthetic/mock system data. No production kernel interfaces (eBPF, `/proc` writes, `sysctl`) are exercised.
- **Embedding Model Offline:** `all-MiniLM-L6-v2` must be downloaded once to local disk via `sentence-transformers`. The daemon requires no internet access for embedding at inference time.
- **Linux Target:** The daemon is designed for Ubuntu 22.04 LTS. Windows Subsystem for Linux (WSL2) is acceptable for development but not recommended for production testing due to `psutil` limitations on WSL.
- **Single-User Prototype:** The v1.0 system assumes a single concurrent user. Multi-user session management and concurrent intent approval are out of scope.

---

## 7. Glossary

| Term | Definition |
|---|---|
| **AIOS** | AI-Native Operating System — an OS architecture where AI acts as an intelligent middleware layer. |
| **Bounded Execution** | The design pattern where AI outputs (intents) are validated by a deterministic layer before any execution. |
| **Circuit Breaker** | A resilience pattern that stops sending requests to a failing service after a threshold of failures, routing to a fallback instead. |
| **eBPF** | Extended Berkeley Packet Filter — a Linux kernel technology for running sandboxed programs in kernel space. Used in simulation in v1.0. |
| **FAISS** | Facebook AI Similarity Search — a library for efficient similarity search over dense vectors. |
| **Intent** | A structured JSON object produced by the LLM describing a proposed system action: `{action_type, target_resource, proposed_value, confidence_score}`. |
| **ngrok** | A tunnelling service that creates a secure public HTTPS URL pointing to a local or remote port. |
| **Ollama** | An open-source tool for running quantised LLMs locally via a REST API. |
| **RAG** | Retrieval-Augmented Generation — augmenting an LLM prompt with relevant documents retrieved from a vector database. |
| **UMA** | Unified Memory Architecture — GPU shares system RAM rather than having dedicated VRAM. |
| **Vector Search** | Semantic similarity search over high-dimensional embedding vectors, as opposed to keyword-based full-text search. |

---

*Document prepared by **Anand Raj** (anand.ar1806@gmail.com) — June 2026*
