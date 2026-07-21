"""Configuration endpoints for the AI Care Operations Optimiser."""

from fastapi import APIRouter, HTTPException

from backend.app.db.repositories import get_config, update_config
from backend.app.models.config import ConfigUpdate

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def read_config() -> dict:
    """Return current configuration status.

    Returns whether a Google Maps API key is set (hasApiKey) and
    a masked version of the key for display purposes.
    """
    config = await get_config()
    api_key = config.get("google_maps_api_key", "")
    has_key = bool(api_key.strip())

    return {
        "hasApiKey": has_key,
        "googleMapsApiKey": "***" if has_key else "",
    }


@router.get("/maps-key")
async def read_maps_key() -> dict:
    """Return the actual Google Maps API key for the frontend map loader.

    This endpoint is used internally by the AnimatedMap component to
    initialize the Google Maps JavaScript API.
    """
    config = await get_config()
    api_key = config.get("google_maps_api_key", "")

    return {
        "key": api_key.strip(),
    }


@router.put("")
async def write_config(data: ConfigUpdate) -> dict:
    """Update the Google Maps API key.

    Validates that the key is not empty before persisting.
    """
    if not data.google_maps_api_key.strip():
        raise HTTPException(
            status_code=422,
            detail="Google Maps API key is required and cannot be empty.",
        )

    await update_config("google_maps_api_key", data.google_maps_api_key.strip())

    return {
        "hasApiKey": True,
        "googleMapsApiKey": "***",
    }
