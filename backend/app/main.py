"""FastAPI application entry point for the AI Care Operations Optimiser backend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler: initialise database on startup."""
    from backend.app.db.database import init_db
    from backend.app.routes.jobs import init_registry

    await init_db()
    init_registry()
    yield


app = FastAPI(
    title="AI Care Operations Optimiser",
    description="Backend API for domiciliary care route optimisation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration — allow the Vite dev server and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        os.environ.get("CORS_ORIGIN", "http://localhost:5173"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Route registration
from backend.app.routes.carers import router as carers_router  # noqa: E402
from backend.app.routes.patients import router as patients_router  # noqa: E402
from backend.app.routes.contracts import router as contracts_router  # noqa: E402
from backend.app.routes.visits import router as visits_router  # noqa: E402
from backend.app.routes.skills import router as skills_router  # noqa: E402
from backend.app.routes.constraints import router as constraints_router  # noqa: E402

from backend.app.routes.scenarios import router as scenarios_router  # noqa: E402
from backend.app.routes.exceptions import router as exceptions_router  # noqa: E402
from backend.app.routes.kpis import router as kpis_router  # noqa: E402
from backend.app.routes.reports import router as reports_router  # noqa: E402
from backend.app.routes.config import router as config_router  # noqa: E402
from backend.app.routes.websocket import router as websocket_router  # noqa: E402
from backend.app.routes.journeys import router as journeys_router  # noqa: E402
from backend.app.routes.mobile_schedule import router as mobile_schedule_router  # noqa: E402
from backend.app.routes.mobile_auth import router as mobile_auth_router  # noqa: E402
from backend.app.routes.mobile_signals import router as mobile_signals_router  # noqa: E402
from backend.app.routes.mobile_questions import router as mobile_questions_router  # noqa: E402
from backend.app.routes.jobs import router as jobs_router  # noqa: E402

app.include_router(carers_router)
app.include_router(patients_router)
app.include_router(contracts_router)
app.include_router(visits_router)
app.include_router(skills_router)
app.include_router(constraints_router)
app.include_router(scenarios_router)
app.include_router(exceptions_router)
app.include_router(kpis_router)
app.include_router(reports_router)
app.include_router(config_router)
app.include_router(websocket_router)
app.include_router(journeys_router)
app.include_router(mobile_schedule_router)
app.include_router(mobile_auth_router)
app.include_router(mobile_signals_router)
app.include_router(mobile_questions_router)
app.include_router(jobs_router)


# --- Serve built frontend in production ---
# If frontend/dist exists (Docker production build), serve it as static files.
# In development, Vite handles this via its proxy.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    # Catch-all: serve index.html for any non-API route (SPA client-side routing)
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the React SPA for all non-API routes."""
        # Don't intercept API, WebSocket, health, or docs routes
        if full_path.startswith(("api/", "ws/", "health", "docs", "openapi.json", "redoc")):
            return None
        file_path = _FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
