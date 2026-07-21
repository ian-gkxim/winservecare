"""Pydantic models for application configuration."""

from pydantic import BaseModel


class ConfigModel(BaseModel):
    """Configuration key-value pair."""

    key: str
    value: str


class ConfigUpdate(BaseModel):
    """Payload for updating configuration (Google Maps API key)."""

    google_maps_api_key: str
