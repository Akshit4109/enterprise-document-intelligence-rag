import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.logging import logger

router = APIRouter(tags=["Health"])

START_TIME = time.time()


@router.get("/health", summary="Basic Service Health Check")
def health_check():
    """
    Returns basic application liveness, uptime, and service metadata.
    """
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": uptime_seconds,
        "version": "1.0.0",
    }


@router.get("/health/db", summary="Database Connectivity & Vector Extension Check")
def database_health_check(db: Session = Depends(get_db)):
    """
    Verifies PostgreSQL database connectivity, executes ping, and confirms pgvector extension status.
    """
    start = time.perf_counter()
    try:
        # Ping database
        db.execute(text("SELECT 1")).scalar()

        # Verify pgvector extension
        pgvector_active = db.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        ).scalar()

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        pool = engine.pool
        pool_status = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

        return {
            "status": "healthy",
            "database": "postgresql",
            "pgvector_installed": bool(pgvector_active),
            "latency_ms": latency_ms,
            "pool": pool_status,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.error(f"Database health check failed after {latency_ms}ms: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": "postgresql",
                "error": "Failed to connect to database",
                "latency_ms": latency_ms,
            },
        )
