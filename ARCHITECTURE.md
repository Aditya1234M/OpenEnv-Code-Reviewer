# Project Architecture Diagram

```mermaid
graph TD
    A[Agent] -->|POST /reset| B[FastAPI Server]
    A -->|GET /state| B
    A -->|POST /step (action)| B
    B --> C[OpenEnv Runtime]
    C --> D[Task Dataset JSONL]
    C --> E[Deterministic Scorer]
    E -->|reward + metrics| A
    F[Optional OpenAI Analyzer] -. baseline tooling .-> C
```

## Description
- **FastAPI Server**: Exposes OpenEnv-compatible `reset`, `state`, and `step` endpoints.
- **OpenEnv Runtime**: Loads one static task per episode and tracks step state.
- **Task Dataset**: Provides PR diff, context, and planted ground truth labels.
- **Deterministic Scorer**: Computes reward from true positives, false positives, and misses.
- **Optional OpenAI Analyzer**: Can be used for baseline agent experiments, not for judging.
