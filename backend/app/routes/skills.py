"""Skill API endpoints."""

from fastapi import APIRouter, HTTPException

from backend.app.db.repositories import get_skills, create_skill
from backend.app.models.skill import SkillCreate, SkillModel

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills():
    """Retrieve all skills with usage counts."""
    return await get_skills()


@router.post("", response_model=SkillModel, status_code=201)
async def add_skill(data: SkillCreate) -> SkillModel:
    """Create a new skill. Name must be unique and 1-100 characters."""
    try:
        return await create_skill(data.name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
