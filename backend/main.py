from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.internal import router as internal_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.limiter import limiter

app = FastAPI(title="Oddlot API", version="0.1.0")

# ── Rate limiter ───────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers ───────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains; preload"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(v1_router)       # /api/v1/...
app.include_router(internal_router)  # /internal/...


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}
