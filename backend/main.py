from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.router import register_routers
from backend.core.config import settings
from backend.core.observability import get_request_id, reset_request_id, set_request_id
from backend.core.security import SecurityError
from backend.db.database import close_db, init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    try:
        yield
    finally:
        await close_db()


app = FastAPI(title="PlanixAI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
    token = set_request_id(request_id)
    request.state.request_id = request_id
    started_at = perf_counter()

    logger.info(
        "Request started | request_id=%s method=%s path=%s query=%s client=%s",
        request_id,
        request.method,
        request.url.path,
        request.url.query or "-",
        request.client.host if request.client else "-",
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "Request crashed | request_id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "Request completed | request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    reset_request_id(token)
    return response


def _error_response(status_code: int, detail) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "HTTP exception | request_id=%s method=%s path=%s status=%s detail=%s",
        get_request_id(),
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return _error_response(exc.status_code, exc.detail)


@app.exception_handler(SecurityError)
async def handle_security_error(request: Request, exc: SecurityError) -> JSONResponse:
    logger.warning(
        "Security error | request_id=%s method=%s path=%s detail=%s",
        get_request_id(),
        request.method,
        request.url.path,
        str(exc),
    )
    return _error_response(status.HTTP_400_BAD_REQUEST, str(exc))


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors(include_url=False)
    logger.info(
        "Request validation error | request_id=%s method=%s path=%s errors=%s",
        get_request_id(),
        request.method,
        request.url.path,
        errors,
    )
    return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, errors)


@app.exception_handler(ValidationError)
async def handle_pydantic_validation_error(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    errors = exc.errors(include_url=False)
    messages = [error["msg"] for error in errors]
    logger.info(
        "Pydantic validation error | request_id=%s method=%s path=%s messages=%s",
        get_request_id(),
        request.method,
        request.url.path,
        messages,
    )
    return _error_response(
        status.HTTP_400_BAD_REQUEST,
        messages[0] if len(messages) == 1 else messages,
    )


@app.exception_handler(IntegrityError)
async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning(
        "Database integrity error | request_id=%s method=%s path=%s",
        get_request_id(),
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _error_response(
        status.HTTP_409_CONFLICT,
        "Database constraint violation.",
    )


@app.exception_handler(SQLAlchemyError)
async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception(
        "Database error | request_id=%s method=%s path=%s",
        get_request_id(),
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Database operation failed.",
    )


@app.exception_handler(ResponseValidationError)
async def handle_response_validation_error(
    request: Request,
    exc: ResponseValidationError,
) -> JSONResponse:
    logger.exception(
        "Response validation error | request_id=%s method=%s path=%s",
        get_request_id(),
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Response serialization failed.",
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled application error | request_id=%s method=%s path=%s",
        get_request_id(),
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Internal server error.",
    )


register_routers(app)
