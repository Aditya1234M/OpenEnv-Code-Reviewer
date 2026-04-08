# Hugging Face Space Quick Fix

If your Space shows "Missing configuration in README", use this exact top block in the Space README:

```md
---
title: OpenEnv PR Grader
emoji: "🤖"
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---
```

For Docker Space, ensure `Dockerfile` runs on port 7860 (or reads `PORT` env var).

This repository's Dockerfile is already Space-compatible:

- default `PORT=7860`
- `EXPOSE 7860`
- command uses `${PORT}` for uvicorn

After updating Space files, commit/push and wait for rebuild.
