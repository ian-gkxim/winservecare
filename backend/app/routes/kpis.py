"""KPI endpoints for the AI Care Operations Optimiser."""

from fastapi import APIRouter

from backend.app.db.repositories import get_kpis
from backend.app.models.optimisation import KPIMetrics

router = APIRouter(prefix="/api/kpis", tags=["kpis"])


@router.get("", response_model=KPIMetrics)
async def read_kpis() -> KPIMetrics:
    """Return current KPI metrics.

    Metrics include total visits, carers available, travel hours,
    mileage, overtime, and continuity score. Values are sourced from
    the latest scenario if available, otherwise derived from base data.
    """
    return await get_kpis()
