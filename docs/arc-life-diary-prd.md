# Product Requirements Document (PRD): arc-life-diary

## 1. Overview & Problem Statement
The user maintains a 6-year personal archive composed of discrete Markdown entries (`YYYY-MM-DD.md`) averaging ~500 words each. Entries are bilingual (written in English, Japanese, and occasional code-switching) and non-linear (recent entries frequently embed unstructured recollections of events from years prior without explicit dates).

Standard chronological skimming and keyword matching (`grep`, BM25) fail to answer thematic, retrospective questions such as *"How did my past self react to high-stress situations over time?"* 

The goal of this system is to provide a single-command CLI tool that semantically retrieves relevant life events regardless of the language written, reconstructs an objective developmental progression over time, and presents direct file citations for personal fact-checking.

**Key Design Mandate:** The codebase must adhere to strict modularity and separation of concerns. All external AI dependencies (embeddings and LLM generation) must be decoupled behind abstract interface boundaries so that alternative providers (e.g., local Ollama, OpenAI, Anthropic, local ONNX) can be swapped in without modifying database logic, ingestion code, or CLI flows.

---

## 2. Goals & Non-Goals

### Goals
* **Modular Provider Interfaces:** Use Python `Protocol` or `ABC` interfaces for embedding models and text generation to ensure zero vendor lock-in.
* **Cross-Lingual Retrieval:** Querying in English must reliably retrieve entries written in Japanese, English, or mixed languages.
* **Non-Linear Synthesis:** Differentiate between *entry creation date* (file timestamp) and *narrative memory date* (when the event actually took place) through LLM context synthesis.
* **Developmental Arc Analysis:** Produce structured, analytical reflections showing internal shift and coping mechanisms across time, rather than a flat bulleted summary.
* **Verifiable Grounding:** Every insight must link directly to the primary Markdown files with distance metrics and context snippets for auditability.
* **Low-Overhead CLI Execution:** Single-shot command-line interface with minimal runtime dependencies and local caching.

### Non-Goals
* **No Stateful Multi-Turn Chat:** Will not support conversational state tracking, sessions, or ongoing agent loops.
* **No Cloud Hosting / SaaS:** The vector store and operational files remain entirely local.
* **No File Mutation:** The system will never write, reformat, or alter the source Markdown files.
* **No Fragmented Chunking:** Entries will not be sliced into arbitrary 200-word sliding windows, preserving the full narrative integrity of each day's entry.

---

## 3. User Personas & Core Use Case

### Primary Persona
* **The Long-Term Self-Chronicler:** An introspective engineer who records daily vignettes and past recollections in raw text, wanting to identify recurring emotional blind spots, evolving career philosophies, and behavioral patterns across multiple years.

### User Journey
1. User writes an entry into their local vault (`entries/2026-10-31.md`).
2. User runs `sync` to update the local vector cache for any new or modified entries.
3. User runs a thematic query via terminal:  
   `diary "How did my reaction to family arguments evolve?"`
4. The system outputs:
   * A synthesized narrative written in English, tracing chronological attitude shifts.
   * A list of cited Markdown source files with distance scores and opening snippets.
5. User reads the analysis, verifies the claims against their original notes, and closes the terminal.

---

## 4. Modular System Architecture

To avoid tightly coupling the application to the Gemini API, the system is separated into distinct layers with clear dependency boundaries:

```text
┌────────────────────────────────────────────────────────┐
│                   CLI / Runner Layer                   │
│                     (cli.py / main)                    │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐       ┌────────────────────────┐
│ Storage & Ingestion   │       │ Introspection Service  │
│ (store.py, parser.py) │       │ (service.py)           │
└───────────┬───────────┘       └───────────┬────────────┘
            │                               │
            │           ┌───────────────────┘
            ▼           ▼
┌────────────────────────────────────────────────────────┐
│               Abstract Provider Interfaces             │
│               - BaseEmbeddingModel                     │
│               - BaseLLMClient                          │
└───────────────────────────┬────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          ▼                                   ▼
┌──────────────────┐                ┌──────────────────┐
│ Gemini Provider  │                │ Alternative/Mock │
│ (gemini.py)      │                │ (ollama.py, etc) │
└──────────────────┘                └──────────────────┘
```

### Module Responsibilities

1. **`interfaces.py`**: Declares abstract contracts for `BaseEmbeddingModel` and `BaseLLMClient`. Does not import any vendor SDK.
2. **`store.py`**: Manages the local SQLite database and `sqlite-vec` virtual tables. Handles file hashing, caching, and raw KNN vector math. Completely agnostic of which embedding model produced the vectors.
3. **`parser.py`**: Reads raw `.md` files, extracts frontmatter (date/title), and cleans text payloads.
4. **`providers/gemini.py`**: Concrete implementation of `BaseEmbeddingModel` (using `text-embedding-004`) and `BaseLLMClient` (using `gemini-2.5-flash`).
5. **`service.py`**: Core orchestration. Coordinates embedding, querying SQLite, structuring prompts, and invoking the LLM. Depends solely on abstract interfaces via dependency injection.
6. **`cli.py`**: Parses terminal commands (`sync`, query), instantiates the chosen provider implementations, and prints formatted output.

---

## 5. Interface Specifications

### 5.1 Embedding Interface (`interfaces.py`)
```python
from typing import List, Protocol

class BaseEmbeddingModel(Protocol):
    """Abstract interface for dense vector embedding generators."""
    
    @property
    def dimensions(self) -> int:
        """Vector dimensionality expected by SQLite table (e.g. 768)."""
        ...

    def embed_document(self, text: str) -> List[float]:
        """Embeds a single document for ingestion."""
        ...

    def embed_query(self, text: str) -> List[float]:
        """Embeds a user query string for vector search."""
        ...
```

### 5.2 LLM Synthesis Interface (`interfaces.py`)
```python
from typing import Protocol

class BaseLLMClient(Protocol):
    """Abstract interface for text synthesis and introspection models."""
    
    def generate_synthesis(self, prompt: str, system_instruction: str) -> str:
        """Takes context and user question and returns formatted textual analysis."""
        ...
```

---

## 6. Functional Requirements

### FR-1: Modular Provider Swapability
* The core application logic (`service.py` and `store.py`) must never import `google.genai` directly.
* Changing providers (e.g., from Gemini to a local Ollama instance or OpenAI) must only require implementing `BaseEmbeddingModel` and `BaseLLMClient` in a new file under `providers/` and passing it to the service.

### FR-2: Entry Ingestion & Change Detection
* **Source of Truth:** Directory containing flat `.md` files named according to `YYYY-MM-DD.md`.
* **Metadata Extraction:** Parse optional YAML frontmatter (`title`, `date`). If absent, default to the filename stem.
* **Incremental Synchronization:**
  * System computes a SHA-256 hash of each file's contents.
  * Compare against stored hashes in SQLite.
  * Only call `embed_document()` on new or modified files ($O(1)$ redundant API calls).

### FR-3: Multilingual Semantic Representation & Storage
* **Embeddings:** Support cross-lingual embeddings that align Japanese, English, and Chinese concepts into unified vector coordinates.
* **Storage Primitives:** Store vectors locally in SQLite using `sqlite-vec` (`vec0` virtual table with cosine distance). Dimensionality dynamically adapts to `BaseEmbeddingModel.dimensions`.

### FR-4: Retrieval Pipeline
* **Query Embedding:** User query is converted to a vector using `BaseEmbeddingModel.embed_query()`.
* **K-Nearest Neighbors:** Execute cosine distance search in SQLite with default limit $k = 5$.
* **Context Payload:** Fetch matching file dates, titles, full bodies, and distance metrics.

### FR-5: Synthesis & Output Generation
* **Synthesis Engine:** Any engine implementing `BaseLLMClient`.
* **Generation Constraints:**
  * System prompt instructs the model to distinguish past memories from entry pen-dates.
  * Output strictly in English regardless of source language.
  * Structure output into two explicit sections:
    1. **Analysis & Progression:** Thoughtful narrative detailing shifts in coping mechanisms and mindset.
    2. **Relevant Sources (Fact-Check):** Metadata list containing filename, date, title, vector distance, and preview.

---

## 7. Non-Functional Requirements

* **Performance & Latency:**
  * Incremental `sync` on an unchanged archive must finish in $<200\text{ ms}$.
  * Retrieval + generation end-to-end turnaround should take $<3.0\text{ seconds}$ on standard broadband.
* **Data Sovereignty & Privacy:**
  * Journal files and vector embeddings reside on local disk (`diary.db`).
  * Cloud interaction is restricted to transient API calls for embedding and generation.
* **Reliability & Stateless Recovery:**
  * Deleting `diary.db` and running `sync` must rebuild the entire index deterministically.
* **Loose Coupling:**
  * Codebase adheres to the Dependency Inversion Principle: High-level modules do not depend on low-level modules; both depend on abstractions.

---

## 8. CLI Interface & Error Handling

### Command Specifications
```bash
# Ingests and updates index incrementally
diary sync

# Executes query, prints analysis and citations
diary "<query-string>"

# Optional flag to adjust retrieval count
diary "<query-string>" --top-k 8
```

### Error Conditions
* **Provider Auth Missing:** If environment variables or credentials required by the configured provider are missing, exit gracefully with a specific error message.
* **Empty Archive:** Warn the user and exit cleanly if the entries directory contains no `.md` files.
* **Dimension Mismatch:** If an existing `diary.db` was built with 768 dimensions and the user switches to a 384-dimension embedder, the database layer must raise a clear migration/rebuild warning.

---

## 9. Success Metrics & Evaluation

| Metric | Target | Verification Method |
| :--- | :--- | :--- |
| **Provider Decoupling** | Zero core edits | Switching to a new provider requires adding 1 class and modifying 0 lines of database/ingestion code. |
| **Cross-Lingual Recall** | 100% | Querying in English retrieves relevant entries written solely in Japanese in the top 3 results. |
| **Temporal Disentanglement** | > 85% accuracy | Model correctly identifies an event as occurring in the past when recounted inside a newer file. |
| **API Call Efficiency** | Zero redundant calls | Consecutive `sync` runs without file modifications make 0 external embedding calls. |