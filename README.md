# 🤖 Autonomous Open Source Maintainer

An AI-powered agent that automatically reviews Pull Requests on GitHub. It attempts to use **Amazon Nova Act** for PR browsing when Nova Act authentication is configured, falls back to the **GitHub API** for PR metadata when it is not, and uses **Amazon Nova via Bedrock** to analyze the codebase before posting actionable feedback on the PR.

## The Problem

Open-source maintainers are drowning. Popular projects get hundreds of PRs and issues. Most are low-quality, out-of-date, or missing tests. Human maintainers burn out trying to keep up.

## How It Works

```
  GitHub PR Event
        │
        ▼
  ┌─────────────┐
  │  Webhook    │  ← FastAPI server receives PR events
  │  Server     │
  └──────┬──────┘
         │
         ▼
       ┌──────────────────────────────┐
       │  Nova Act (optional)         │  ← Uses Nova Act only if auth is configured
       │  GitHub API fallback         │     otherwise falls back to GitHub API
       │  PR Browser                  │
       └──────────────┬───────────────┘
         │
         ▼
  ┌─────────────┐
  │  Test Runner│  ← Clones repo, auto-detects framework, runs tests
  │  (Sandbox)  │
  └──────┬──────┘
         │
         ▼
       ┌──────────────────────────────┐
       │  Bedrock Analyzer            │  ← Prefers Nova Premier
       │  Nova Premier -> Nova Pro    │     Falls back to Nova Pro when needed
       └──────────────┬───────────────┘
         │
         ▼
  ┌─────────────┐
  │  GitHub     │  ← Posts review with inline comments & fix suggestions
  │  Reviewer   │
  └─────────────┘
```

## Project Structure

```
src/
├── __init__.py          # Package init
├── config.py            # Environment-based configuration
├── server.py            # FastAPI webhook endpoint
├── pipeline.py          # Orchestrates the full review flow
├── pr_browser.py        # Nova Act — browses and extracts PR details
├── analyzer.py          # Nova 2 Pro — deep codebase analysis
├── test_runner.py       # Clones repos, detects frameworks, runs tests
└── reviewer.py          # Posts structured reviews back to GitHub
```

## Setup

### 1. Prerequisites

- Python 3.10+
- An AWS account with Bedrock access
- A GitHub Personal Access Token with repository write access
- Optional: Nova Act API key or Nova Act workflow-based AWS setup

### 2. Install

```bash
# Clone this repo
git clone https://github.com/Aditya1234M/Autonomous-Open-Source-Maintainer.git
cd Autonomous-Open-Source-Maintainer

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your actual keys
```

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope or fine-grained `issues:write` + `pull_requests:write` |
| `GITHUB_WEBHOOK_SECRET` | Secret for verifying webhook payloads |
| `AWS_ACCESS_KEY_ID` | AWS credentials for Bedrock |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for Bedrock |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `BEDROCK_MODEL_ID` | Optional model override. Defaults to `amazon.nova-premier-v1:0` |
| `BEDROCK_INFERENCE_PROFILE_ID` | Optional Bedrock inference profile ID or ARN for Nova Premier |

`.env` is intentionally excluded from git via `.gitignore`. Keep real credentials only in your local `.env` file and never commit them.

### 4. Authentication Notes

- **GitHub posting permissions:** the bot needs `issues:write` and `pull_requests:write` to post results back to a PR.
- **Nova Act:** this repo does not currently ship a configured Nova Act workflow definition. If Nova Act auth is not configured, the bot automatically falls back to GitHub API metadata collection.
- **Bedrock:** the analyzer prefers `amazon.nova-premier-v1:0`. If Nova Premier cannot be invoked without an inference profile, it falls back to `amazon.nova-pro-v1:0`.

### 5. Actual Nova Usage In This Repo

- **Nova Act:** optional. No workflow definition is committed in this repository today.
- **PR metadata path used by default:** GitHub API fallback when Nova Act is not configured.
- **Primary Bedrock model:** `amazon.nova-premier-v1:0`
- **Automatic fallback Bedrock model:** `amazon.nova-pro-v1:0`
- **Inference profile support:** optional via `BEDROCK_INFERENCE_PROFILE_ID`

### 6. Run

```bash
# Start the webhook server
uvicorn src.server:app --host 0.0.0.0 --port 8000

# For development with auto-reload
uvicorn src.server:app --reload --port 8000
```

### 7. Set Up GitHub Webhook

1. Go to your repo → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL:** `https://your-server.com/webhook`
3. **Content type:** `application/json`
4. **Secret:** Same value as `GITHUB_WEBHOOK_SECRET` in `.env`
5. **Events:** Select "Pull requests"

> **Tip:** For local development, use [ngrok](https://ngrok.com/) or [smee.io](https://smee.io/) to expose your local server.

### 8. Trigger A Review

1. Open a pull request in the target repository.
2. Push another commit to that PR branch, or edit a file from the GitHub UI.
3. GitHub sends a `pull_request` webhook (`opened`, `synchronize`, or `reopened`).
4. The bot clones the repo, inspects the PR, analyzes the codebase, and posts a review or PR comment.

If you are testing on your own PR, GitHub may reject `REQUEST_CHANGES` as a review event. In that case this project automatically posts a normal PR comment instead.

## Supported Languages

The test runner auto-detects and runs tests for:

| Language | Detection | Command |
|---|---|---|
| Python | `pyproject.toml` / `setup.py` | `pytest` |
| Node.js | `package.json` | `npm test` |
| Go | `go.mod` | `go test ./...` |
| Rust | `Cargo.toml` | `cargo test` |
| Java (Maven) | `pom.xml` | `mvn test` |
| Java (Gradle) | `build.gradle` | `./gradlew test` |
| Makefile | `Makefile` | `make test` |

## What the Review Includes

- **Risk Assessment** — Low / Medium / High / Critical
- **Test Results** — Actually runs the test suite and reports pass/fail
- **Bug Detection** — Logic errors, breaking changes, security issues
- **Inline Comments** — Specific file + line references with fix suggestions
- **Missing Tests** — What test cases should be added

## License

MIT
