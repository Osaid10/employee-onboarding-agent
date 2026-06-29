"""
Lab 8 — FastAPI entry point.

This file satisfies the Lab 8 submission checklist requirement for 'main.py'.
It re-exports the FastAPI application from web/app.py so the server can be
launched directly from the project root:

    uvicorn api_main:app --host 0.0.0.0 --port 8000

The actual implementation lives in web/app.py to maintain the project's
package structure. All endpoints (/api/chat, /api/stream, /api/employees, etc.)
are defined there.
"""

from web.app import app  # noqa: F401  — re-export for uvicorn

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)
