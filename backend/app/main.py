from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, metrics, pipeline, teams, users
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.scheduler import start_scheduler, stop_scheduler

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Operacional C6 — API",
    description="Automação de relatórios e dashboards operacionais do Corban C6Bank.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.environment != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(users.router)
app.include_router(metrics.router)
app.include_router(audit.router)
app.include_router(pipeline.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
