"""
Data ingestion API endpoints.
"""

from fastapi import APIRouter
from app.ingestion.generator import SyntheticDataGenerator
from app.ingestion.neo4j_loader import Neo4jLoader
from app.ingestion.validator import DataValidator

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


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
    gen.export_json("data/synthetic")
    gen.export_csv("data/synthetic")
    return {
        "status": "generated",
        "taxpayers": len(data["taxpayers"]),
        "invoices": len(data["invoices"]),
    }


@router.post("/load")
async def load_data():
    """Load generated data into Neo4j."""
    loader = Neo4jLoader()
    loader.load_all("data/synthetic")
    return {"status": "loaded"}


@router.post("/validate")
async def validate_data():
    """Run data quality validations."""
    validator = DataValidator()
    report = validator.run_all_checks()
    return report


@router.post("/seed")
async def seed_database(
    num_taxpayers: int = 55,
    num_invoices: int = 600,
):
    """Generate, load, and validate in one step."""
    gen = SyntheticDataGenerator(
        num_taxpayers=num_taxpayers,
        num_invoices=num_invoices,
    )
    gen.generate_all()
    gen.export_json("data/synthetic")

    loader = Neo4jLoader()
    loader.load_all("data/synthetic")

    validator = DataValidator()
    report = validator.run_all_checks()
    return {"status": "seeded", "validation": report}
