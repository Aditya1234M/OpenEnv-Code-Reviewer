"""Server entrypoint shim for multi-mode deployment validators."""

from __future__ import annotations

import os
import uvicorn

from src.server import app


def main() -> None:
    """Run the FastAPI server."""
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.server:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
