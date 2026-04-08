"""FastAPI server exposing OpenEnv-compatible reset/state/step APIs."""

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config import settings
from src.pipeline import current_state, reset_environment, step_environment

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenEnv Code Review Environment")


class ResetRequest(BaseModel):
    seed: int | None = None


class StepRequest(BaseModel):
    action: dict[str, Any] | str


class GradeRequest(BaseModel):
    action: dict[str, Any] | str
    seed: int | None = None
    pr_url: str | None = None


_DEFAULT_ACTION = {
    "overall_decision": "request_changes",
    "issues": [
        {
            "file": "auth.py",
            "line": 5,
            "category": "security",
            "severity": "critical",
            "description": "Empty token bypass",
        }
    ],
}


def _reward_to_grade(reward: float) -> str:
    if reward >= 0.9:
        return "A"
    if reward >= 0.7:
        return "B"
    if reward >= 0.5:
        return "C"
    if reward >= 0.3:
        return "D"
    return "F"


def _build_explanation(grade: str, score: dict[str, Any]) -> str:
    tp = int(score.get("true_positives", 0) or 0)
    fp = int(score.get("false_positives", 0) or 0)
    missed = int(score.get("missed", 0) or 0)
    sev_hits = int(score.get("severity_hits", 0) or 0)
    critical_missed = int(score.get("critical_missed", 0) or 0)
    decision_match = bool(score.get("decision_match", False))

    parts = [
        f"Grade {grade} based on {tp} true positive(s), {fp} false positive(s), and {missed} missed issue(s).",
        f"Severity matched for {sev_hits} issue(s).",
        "Overall decision matched expected outcome." if decision_match else "Overall decision did not match expected outcome.",
    ]
    if critical_missed > 0:
        parts.append(f"Penalty applied for {critical_missed} missed critical issue(s).")
    return " ".join(parts)


def _build_markdown_report(task_id: str, reward: float, score: dict[str, Any], pr_url: str | None) -> str:
    grade = _reward_to_grade(reward)
    explanation = _build_explanation(grade, score)
    lines = [
        "## OpenEnv PR Review Grade",
        "",
        f"- Task: `{task_id}`",
        f"- Reward: `{reward:.4f}`",
        f"- Grade: `{grade}`",
    ]
    if pr_url:
        lines.append(f"- PR: {pr_url}")

    lines.extend(
        [
            "",
        "### Explanation",
        explanation,
        "",
            "### Score Breakdown",
            f"- True Positives: `{score.get('true_positives', 0)}`",
            f"- False Positives: `{score.get('false_positives', 0)}`",
            f"- Missed Issues: `{score.get('missed', 0)}`",
            f"- Severity Hits: `{score.get('severity_hits', 0)}`",
            f"- Critical Missed: `{score.get('critical_missed', 0)}`",
            f"- Decision Match: `{score.get('decision_match', False)}`",
        ]
    )
    return "\n".join(lines)


def _grade_action(action: dict[str, Any] | str, seed: int | None, pr_url: str | None) -> dict[str, Any]:
    reset_environment(seed=seed)
    obs, reward, terminated, truncated, info = step_environment(action)
    score = info.get("score", {})
    task_id = str(info.get("task_id", "unknown"))
    grade_letter = _reward_to_grade(reward)
    explanation = _build_explanation(grade_letter, score)

    return {
        "task_id": task_id,
        "reward": reward,
        "grade": grade_letter,
        "explanation": explanation,
        "terminated": terminated,
        "truncated": truncated,
        "score": score,
        "observation": obs,
        "markdown_report": _build_markdown_report(task_id, reward, score, pr_url),
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Tiny built-in UI for live demo and grading visibility."""
    return """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>OpenEnv Code Review Grader</title>
  <style>
    body { font-family: Segoe UI, sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }
    .card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    textarea { width: 100%; min-height: 170px; font-family: Consolas, monospace; }
    button { background: #0f766e; color: white; border: none; padding: 10px 14px; border-radius: 8px; cursor: pointer; }
    pre { white-space: pre-wrap; background: #0b1020; color: #e2e8f0; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>OpenEnv PR Review Grader</h1>
  <div class='card'>
    <p>Use this page to submit an agent review action and view grading output.</p>
    <button id='btnReset'>Reset Episode</button>
    <p id='taskInfo'></p>
  </div>
  <div class='card'>
    <h3>Agent Action JSON</h3>
    <textarea id='actionBox'>{
  "overall_decision": "request_changes",
  "issues": [
    {
      "file": "auth.py",
      "line": 5,
      "category": "security",
      "severity": "critical",
      "description": "Empty token bypass"
    }
  ]
}</textarea>
    <p style='margin-top:12px;'>
      <button id='btnGrade'>Grade Action</button>
    </p>
  </div>
  <div class='card'>
    <h3>Result</h3>
    <pre id='resultBox'>No grading yet.</pre>
  </div>

  <script>
    async function resetEpisode() {
      const r = await fetch('/reset', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({seed: 123}) });
      const data = await r.json();
      document.getElementById('taskInfo').innerText = 'Task: ' + (data.info?.task_id || 'n/a');
    }

    async function gradeAction() {
      const raw = document.getElementById('actionBox').value;
      let action;
      try { action = JSON.parse(raw); }
      catch (e) {
        document.getElementById('resultBox').innerText = 'Invalid JSON: ' + e;
        return;
      }

      const r = await fetch('/grade', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ action })
      });
      const data = await r.json();
      document.getElementById('resultBox').innerText = JSON.stringify(data, null, 2);
    }

    document.getElementById('btnReset').onclick = resetEpisode;
    document.getElementById('btnGrade').onclick = gradeAction;
    resetEpisode();
  </script>
</body>
</html>
"""


@app.post("/reset")
async def reset(payload: ResetRequest):
    """Start a new episode and return initial observation."""
    obs, info = reset_environment(seed=payload.seed)
    return {"observation": obs, "info": info}


@app.get("/state")
async def state():
    """Return current environment observation without stepping."""
    return {"observation": current_state()}


@app.post("/step")
async def step(payload: StepRequest):
    """Apply an action and return OpenEnv transition tuple."""
    try:
        obs, reward, terminated, truncated, info = step_environment(payload.action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid action payload: {exc}") from exc

    return {
        "observation": obs,
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "info": info,
    }


@app.post("/grade")
async def grade(payload: GradeRequest | None = None):
    """One-shot grading endpoint useful for UI and automation pipelines."""
    if payload is None:
        # Some external validators probe POST endpoints without JSON bodies.
        # Return a valid JSON response instead of a 422 to improve compatibility.
        return {
            "status": "ok",
            "message": "No body provided. Returning demo grade response.",
            "result": _grade_action(_DEFAULT_ACTION, 123, None),
        }
    return _grade_action(payload.action, payload.seed, payload.pr_url)


@app.post("/github/pr-review-grade")
async def github_pr_review_grade(payload: GradeRequest | None = None):
    """GitHub-Action-friendly alias endpoint returning markdown report for PR checks."""
    if payload is None:
        result = _grade_action(_DEFAULT_ACTION, 123, None)
    else:
        result = _grade_action(payload.action, payload.seed, payload.pr_url)
    return {
        "status": "ok",
        "summary_markdown": result["markdown_report"],
        "result": result,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "openenv-code-review"}
