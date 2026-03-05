"""
Data ingestion API endpoints.
"""

import os
import json
from fastapi import APIRouter
from loguru import logger
from app.ingestion.generator import SyntheticDataGenerator
from app.ingestion.neo4j_loader import Neo4jLoader
from app.ingestion.validator import DataValidator
from app.ingestion.seed_fraud_cases import seed_fraud_cases

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "synthetic"
)


@router.post("/generate")
async def generate_data(
    num_taxpayers: int = 55,
    num_invoices: int = 600,
    mismatch_rate: float = 0.17,
):
    """Generate synthetic GST data."""
    gen = SyntheticDataGenerator(
        num_taxpayers=num_taxpayers,
        num_invoices=num_invoices,
        mismatch_rate=mismatch_rate,
    )
    data = gen.generate_all()
    os.makedirs(DATA_DIR, exist_ok=True)
    gen.export_json(DATA_DIR)
    gen.export_csv(DATA_DIR)
    return {
        "status": "generated",
        "taxpayers": len(data["taxpayers"]),
        "invoices_gstr1": len(data["invoices_gstr1"]),
        "invoices_gstr2b": len(data["invoices_gstr2b"]),
    }


@router.post("/load")
async def load_data():
    """Load generated data into Neo4j from previously exported JSON."""
    data = {}
    keys = [
        "taxpayers", "gstins", "invoices_gstr1", "invoices_gstr2b",
        "returns", "irns", "ewaybills", "line_items",
        "bank_transactions", "purchase_entries",
    ]
    for key in keys:
        filepath = os.path.join(DATA_DIR, f"{key}.json")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                data[key] = json.load(f)
        else:
            data[key] = []

    loader = Neo4jLoader()
    stats = loader.load_all(data)
    return {"status": "loaded", "stats": stats}


@router.post("/validate")
async def validate_data():
    """Run data quality validations."""
    validator = DataValidator()
    report = validator.validate_all()
    return report


@router.post("/seed")
async def seed_database(
    num_taxpayers: int = 55,
    num_invoices: int = 600,
):
    """Generate, load, and validate in one step."""
    logger.info(f"Seeding database with {num_taxpayers} taxpayers, {num_invoices} invoices...")

    # Step 1: Generate synthetic data
    gen = SyntheticDataGenerator(
        num_taxpayers=num_taxpayers,
        num_invoices=num_invoices,
    )
    data = gen.generate_all()
    os.makedirs(DATA_DIR, exist_ok=True)
    gen.export_json(DATA_DIR)
    logger.info(f"Generated: {data['stats']}")

    # Step 2: Load data dict directly into Neo4j
    loader = Neo4jLoader()
    stats = loader.load_all(data)
    logger.info(f"Loaded into Neo4j: {stats}")

    # Step 3: Validate
    validator = DataValidator()
    report = validator.validate_all()

    return {
        "status": "seeded",
        "generation_stats": data["stats"],
        "load_stats": stats,
        "validation": report,
    }


@router.post("/seed-fraud")
async def seed_fraud():
    """Seed realistic fraud cases (Mismatch nodes) + risk profiles into Neo4j."""
    logger.info("Seeding fraud cases...")
    result = seed_fraud_cases()
    return result
