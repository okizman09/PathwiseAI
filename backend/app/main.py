import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import UserFacingError, log_internal_error
from app.core.rate_limit import get_client_ip
from app.routers import events, go, health, interview, quota, taxonomy, tools, users, workflow


class JSONLogFormatter(logging.Formatter):
    STANDARD_ATTRS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message"
    }

    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key not in self.STANDARD_ATTRS and not key.startswith("_"):
                lower_key = key.lower()
                # Security: never log tokens, passwords, secrets, API keys, or prompts containing user data
                if any(s in lower_key for s in ("token", "secret", "password", "key", "authorization", "prompt", "cookie")):
                    continue
                log_record[key] = val

        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger("pathwise.api")
handler = logging.StreamHandler()
if settings.ENVIRONMENT == "production":
    handler.setFormatter(JSONLogFormatter())
else:
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger.handlers = [handler]
logger.setLevel(logging.INFO)
# Avoid double logging
logger.propagate = False

if settings.SENTRY_DSN:
    try:
        import sentry_sdk

        def scrub_sentry_event(event, hint):
            # Scrub request headers (Authorization, cookie, etc.)
            request_data = event.get("request", {})
            headers = request_data.get("headers", {})
            for key in list(headers.keys()):
                if key.lower() in ("authorization", "cookie", "proxy-authorization", "x-api-key"):
                    headers[key] = "[REDACTED]"

            # Scrub prompt and user goals from request data
            data = request_data.get("data")
            if isinstance(data, dict):
                for sensitive in ("prompt", "goal", "user_goal", "idea", "answer", "notes", "input"):
                    if sensitive in data:
                        data[sensitive] = "[REDACTED]"
            elif isinstance(data, str):
                for sensitive in ("prompt", "goal", "user_goal"):
                    if sensitive in data.lower():
                        data = "[REDACTED_REQUEST_BODY]"
                        request_data["data"] = data
                        break

            # Scrub breadcrumbs
            for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
                b_data = breadcrumb.get("data", {})
                if isinstance(b_data, dict):
                    for k in list(b_data.keys()):
                        if any(s in k.lower() for s in ("prompt", "goal", "token", "auth")):
                            b_data[k] = "[REDACTED]"

            return event

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            before_send=scrub_sentry_event,
            traces_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
            send_default_pii=False,
        )
    except ImportError:
        logger.warning("sentry-sdk is not installed; skipping Sentry initialization.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Slice 1: No table creation or seeding at startup. Handled by Alembic and scripts.
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENVIRONMENT != "production" else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS middleware for local Vite / Next frontends and Cloudflare deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*(\.workers\.dev|\.pages\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(UserFacingError)
async def user_facing_error_handler(request: Request, exc: UserFacingError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    is_admin = request.url.path.startswith("/api/v1/admin") or request.url.path.startswith("/admin")
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    if not is_admin and exc.status_code >= 500:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Something went wrong. Please try again."},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log_internal_error(exc, f"{request.method} {request.url.path}")
    is_admin = request.url.path.startswith("/api/v1/admin") or request.url.path.startswith("/admin")
    if is_admin:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )



@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Log incoming HTTP request method, path, client IP, response status, and duration."""
    start_time = time.perf_counter()

    client_ip = get_client_ip(request)

    response = await call_next(request)

    process_time_ms = (time.perf_counter() - start_time) * 1000.0

    if settings.ENVIRONMENT == "production":
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": process_time_ms,
                "client_ip": client_ip
            }
        )
    else:
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({process_time_ms:.1f}ms) [Client: {client_ip}]"
        )

    return response


# Top-level routes: /health, /go, /taxonomy, /tools, /admin/tools
app.include_router(health.router)
app.include_router(go.router)
app.include_router(taxonomy.router)
app.include_router(tools.router)

# API routes mounted strictly under /api/v1
app.include_router(health.router, prefix="/api/v1")
app.include_router(taxonomy.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(interview.router, prefix="/api/v1")
app.include_router(workflow.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(quota.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
