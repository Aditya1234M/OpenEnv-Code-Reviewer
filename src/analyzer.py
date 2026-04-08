"""Codebase Analyzer — uses OpenAI to analyze code + PR diffs."""

import asyncio
import json
import logging
import os

from openai import OpenAI

from src.config import settings

logger = logging.getLogger(__name__)


def _collect_repo_files(repo_path: str) -> list[dict]:
    """Walk the cloned repo and collect file contents, skipping binary and large files."""
    files = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    text_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala",
        ".md", ".txt", ".yml", ".yaml", ".toml", ".json", ".xml",
        ".html", ".css", ".scss", ".sql", ".sh", ".bash", ".zsh",
        ".dockerfile", ".tf", ".hcl", ".proto", ".graphql",
    }

    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            known_names = {"Makefile", "Dockerfile", "Jenkinsfile"}
            if ext not in text_extensions and fname not in known_names:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, repo_path)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Skip files larger than 100 KB to stay within token budget
                if len(content) > 100_000:
                    content = content[:100_000] + "\n... [TRUNCATED] ..."
                files.append({"path": rel_path, "content": content})
            except OSError:
                continue

    return files


def _build_analysis_prompt(repo_files: list[dict], diff_summary: str) -> str:
    """Build the prompt that feeds the full codebase + PR diff to OpenAI."""
    codebase_section = ""
    for f in repo_files:
        codebase_section += f"\n\n=== FILE: {f['path']} ===\n{f['content']}"

    return f"""You are an expert code reviewer for an open-source project.

Below is the FULL CODEBASE of the repository, followed by the DIFF of a new Pull Request.

Your job:
1. Understand the existing codebase architecture, patterns, and conventions.
2. Analyze the PR diff for:
   - Bugs or logic errors introduced
   - Breaking changes to existing functionality
   - Missing error handling
   - Security vulnerabilities (injection, auth issues, etc.)
   - Style/convention violations compared to the existing code
   - Missing or inadequate tests
3. Provide a structured JSON review with:
   - "summary": A 2-3 sentence overall assessment
   - "risk_level": "low" | "medium" | "high" | "critical"
   - "issues": A list of objects, each with "file", "line", "severity", "description", "suggestion"
   - "missing_tests": A list of test cases that should be added
   - "approval": "approve" | "request_changes" | "comment"

Be specific. Reference exact file paths and line numbers. Provide concrete fix suggestions.

--- FULL CODEBASE ---
{codebase_section}

--- PR DIFF ---
{diff_summary}

Return ONLY valid JSON. No markdown fences.
"""


def _invoke_openai(prompt: str) -> str:
    """Invoke an OpenAI-compatible chat completion endpoint and return text output."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for analysis in OpenEnv mode")

    base_url = settings.openai_base_url.strip() or "https://api.openai.com/v1"
    # Auto-switch for OpenRouter keys when base URL is not explicitly set.
    if base_url == "https://api.openai.com/v1" and settings.openai_api_key.startswith("sk-or-"):
        base_url = "https://openrouter.ai/api/v1"

    default_headers = None
    if "openrouter.ai" in base_url:
        default_headers = {}
        if settings.openrouter_site_url:
            default_headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_app_name:
            default_headers["X-Title"] = settings.openrouter_app_name

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=base_url,
        default_headers=default_headers,
    )
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4096,
    )
    content = response.choices[0].message.content if response.choices else ""
    return content or ""


async def analyze_codebase_with_pr(repo_path: str, diff_summary: str) -> dict:
    """Send the full codebase + PR diff to OpenAI for deep analysis."""
    logger.info("Collecting repo files from: %s", repo_path)
    repo_files = _collect_repo_files(repo_path)
    logger.info("Collected %d files for analysis", len(repo_files))

    prompt = _build_analysis_prompt(repo_files, diff_summary)

    logger.info("Sending analysis request to OpenAI model (%s)", settings.openai_model)
    raw_text = await asyncio.to_thread(_invoke_openai, prompt)

    try:
        analysis = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("OpenAI model returned non-JSON; wrapping as raw analysis")
        analysis = {
            "summary": raw_text[:500],
            "risk_level": "unknown",
            "issues": [],
            "missing_tests": [],
            "approval": "comment",
        }

    logger.info("Analysis complete — risk: %s, issues: %d",
                analysis.get("risk_level"), len(analysis.get("issues", [])))
    return analysis
