# AIOS Test Suite Results & Kaggle Benchmarks Reference

This document provides a detailed breakdown of the AI-Native Operating System (AIOS) test suite verification results and describes the integration of the Kaggle Benchmarks LLM evaluation framework.

---

## 🧪 Part 1: Pytest Suite Execution & Module Verification

The core Python daemon and middleware logic are validated using a rigorous automated test suite. The test suite verifies component isolation, data sanitisation, hybrid retrieval accuracy, and the strict safety boundaries enforced by the Deterministic Control Plane.

### Execution Summary
* **Command**: `pytest`
* **Coverage**: Core components (Telemetry logs, Sanitiser, FAISS, MongoDB, Control Plane, Inference Client)
* **Results**: **56 passed, 0 failed, 3 warnings**
* **Duration**: **48.53 seconds**

```bash
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/anand_raj/AIOS-Prototype_Rag
plugins: asyncio-1.4.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False
collected 56 items

tests/test_atlas_store.py ....                                           [  7%]
tests/test_cached_mongodb.py ...                                         [ 12%]
tests/test_control_plane.py ........                                     [ 26%]
tests/test_embedder.py .......                                           [ 39%]
tests/test_faiss_store.py .....                                          [ 48%]
tests/test_inference_client.py ......                                    [ 58%]
tests/test_prompt_builder.py ......                                      [ 69%]
tests/test_retriever.py .....                                            [ 78%]
tests/test_sanitiser.py ............                                     [100%]

======================= 56 passed, 3 warnings in 48.53s ========================
```

---

### Module-by-Module Verification Details

#### 1. Data Sanitisation & Egress Safety (`test_sanitiser.py` — 12 Tests Passed)
* **Objective**: Verifies that no sensitive host system details (e.g., passwords, secret keys, user credentials, SSH keys, or private system IDs) leave the WSL host environment.
* **Verified Features**:
  * Scans telemetry data using 10 regex-based entity extraction rules.
  * Replaces credentials and private identifiers with neutral tokens (e.g., `<ANONYMISED_SECRET>`).
  * Asserts that only sanitised log chunks are forwarded to the vector databases and LLM prompts.

#### 2. Deterministic Control Plane (`test_control_plane.py` — 8 Tests Passed)
* **Objective**: Assures that the AI agent can only propose optimizations, and that zero modifications are made to the host environment without strict deterministic check gates.
* **Verified Features**:
  * **Null Checking**: Rejects malformed, incomplete, or corrupted JSON outputs.
  * **Allowlist Enforcement**: Checks that proposed intents match exactly the allowed commands (`suggest_renice`, `suggest_cgroup_limit`, `suggest_log_rotate`).
  * **Confidence Level Gate**: Auto-rejects suggestions below the configurable safety threshold (e.g., 80% confidence).
  * **Human-in-the-Loop Gate**: Verifies that final authorization states wait for explicit manual operator approval.

#### 3. FAISS Local Vector Store (`test_faiss_store.py` — 5 Tests Passed)
* **Objective**: Validates the local search index storing historical system error-resolution configurations.
* **Verified Features**:
  * Dynamic creation of the FAISS FlatL2 index.
  * Correct matching of high-dimensionality text embeddings.
  * Score distance threshold filters to filter out irrelevant historical context.

#### 4. Prompt Builder (`test_prompt_builder.py` — 6 Tests Passed)
* **Objective**: Assures correct assembly of system prompts containing telemetry, RAG matching context, and system instructions.
* **Verified Features**:
  * Correct injection of sanitised logs.
  * Prevention of prompt injection attempts inside telemetry payloads.
  * Rigid enforcement of JSON format formatting rules in system instructions.

#### 5. Local LLM Inference Client (`test_inference_client.py` — 6 Tests Passed)
* **Objective**: Validates connection stability and fail-safe handling when executing queries against local Ollama.
* **Verified Features**:
  * Enforces a `3-second connect timeout` and `10-second read timeout` to prevent hanging system tasks.
  * Handles local connection errors or container outages gracefully without throwing uncaught middleware crashes.
  * Parses LLM outputs into structured JavaScript objects.

#### 6. Hybrid Retriever (`test_retriever.py` — 5 Tests Passed)
* **Objective**: Evaluates the score fusion logic combining local and cloud indices.
* **Verified Features**:
  * Fetches candidate documents from local FAISS and cloud MongoDB Atlas.
  * Combines vector scores using weighted score fusion coefficients.
  * Filters and groups final RAG candidate lists to prevent prompt cluttering.

#### 7. Cloud Memory Store (`test_atlas_store.py` — 4 Tests Passed)
* **Objective**: Validates indexing and querying against MongoDB Atlas cloud databases.
* **Verified Features**:
  * Collection insertion, updates, and vector query parsing.

#### 8. DB Caching (`test_cached_mongodb.py` — 3 Tests Passed)
* **Objective**: Confirms that MongoDB query result caching performs correctly to minimize API call latencies.
* **Verified Features**:
  * Cache hit returns matching vector context immediately (< 2ms).
  * Cache invalidation operates correctly when local systems write new diagnostic remediations.

---

## 🏆 Part 2: Kaggle Benchmarks LLM Evaluation Integration

To evaluate the reasoning accuracy and reliability of the AIOS prompt engine, this project integrates Google's **Kaggle Benchmarks (`kaggle-benchmarks`)** library. This allows us to push evaluation tasks to Kaggle’s hosted leaderboards and score model responses against deterministic expectations.

### 1. Task Definition (`benchmark_test.py`)
Evaluation tasks are defined using the `@kbench.task` decorator:
```python
import kaggle_benchmarks as kbench

@kbench.task(name="simple-test", description="Simple RAG system sanity check", version=1)
def simple_test(llm) -> None:
    # prompt the model under test (llm)
    response = llm.prompt("Hello! Are you ready?")
    
    # Assert criteria and log results to leaderboard
    kbench.assertions.assert_true(
        len(response) > 0, expectation="Response is not empty"
    )
```

### 2. Supported Return Annotations
The return type of the task function controls how results are rendered on the Kaggle Benchmarks leaderboard:

| Return Type | leaderboards Formatting |
|---|---|
| `None` / omitted | Pass/Fail graded solely by assertions |
| `-> bool` | Binary pass/fail score |
| `-> int` / `-> float` | Direct numerical score |
| `-> tuple[int, int]` | Score count (passed, total) |
| `-> dict` | Structured telemetry result dictionary |

---

### 3. Programmatic Push & Run (`upload_benchmark.py`)
We automate task management using the programmatic Python API client. The `upload_benchmark.py` script authenticates with Kaggle and runs tasks in Kaggle's evaluation environment:

```python
from kaggle.api.kaggle_api_extended import KaggleApi

def upload_and_run_benchmark():
    # 1. Authenticate with Kaggle credentials
    api = KaggleApi()
    api.authenticate()

    task_slug = "simple-test"
    task_file = "benchmark_test.py"

    # 2. Push task source code
    print(f"Uploading '{task_file}' as task '{task_slug}'...")
    api.benchmarks_tasks_push_cli(
        task=task_slug,
        file=task_file,
        wait=True
    )

    # 3. Trigger remote execution against benchmark models
    print(f"Triggering execution of '{task_slug}' on Kaggle Benchmarks...")
    api.benchmarks_tasks_run_cli(
        task=task_slug,
        wait=True
    )
    print("✅ Success! The benchmark run has completed. Results are on Kaggle.")
```

### 4. Advanced Evaluation: Judge-Based Assessment
For complex, multi-dimensional prompts (such as verifying if the LLM reasoner correctly identified cgroups configuration limits), we use a secondary **Judge LLM** to evaluate the primary model's output against criteria:

```python
# Conduct an automated judge assessment
report = kbench.assertions.assess_response_with_judge(
    criteria=(
        "Does the response identify memory threshold issues?",
        "Does the response suggest cgroups limit commands?"
    ),
    response_text=llm_response,
    judge_llm=kbench.judge_llm
)

# Apply assertions based on the judge's assessment report
for result in report.results:
    kbench.assertions.assert_true(
        result.passed, 
        expectation=f"Judge check - {result.criterion}: {result.reason}"
    )
```
This ensures that the AIOS optimization prompts can be mathematically scored for logical correctness before deployment.
