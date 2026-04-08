# Judges Quickstart

This project provides an OpenEnv-compatible grading service for PR review actions.

## 1) Start the service

```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
```

Verify:

- `GET /health`
- `GET /` (built-in UI)

## 2) Quick local grading test

```bash
curl -X POST http://127.0.0.1:8000/grade \
  -H "Content-Type: application/json" \
  -d '{
    "seed": 123,
    "pr_url": "https://github.com/demo/repo/pull/1",
    "action": {
      "overall_decision": "request_changes",
      "issues": [
        {
          "file": "auth.py",
          "line": 5,
          "category": "security",
          "severity": "critical",
          "description": "auth bypass"
        }
      ]
    }
  }'
```

## 3) GitHub PR integration (Actions-only)

1. In target repo, add secret `GRADER_URL` (public URL of this service).
2. Add secret `OPENAI_API_KEY` for action generation from real PR diffs.
3. Optional: add `OPENAI_BASE_URL` and `OPENAI_MODEL` if using non-default provider/model.
4. Add workflow file from `docs/pr-grader-workflow.yml` to `.github/workflows/pr-grader.yml`.
5. Open or update a PR.
6. Workflow generates action from actual PR diff and posts grade summary comment to PR.

## 4) Endpoints used in evaluation

- `POST /reset`
- `GET /state`
- `POST /step`
- `POST /grade`
- `POST /github/pr-review-grade`

All responses are JSON and include machine-readable scores.
