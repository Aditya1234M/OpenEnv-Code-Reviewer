# OpenEnv Code Review Environment

This project is now an OpenEnv-style reinforcement learning environment for code review.

An external AI agent receives a static PR task (diff + context), submits a review as an action, and gets a reward based on planted ground-truth issues.

## What Changed

- Added GitHub Actions integration endpoint for live PR grading.
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
OPENAI_BASE_URL=https://api.openai.com/v1
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
4. `POST /grade` (one-shot reset + step + grading report)
5. `POST /github/pr-review-grade` (GitHub Actions friendly with markdown summary)

These first three endpoints (`/reset`, `/state`, `/step`) are the core OpenEnv interaction loop required by evaluators.

## GitHub Actions Integration

Use GitHub Actions in the target repository to call this service on PR events.

1. Add repo secret `GRADER_URL` pointing to your deployed server URL.
2. Trigger workflow on `pull_request` (`opened`, `synchronize`, `reopened`).
3. Build or generate agent action JSON in workflow.
4. Call `POST /github/pr-review-grade`.
5. Post `summary_markdown` to PR comment or check summary.

See template: `docs/pr-grader-workflow.yml`.

## Evaluator Step-by-Step Guide

Use this section to evaluate the project end-to-end without author assistance.

### A) Start the Grader Service

1. Clone the repository and install dependencies.
2. Create `.env` based on `.env.example`.
3. Run the API service:

```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
```

4. Verify health:

```bash
curl http://127.0.0.1:8000/health
```

Expected: JSON with `status: ok`.

### B) Expose Service Publicly (if using GitHub Actions from another repo)

If evaluating from an external repo, expose local service (for example via ngrok):

```bash
ngrok http 8000
```

Copy the HTTPS public URL; this becomes `GRADER_URL`.

### C) Configure Target Repository Secrets

In target repo: **Settings -> Secrets and variables -> Actions -> Repository secrets**

Add:

1. `GRADER_URL` = public base URL of grader service (`https://...`)
2. `OPENAI_API_KEY` = model provider key used by workflow to generate actions
3. Optional `OPENAI_BASE_URL` = provider base URL (for OpenRouter/OpenAI-compatible endpoints)
4. Optional `OPENAI_MODEL` = override model name (defaults to `gpt-4.1-mini`)

### D) Add Workflow in Target Repository

1. Create file: `.github/workflows/pr-grader.yml`
2. Paste workflow template from `docs/pr-grader-workflow.yml`
3. Commit to default branch

### E) Trigger Evaluation

1. Open a PR in target repo (or push a new commit to existing PR)
2. Go to **Actions** tab and open `PR Grader` run
3. Wait until run completes

### F) Verify Successful Evaluation

Check all of the following:

1. Workflow run status is green
2. PR Conversation tab contains bot grading comment
3. Comment includes grade, explanation, and score breakdown
4. Grader service logs show request to `/github/pr-review-grade`

### G) Troubleshooting

1. `httpx.UnsupportedProtocol` or invalid URL errors:
  Ensure secrets include full protocol (`https://...`) for `GRADER_URL` and optional `OPENAI_BASE_URL`.
2. No workflow run visible:
  Ensure workflow is in `.github/workflows/pr-grader.yml` on default branch and trigger types include pull_request events.
3. No PR comment:
  Ensure workflow permissions include `pull-requests: write`.
4. ngrok URL works in browser but fails in CI:
  Keep `ngrok-skip-browser-warning` header in workflow request.

## Live UI Output

- Open `http://127.0.0.1:8000/` for a built-in grading UI.
- Paste agent action JSON and get visible score breakdown, grade, and report.

## GitHub Actions Integration

Use `POST /github/pr-review-grade` with:

```json
{
  "seed": 123,
  "pr_url": "https://github.com/org/repo/pull/123",
  "action": {
    "overall_decision": "request_changes",
    "issues": [
      {"file": "auth.py", "line": 5, "category": "security", "severity": "critical", "description": "..."}
    ]
  }
}
```

The response includes `summary_markdown` / `markdown_report` you can publish to PR checks.

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

### Baseline Evaluation (All Tasks)

Run deterministic baseline evaluation across the full dataset:

```bash
python scripts/baseline_eval.py
```

For full JSON output (including per-task details):

```bash
python scripts/baseline_eval.py --json
```

### Docker Quickstart

Build image:

```bash
docker build -t openenv-code-review:latest .
```

Run container with env file:

```bash
docker run --rm -p 8000:8000 --env-file .env openenv-code-review:latest
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Hugging Face Dataset

- Dataset file used by this environment: `data/pr_tasks.jsonl`
- Publish URL: `https://huggingface.co/datasets/<your-username>/<your-dataset-name>`

Quick publish steps:

1. Create a new dataset repo on Hugging Face.
2. Upload `data/pr_tasks.jsonl`.
3. Replace the placeholder URL above with your final dataset link.

If deploying to Hugging Face Spaces and you see a configuration error, follow:

- `docs/HF_SPACE_QUICK_FIX.md`

## License

MIT
