"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from app.config import settings
from app.database import Neo4jConnection, verify_connectivity
from app.api import reconciliation, dashboard, audit, risk, ingestion, model_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Neo4j connection lifecycle."""
    logger.info("Connecting to Neo4j...")
    Neo4jConnection.get_driver()
    verify_connectivity()
    logger.info("Neo4j connected successfully.")
    yield
    logger.info("Shutting down Neo4j connection...")
    Neo4jConnection.close()


app = FastAPI(
    title="GST Reconciliation Engine",
    description="Intelligent GST Reconciliation using Knowledge Graphs",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(reconciliation.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")
app.include_router(model_metrics.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"service": "GST Reconciliation Engine", "version": "1.0.0"}


@app.get("/health")
async def health():
    try:
        verify_connectivity()
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "degraded", "neo4j": str(e)}
