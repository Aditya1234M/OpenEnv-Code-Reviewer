# OpenEnv Code Review Environment

This project is now an OpenEnv-style reinforcement learning environment for code review.

An external AI agent receives a static PR task (diff + context), submits a review as an action, and gets a reward based on planted ground-truth issues.

## What Changed

- Removed webhook-first runtime from the active execution path.
- Removed Nova Act and Bedrock from the active model path.
- Added OpenAI-backed analyzer utilities.
- Added deterministic OpenEnv environment API:
  - reset(seed)
  - state()
  - step(action)

## Required Hackathon Stack

- Python: environment and scorer implementation
- GitHub: source historical PRs and diffs for dataset generation
- Hugging Face: host benchmark dataset and optional baseline artifacts
- Google Colab: provide reproducible training/eval notebook
- OpenEnv framework: expose reset/step/state interaction pattern
- Docker: package environment server + dataset for reproducibility

## Project Structure

```
src/
├── config.py            # Env vars and runtime settings
├── analyzer.py          # OpenAI analysis utility (optional baseline helper)
├── openenv_env.py       # Core environment with reset/step/state
├── pipeline.py          # Thin wrappers around environment operations
└── server.py            # FastAPI API for /reset /state /step

data/
└── pr_tasks.jsonl       # Static benchmark tasks with ground truth labels
```

## Task Format (JSONL)

Each line in `data/pr_tasks.jsonl` must include:

- `task_id`
- `title`
- `description`
- `diff`
- `ground_truth.issues[]`
- Optional `ground_truth.expected_decision`
- Optional `context_files[]`

## Action Format

Agents submit JSON actions like:

```json
{
  "overall_decision": "request_changes",
  "issues": [
    {
      "file": "auth.py",
      "line": 42,
      "category": "security",
      "severity": "critical",
      "description": "Token bypass allows unauthorized access"
    }
  ]
}
```

## Reward

Reward is deterministic and based on matching predicted issues to planted truth:

- True positives increase score
- Severity matches add bonus
- False positives penalize score
- Missed issues penalize score
- Missed critical issues add extra penalty
- Correct overall decision adds small bonus

Final reward is normalized and clipped to [-1, 1].

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Create `.env` with at least:

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4.1-mini
OPENENV_DATASET_PATH=data/pr_tasks.jsonl
OPENENV_MAX_STEPS=1
```

## Run API Server

```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
```

## OpenEnv HTTP API

1. `POST /reset`
2. `GET /state`
3. `POST /step`

Example `POST /step` body:

```json
{
  "action": {
    "overall_decision": "request_changes",
    "issues": [
      {"file": "utils.py", "line": 12, "category": "bug", "severity": "high", "description": "..."}
    ]
  }
}
```

## Docker and Colab

- Docker: package this API and dataset for deterministic scoring.
- Colab: load tasks, run a baseline agent loop, and report average reward.

## License

MIT
