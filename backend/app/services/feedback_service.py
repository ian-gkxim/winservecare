"""Service layer for Journey Feedback business logic."""

from fastapi import HTTPException

from backend.app.db import feedback_repository as fb_repo
from backend.app.db import journey_repository as journey_repo
from backend.app.models.journey import (
    FeedbackRating,
    JourneyFeedbackCreate,
    JourneyFeedbackModel,
    JourneyStatus,
)


class FeedbackService:
    """Encapsulates business logic for journey route feedback."""

    async def submit_feedback(self, data: JourneyFeedbackCreate) -> JourneyFeedbackModel:
        """Validate journey eligibility and persist feedback.

        Validates:
        - Journey exists (422 if not)
        - Journey has status 'completed' (422 if not)
        - No duplicate feedback for same journey+carer (409 if exists)
        """
        # 1. Check journey exists
        journey = await journey_repo.get_journey(data.journey_id)
        if journey is None:
            raise HTTPException(
                status_code=422,
                detail=f"Journey {data.journey_id} does not exist.",
            )

        # 2. Check journey is completed
        if journey["status"] != JourneyStatus.COMPLETED.value:
            raise HTTPException(
                status_code=422,
                detail=f"Journey {data.journey_id} has status '{journey['status']}', feedback requires 'completed' status.",
            )

        # 3. Check no duplicate
        exists = await fb_repo.feedback_exists(data.journey_id, data.carer_id)
        if exists:
            raise HTTPException(
                status_code=409,
                detail=f"Feedback already exists for journey {data.journey_id} from carer {data.carer_id}.",
            )

        # 4. Persist
        row = await fb_repo.insert_feedback(
            journey_id=data.journey_id,
            carer_id=data.carer_id,
            rating=data.rating.value,
            comment=data.comment,
            submitted_at=data.submitted_at.isoformat(),
        )

        return JourneyFeedbackModel(
            id=row["id"],
            journey_id=row["journey_id"],
            carer_id=row["carer_id"],
            rating=FeedbackRating(row["rating"]),
            comment=row.get("comment"),
            submitted_at=row["submitted_at"],
            created_at=row["created_at"],
        )

    async def get_feedback(self, journey_id: int) -> JourneyFeedbackModel | None:
        """Retrieve feedback for a specific journey. Returns None if no feedback."""
        row = await fb_repo.get_feedback_by_journey(journey_id)
        if row is None:
            return None

        return JourneyFeedbackModel(
            id=row["id"],
            journey_id=row["journey_id"],
            carer_id=row["carer_id"],
            rating=FeedbackRating(row["rating"]),
            comment=row.get("comment"),
            submitted_at=row["submitted_at"],
            created_at=row["created_at"],
        )
