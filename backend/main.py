"""Railway/Railpack entrypoint.

Railpack's default Python web start command is often `uvicorn main:app`.
JarlPM's FastAPI application lives in `server.py`.

This module provides a stable `main:app` target for deployment.
"""

from server import app  # noqa: F401
