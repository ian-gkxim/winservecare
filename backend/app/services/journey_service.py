"""Service layer for Journey Lifecycle Management business logic."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from backend.app.db import journey_repository as repo
from backend.app.db.repositories import get_carers, get_patients
from fastapi import HTTPException

from backend.app.models.journey import (
    ActualJourneyCreate,
    ActualJourneyModel,
    ComparisonEntry,
    ComparisonResult,
    DaySummary,
    DeleteConfirmation,
    JourneyCreate,
    JourneyFilters,
    JourneyModel,
    JourneyPlanModel,
    JourneyStatus,
    JourneyUpdate,
    MatchStatus,
    PaginatedResult,
    PlanCreationReason,
    VarianceModel,
)
from backend.app.models.optimisation import RouteModel


class JourneyService:
    """Encapsulates business logic for journey plan lifecycle operations."""

    async def create_plan(
        self,
        operating_day: date,
        journeys: list[JourneyCreate],
        reason: PlanCreationReason,
    ) -> JourneyPlanModel:
        """Create a new journey plan for a specified operating day.

        Validates the operating day is today or a future date within 365 days,
        determines the next plan version, persists the plan and its journeys.

        Args:
            operating_day: The date for which the plan is being created.
            journeys: List of journey payloads to include in the plan.
            reason: The reason for creating this plan version.

        Returns:
            The full JourneyPlanModel with nested journey records.

        Raises:
            ValueError: If operating_day is in the past or more than 365 days ahead.
        """
        today = date.today()

        if operating_day < today:
            raise ValueError(
                "Plans cannot be created for past dates. "
                f"Operating day {operating_day.isoformat()} is before today ({today.isoformat()})."
            )

        max_future = today + timedelta(days=365)
        if operating_day > max_future:
            raise ValueError(
                "Plans cannot be created for dates more than 365 days in the future. "
                f"Operating day {operating_day.isoformat()} exceeds the limit ({max_future.isoformat()})."
            )

        # Determine the next plan version for this operating day
        operating_day_str = operating_day.isoformat()
        latest_version = await repo.get_latest_plan_version(operating_day_str)
        new_version = latest_version + 1

        # Create the journey plan record
        plan_row = await repo.create_journey_plan(
            operating_day=operating_day_str,
            creation_reason=reason.value,
            plan_version=new_version,
        )

        plan_id = plan_row["id"]

        # Create each journey record within the plan
        journey_models: list[JourneyModel] = []
        for journey_data in journeys:
            journey_row = await repo.create_journey(
                plan_id=plan_id,
                carer_id=journey_data.carer_id,
                visit_id=journey_data.visit_id,
                origin_lat=journey_data.origin_lat,
                origin_lng=journey_data.origin_lng,
                origin_label=journey_data.origin_label,
                destination_lat=journey_data.destination_lat,
                destination_lng=journey_data.destination_lng,
                destination_label=journey_data.destination_label,
                planned_departure=journey_data.planned_departure.isoformat(),
                planned_arrival=journey_data.planned_arrival.isoformat(),
                planned_distance_miles=journey_data.planned_distance_miles,
            )
            journey_models.append(_row_to_journey_model(journey_row))

        return JourneyPlanModel(
            id=plan_row["id"],
            operating_day=plan_row["operating_day"],
            plan_version=plan_row["plan_version"],
            creation_reason=PlanCreationReason(plan_row["creation_reason"]),
            is_archived=bool(plan_row["is_archived"]),
            archived_at=plan_row.get("archived_at"),
            created_at=plan_row["created_at"],
            journeys=journey_models,
        )

    async def create_plan_from_optimiser(
        self,
        operating_day: date,
        routes: list[RouteModel],
    ) -> JourneyPlanModel:
        """Convert optimiser route output into a journey plan.

        Each consecutive pair of stops within a route becomes a journey,
        with departure at the previous stop's end_time and arrival at
        the next stop's arrival_time.

        Args:
            operating_day: The date the routes are planned for.
            routes: List of RouteModel objects from the optimiser.

        Returns:
            The created JourneyPlanModel with nested journeys.
        """
        # Look up patient locations for building origin/destination coordinates
        patients = await get_patients()
        patient_map = {p.id: p for p in patients}

        # Look up carer home locations for the first leg (home -> first stop)
        carers = await get_carers()
        carer_map = {c.id: c for c in carers}

        journeys: list[JourneyCreate] = []

        for route in routes:
            if not route.stops:
                continue

            carer = carer_map.get(route.carer_id)

            for i in range(len(route.stops)):
                stop = route.stops[i]

                if i == 0:
                    # First journey: from carer's home to first stop
                    origin_lat = carer.home_lat if carer else 0.0
                    origin_lng = carer.home_lng if carer else 0.0
                    origin_label = carer.name + " (Home)" if carer else None
                else:
                    # Subsequent journeys: from previous stop to current stop
                    prev_stop = route.stops[i - 1]
                    prev_patient = patient_map.get(prev_stop.patient_id)
                    origin_lat = prev_patient.lat if prev_patient else 0.0
                    origin_lng = prev_patient.lng if prev_patient else 0.0
                    origin_label = prev_patient.name if prev_patient else None

                # Destination is always the current stop's patient location
                dest_patient = patient_map.get(stop.patient_id)
                destination_lat = dest_patient.lat if dest_patient else 0.0
                destination_lng = dest_patient.lng if dest_patient else 0.0
                destination_label = dest_patient.name if dest_patient else None

                # Compute departure and arrival times
                # Departure: for the first stop, derive from arrival_time - travel_time_from_prev
                # For subsequent stops, departure is the previous stop's end_time
                if i == 0:
                    # Departure = arrival_time - travel_time_from_prev
                    arrival_dt = _parse_time_to_datetime(
                        operating_day, stop.arrival_time
                    )
                    departure_dt = arrival_dt - timedelta(
                        minutes=stop.travel_time_from_prev
                    )
                else:
                    prev_stop = route.stops[i - 1]
                    departure_dt = _parse_time_to_datetime(
                        operating_day, prev_stop.end_time
                    )
                    arrival_dt = _parse_time_to_datetime(
                        operating_day, stop.arrival_time
                    )

                journeys.append(
                    JourneyCreate(
                        carer_id=route.carer_id,
                        visit_id=stop.visit_id,
                        origin_lat=origin_lat,
                        origin_lng=origin_lng,
                        origin_label=origin_label,
                        destination_lat=destination_lat,
                        destination_lng=destination_lng,
                        destination_label=destination_label,
                        planned_departure=departure_dt,
                        planned_arrival=arrival_dt,
                        planned_distance_miles=stop.mileage_from_prev,
                    )
                )

        # Sort journeys by planned departure time within each carer's route
        journeys.sort(key=lambda j: (j.carer_id, j.planned_departure))

        # Determine creation reason: initial_creation if first plan for the day,
        # re_optimisation otherwise
        operating_day_str = operating_day.isoformat()
        latest_version = await repo.get_latest_plan_version(operating_day_str)
        reason = (
            PlanCreationReason.INITIAL_CREATION
            if latest_version == 0
            else PlanCreationReason.RE_OPTIMISATION
        )

        return await self.create_plan(
            operating_day=operating_day,
            journeys=journeys,
            reason=reason,
        )


    async def modify_journey(
        self,
        plan_id: int,
        journey_id: int,
        update: JourneyUpdate,
    ) -> JourneyPlanModel:
        """Modify a journey within a plan, creating a new plan version.

        Validates state transitions and enforces field editability rules based
        on the journey's current status. Creates a new plan version with the
        updated journey and marks the original journey as amended in the old
        plan version.

        Args:
            plan_id: The journey plan ID containing the journey.
            journey_id: The ID of the journey to modify.
            update: The partial update payload with fields to change.

        Returns:
            The new JourneyPlanModel (new plan version) with all journeys.

        Raises:
            HTTPException: 404 if journey not found, 409 if journey is in
                a terminal state or if restricted fields are changed for
                in_progress journeys.
        """
        # Get the journey from repository
        journey_row = await repo.get_journey(journey_id)
        if journey_row is None:
            raise HTTPException(status_code=404, detail="Journey not found")

        # Verify the journey belongs to the specified plan
        if journey_row["plan_id"] != plan_id:
            raise HTTPException(
                status_code=404,
                detail="Journey not found in the specified plan",
            )

        current_status = journey_row["status"]

        # Terminal states cannot be modified
        if current_status in ("completed", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot modify journey in terminal state '{current_status}'. "
                f"{'Completed' if current_status == 'completed' else 'Cancelled'} "
                "journeys cannot be amended.",
            )

        # In-progress journeys: only allow planned_arrival and destination changes
        if current_status == "in_progress":
            restricted_fields = {
                "carer_id",
                "planned_departure",
                "origin_lat",
                "origin_lng",
            }
            update_data = update.model_dump(exclude_none=True)
            violated_fields = restricted_fields & set(update_data.keys())
            if violated_fields:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot modify fields {sorted(violated_fields)} on an "
                    "in_progress journey. Only planned_arrival, destination_lat, "
                    "and destination_lng can be changed.",
                )

        # Get the current plan to determine operating day and create new version
        plan_row = await repo.get_journey_plan(plan_id)
        if plan_row is None:
            raise HTTPException(status_code=404, detail="Journey plan not found")

        operating_day_str = plan_row["operating_day"]

        # Get the next plan version number
        latest_version = await repo.get_latest_plan_version(operating_day_str)
        new_version = latest_version + 1

        # Create new plan version
        new_plan_row = await repo.create_journey_plan(
            operating_day=operating_day_str,
            creation_reason=PlanCreationReason.MANUAL_AMENDMENT.value,
            plan_version=new_version,
        )
        new_plan_id = new_plan_row["id"]

        # Get all journeys from the current plan version
        current_journeys = await repo.get_journeys_by_plan(plan_id)

        # Mark the original journey as amended in the old plan version
        await repo.update_journey_status(journey_id, "amended")

        # Copy all journeys to the new plan version, applying updates to the modified one
        update_data = update.model_dump(exclude_none=True)
        new_journey_models: list[JourneyModel] = []

        for j in current_journeys:
            # Build journey fields, applying updates to the target journey
            carer_id = j["carer_id"]
            visit_id = j.get("visit_id")
            origin_lat = j["origin_lat"]
            origin_lng = j["origin_lng"]
            origin_label = j.get("origin_label")
            destination_lat = j["destination_lat"]
            destination_lng = j["destination_lng"]
            destination_label = j.get("destination_label")
            planned_departure = j["planned_departure"]
            planned_arrival = j["planned_arrival"]
            planned_distance_miles = j["planned_distance_miles"]
            status = j["status"]

            if j["id"] == journey_id:
                # Apply update fields to this journey
                if "carer_id" in update_data:
                    carer_id = update_data["carer_id"]
                if "origin_lat" in update_data:
                    origin_lat = update_data["origin_lat"]
                if "origin_lng" in update_data:
                    origin_lng = update_data["origin_lng"]
                if "destination_lat" in update_data:
                    destination_lat = update_data["destination_lat"]
                if "destination_lng" in update_data:
                    destination_lng = update_data["destination_lng"]
                if "planned_departure" in update_data:
                    planned_departure = update_data["planned_departure"].isoformat()
                if "planned_arrival" in update_data:
                    planned_arrival = update_data["planned_arrival"].isoformat()
                # Reset status to planned for the modified journey in new version
                status = "planned"
            else:
                # For non-modified journeys, skip if they are already in a terminal state
                # that shouldn't be copied (amended journeys refer to a prior version)
                # Keep all other statuses as-is
                pass

            new_journey_row = await repo.create_journey(
                plan_id=new_plan_id,
                carer_id=carer_id,
                visit_id=visit_id,
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                origin_label=origin_label,
                destination_lat=destination_lat,
                destination_lng=destination_lng,
                destination_label=destination_label,
                planned_departure=planned_departure,
                planned_arrival=planned_arrival,
                planned_distance_miles=planned_distance_miles,
                status=status,
            )
            new_journey_models.append(_row_to_journey_model(new_journey_row))

        return JourneyPlanModel(
            id=new_plan_row["id"],
            operating_day=new_plan_row["operating_day"],
            plan_version=new_plan_row["plan_version"],
            creation_reason=PlanCreationReason(new_plan_row["creation_reason"]),
            is_archived=bool(new_plan_row["is_archived"]),
            archived_at=new_plan_row.get("archived_at"),
            created_at=new_plan_row["created_at"],
            journeys=new_journey_models,
        )

    async def cancel_journey(self, journey_id: int) -> JourneyModel:
        """Cancel a journey, creating a new plan version.

        Validates the journey exists and is in a cancellable state (planned or
        in_progress). Sets status to cancelled with a UTC timestamp. Creates a
        new plan version reflecting the cancellation. For in_progress journeys,
        marks incomplete visits as unassigned.

        Args:
            journey_id: The ID of the journey to cancel.

        Returns:
            The updated JourneyModel for the cancelled journey in the new plan version.

        Raises:
            HTTPException: 404 if journey not found, 409 if journey is in a
                terminal state (completed or already cancelled).
        """
        from backend.app.db.database import get_db

        # 1. Get the journey — raise 404 if not found
        journey_row = await repo.get_journey(journey_id)
        if journey_row is None:
            raise HTTPException(status_code=404, detail="Journey not found")

        current_status = journey_row["status"]

        # 2. Check current status
        if current_status == "completed":
            raise HTTPException(
                status_code=409,
                detail="completed Journeys cannot be cancelled",
            )
        if current_status == "cancelled":
            raise HTTPException(
                status_code=409,
                detail="Journey is already cancelled",
            )

        # 3. Record cancellation timestamp
        cancelled_at = datetime.now(timezone.utc).isoformat()

        # 4. Create new Plan_Version
        plan_id = journey_row["plan_id"]
        plan_row = await repo.get_journey_plan(plan_id)
        if plan_row is None:
            raise HTTPException(status_code=404, detail="Journey plan not found")

        operating_day_str = plan_row["operating_day"]

        # Get next plan version
        latest_version = await repo.get_latest_plan_version(operating_day_str)
        new_version = latest_version + 1

        # Create new plan version
        new_plan_row = await repo.create_journey_plan(
            operating_day=operating_day_str,
            creation_reason=PlanCreationReason.MANUAL_AMENDMENT.value,
            plan_version=new_version,
        )
        new_plan_id = new_plan_row["id"]

        # Get all journeys from the current plan version
        current_journeys = await repo.get_journeys_by_plan(plan_id)

        # 5. If in_progress: mark incomplete visits as unassigned
        if current_status == "in_progress" and journey_row.get("visit_id"):
            async with get_db() as db:
                await db.execute(
                    "UPDATE visits SET is_cancelled = 1 WHERE id = ? AND is_cancelled = 0",
                    (journey_row["visit_id"],),
                )
                await db.commit()

        # Copy all journeys to the new plan version
        # The cancelled journey gets status 'cancelled' with cancelled_at
        # Other journeys retain their current status
        cancelled_journey_model: JourneyModel | None = None

        for j in current_journeys:
            status = j["status"]
            j_cancelled_at = j.get("cancelled_at")

            if j["id"] == journey_id:
                status = "cancelled"
                j_cancelled_at = cancelled_at

            new_journey_row = await repo.create_journey(
                plan_id=new_plan_id,
                carer_id=j["carer_id"],
                visit_id=j.get("visit_id"),
                origin_lat=j["origin_lat"],
                origin_lng=j["origin_lng"],
                origin_label=j.get("origin_label"),
                destination_lat=j["destination_lat"],
                destination_lng=j["destination_lng"],
                destination_label=j.get("destination_label"),
                planned_departure=j["planned_departure"],
                planned_arrival=j["planned_arrival"],
                planned_distance_miles=j["planned_distance_miles"],
                status=status,
            )

            # If this is the cancelled journey, update it with the cancelled_at timestamp
            if j["id"] == journey_id:
                await repo.update_journey_status(
                    new_journey_row["id"], "cancelled", cancelled_at=j_cancelled_at
                )
                # Re-fetch to get updated row
                updated_row = await repo.get_journey(new_journey_row["id"])
                cancelled_journey_model = _row_to_journey_model(updated_row)

        return cancelled_journey_model

    async def delete_plan(self, plan_id: int) -> DeleteConfirmation:
        """Delete (archive) a journey plan after validation checks.

        Validates that:
        - The plan exists (404 if not found)
        - The plan's operating_day is not in the past (409 if past)
        - The plan is not today's only plan (409 if so)
        - No journeys have in_progress or completed status (409 with IDs)

        On success, performs a soft-delete by archiving the plan with a UTC timestamp.

        Args:
            plan_id: The unique identifier of the journey plan to delete.

        Returns:
            A DeleteConfirmation with the plan_id and count of journeys removed.

        Raises:
            HTTPException: 404 if plan not found, 409 for business rule violations.
        """
        # 1. Get the plan — 404 if not found
        plan = await repo.get_journey_plan(plan_id)
        if plan is None:
            raise HTTPException(
                status_code=404,
                detail="The specified Journey_Plan was not found.",
            )

        # 2. Check the operating_day date constraints
        today = date.today()
        operating_day = date.fromisoformat(plan["operating_day"])

        if operating_day < today:
            raise HTTPException(
                status_code=409,
                detail="Past journey plans cannot be deleted.",
            )

        if operating_day == today:
            # Check if this is the only plan for today (non-archived)
            plans_for_today = await repo.list_journey_plans(
                operating_day=plan["operating_day"], include_archived=False
            )
            if len(plans_for_today) <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="Active day plan cannot be deleted.",
                )

        # 3. Check for active journeys (in_progress or completed)
        journeys = await repo.get_journeys_by_plan(plan_id)
        blocking_ids = [
            j["id"]
            for j in journeys
            if j["status"]
            in (JourneyStatus.IN_PROGRESS.value, JourneyStatus.COMPLETED.value)
        ]

        if blocking_ids:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete plan: journeys {blocking_ids} have active status.",
            )

        # 4. Archive the plan with current UTC timestamp
        archived_at = datetime.now(timezone.utc).isoformat()
        await repo.archive_journey_plan(plan_id, archived_at)

        return DeleteConfirmation(
            plan_id=plan_id,
            journeys_removed=len(journeys),
        )


    async def receive_actual(self, data: ActualJourneyCreate) -> ActualJourneyModel:
        """Receive actual journey data from the field.

        Validates input, matches to a planned journey using carer ID + operating
        day + 60-minute departure window, creates an actual journey record, and
        triggers the appropriate state transition on the matched planned journey.

        Args:
            data: The actual journey data payload.

        Returns:
            The created ActualJourneyModel.

        Raises:
            HTTPException: 422 if validation fails (invalid carer, arrival <= departure).
        """
        import json

        # 1. Validate carer_id exists
        carers = await get_carers()
        carer_ids = {c.id for c in carers}
        if data.carer_id not in carer_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Carer with id {data.carer_id} does not exist.",
            )

        # 2. Validate actual_arrival > actual_departure
        if data.actual_arrival <= data.actual_departure:
            raise HTTPException(
                status_code=422,
                detail="Actual arrival time must be strictly later than actual departure time.",
            )

        # 3. Match to planned journey
        operating_day_str = data.operating_day.isoformat()
        actual_departure_str = data.actual_departure.isoformat()

        matched_journey = await repo.find_matching_planned_journey(
            carer_id=data.carer_id,
            operating_day=operating_day_str,
            actual_departure=actual_departure_str,
        )

        if matched_journey:
            match_status = MatchStatus.MATCHED
            journey_id = matched_journey["id"]
        else:
            match_status = MatchStatus.UNMATCHED
            journey_id = None

        # 4. Create actual journey record
        route_coords_json = json.dumps(data.route_coordinates)
        actual_row = await repo.create_actual_journey(
            journey_id=journey_id,
            carer_id=data.carer_id,
            operating_day=operating_day_str,
            actual_departure=actual_departure_str,
            actual_arrival=data.actual_arrival.isoformat(),
            actual_distance_miles=round(data.actual_distance_miles, 1),
            route_coordinates=route_coords_json,
            match_status=match_status.value,
        )

        # 5. State transition on matched planned journey
        if matched_journey:
            current_status = matched_journey["status"]
            if current_status == JourneyStatus.PLANNED.value:
                # Departure received → transition to in_progress
                await repo.update_journey_status(journey_id, JourneyStatus.IN_PROGRESS.value)
            elif current_status == JourneyStatus.IN_PROGRESS.value:
                # Arrival received → transition to completed
                await repo.update_journey_status(journey_id, JourneyStatus.COMPLETED.value)

        # 6. Build and return ActualJourneyModel
        return ActualJourneyModel(
            id=actual_row["id"],
            journey_id=actual_row.get("journey_id"),
            carer_id=actual_row["carer_id"],
            operating_day=actual_row["operating_day"],
            actual_departure=actual_row["actual_departure"],
            actual_arrival=actual_row["actual_arrival"],
            actual_distance_miles=actual_row["actual_distance_miles"],
            route_coordinates=json.loads(actual_row["route_coordinates"]),
            match_status=MatchStatus(actual_row["match_status"]),
            created_at=actual_row["created_at"],
        )


    async def check_overdue_journeys(self) -> list[int]:
        """Check for in_progress journeys that have exceeded the 4-hour timeout.

        Finds all journeys with status 'in_progress' whose actual departure was
        more than 4 hours ago and flags them as 'overdue'.

        Returns:
            A list of journey IDs that were transitioned to overdue status.
        """
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        overdue_journeys = await repo.get_overdue_in_progress_journeys(cutoff_time)

        flagged_ids: list[int] = []
        for journey in overdue_journeys:
            await repo.update_journey_status(journey["id"], JourneyStatus.OVERDUE.value)
            flagged_ids.append(journey["id"])

        return flagged_ids

    async def get_comparison(
        self, operating_day: date, plan_version: int | None = None
    ) -> ComparisonResult:
        """Compare planned journeys with actuals for an operating day.

        Pairs planned journeys with their corresponding actual journeys,
        calculates variance (departure/arrival in minutes, distance in miles),
        groups results by carer, and orders by departure time.

        Args:
            operating_day: The date to compare.
            plan_version: If specified, use this plan version; otherwise use latest.

        Returns:
            A ComparisonResult with entries grouped by carer.
        """
        import json

        operating_day_str = operating_day.isoformat()

        # 1. Get the plan for the operating day
        if plan_version is not None:
            # Use specified plan version
            plans = await repo.list_journey_plans(
                operating_day=operating_day_str, include_archived=False
            )
            plan = next(
                (p for p in plans if p["plan_version"] == plan_version), None
            )
        else:
            # Use latest plan version
            plans = await repo.list_journey_plans(
                operating_day=operating_day_str, include_archived=False
            )
            plan = plans[-1] if plans else None

        # 2. Get all actual journeys for the operating day
        actuals = await repo.get_actual_journeys_by_day(operating_day_str)

        # If no plan and no actuals, return empty result with message
        if plan is None and not actuals:
            return ComparisonResult(
                operating_day=operating_day_str,
                plan_version=0,
                entries_by_carer={},
                message="No data is available for that date",
            )

        # 3. Get all journeys from the selected plan version
        planned_journeys: list[dict] = []
        used_plan_version = 0
        if plan is not None:
            planned_journeys = await repo.get_journeys_by_plan(plan["id"])
            used_plan_version = plan["plan_version"]

        # 4. Build a lookup of actual journeys keyed by journey_id
        actuals_by_journey_id: dict[int, dict] = {}
        unmatched_actuals: list[dict] = []
        for actual in actuals:
            journey_id = actual.get("journey_id")
            if journey_id is not None:
                actuals_by_journey_id[journey_id] = actual
            else:
                unmatched_actuals.append(actual)

        # 5. Pair planned journeys with actuals and calculate variance
        entries_by_carer: dict[int, list[ComparisonEntry]] = {}

        # Track which actuals have been matched to planned journeys in this plan
        matched_actual_journey_ids: set[int] = set()

        for pj in planned_journeys:
            carer_id = pj["carer_id"]
            planned_model = _row_to_journey_model(pj)

            # Check if there's a matching actual for this planned journey
            actual_row = actuals_by_journey_id.get(pj["id"])

            if actual_row is not None:
                matched_actual_journey_ids.add(actual_row["id"])
                actual_model = _row_to_actual_model(actual_row)

                # Calculate variance
                planned_dep = datetime.fromisoformat(pj["planned_departure"])
                planned_arr = datetime.fromisoformat(pj["planned_arrival"])
                actual_dep = datetime.fromisoformat(actual_row["actual_departure"])
                actual_arr = datetime.fromisoformat(actual_row["actual_arrival"])

                departure_variance_minutes = int(
                    (actual_dep - planned_dep).total_seconds() / 60
                )
                arrival_variance_minutes = int(
                    (actual_arr - planned_arr).total_seconds() / 60
                )
                distance_variance_miles = round(
                    actual_row["actual_distance_miles"]
                    - pj["planned_distance_miles"],
                    1,
                )

                variance = VarianceModel(
                    departure_variance_minutes=departure_variance_minutes,
                    arrival_variance_minutes=arrival_variance_minutes,
                    distance_variance_miles=distance_variance_miles,
                )

                entry = ComparisonEntry(
                    planned_journey=planned_model,
                    actual_journey=actual_model,
                    variance=variance,
                    match_status=MatchStatus.MATCHED,
                )
            else:
                # Unstarted planned journey - no matching actual
                entry = ComparisonEntry(
                    planned_journey=planned_model,
                    actual_journey=None,
                    variance=None,
                    match_status=MatchStatus.UNSTARTED,
                )

            if carer_id not in entries_by_carer:
                entries_by_carer[carer_id] = []
            entries_by_carer[carer_id].append(entry)

        # 6. Handle unplanned actuals (actuals with no matching planned journey)
        # Include unmatched actuals AND actuals matched to journeys NOT in this plan
        for actual in actuals:
            if actual["id"] in matched_actual_journey_ids:
                continue
            # Check if this actual's journey_id belongs to a journey in the current plan
            if actual.get("journey_id") is not None:
                planned_ids = {pj["id"] for pj in planned_journeys}
                if actual["journey_id"] in planned_ids:
                    continue

            carer_id = actual["carer_id"]
            actual_model = _row_to_actual_model(actual)

            entry = ComparisonEntry(
                planned_journey=None,
                actual_journey=actual_model,
                variance=None,
                match_status=MatchStatus.UNPLANNED,
            )

            if carer_id not in entries_by_carer:
                entries_by_carer[carer_id] = []
            entries_by_carer[carer_id].append(entry)

        # 7. Order entries within each group by planned_departure ascending
        for carer_id in entries_by_carer:
            entries_by_carer[carer_id].sort(
                key=lambda e: (
                    e.planned_journey.planned_departure
                    if e.planned_journey
                    else e.actual_journey.actual_departure
                    if e.actual_journey
                    else ""
                )
            )

        return ComparisonResult(
            operating_day=operating_day_str,
            plan_version=used_plan_version,
            entries_by_carer=entries_by_carer,
        )

    async def query_journeys(
        self, filters: JourneyFilters, page: int = 1, page_size: int = 20
    ) -> PaginatedResult:
        """Query journeys with filters and pagination.

        Validates pagination parameters and filter values, then delegates to
        the repository layer. Uses the latest plan version per operating day.

        Args:
            filters: Filter criteria (operating_day, carer_id, status).
            page: Page number (1-indexed, minimum 1).
            page_size: Number of results per page (1-100, default 20).

        Returns:
            A PaginatedResult with matching journeys and total count.

        Raises:
            HTTPException: 422 if pagination params or filter values are invalid.
        """
        # 1. Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=422,
                detail="Page number must be at least 1.",
            )
        if page_size < 1 or page_size > 100:
            raise HTTPException(
                status_code=422,
                detail="Page size must be between 1 and 100.",
            )

        # 2. Validate filters
        if filters.status is not None:
            valid_statuses = {s.value for s in JourneyStatus}
            if filters.status.value not in valid_statuses:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid status filter: '{filters.status.value}'. "
                    f"Must be one of: {sorted(valid_statuses)}.",
                )

        if filters.carer_id is not None:
            carers = await get_carers()
            carer_ids = {c.id for c in carers}
            if filters.carer_id not in carer_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid carer_id filter: carer with id {filters.carer_id} does not exist.",
                )

        if filters.operating_day is not None:
            # operating_day is already a date object from Pydantic validation,
            # so if we get here it's a valid date. No additional validation needed.
            pass

        # 3. Call repository with filter values
        operating_day_str = (
            filters.operating_day.isoformat() if filters.operating_day else None
        )
        status_str = filters.status.value if filters.status else None

        rows, total_count = await repo.query_journeys(
            operating_day=operating_day_str,
            carer_id=filters.carer_id,
            status=status_str,
            page=page,
            page_size=page_size,
        )

        # 4. Convert rows to JourneyModel list
        journeys = [_row_to_journey_model(row) for row in rows]

        # 5. Return PaginatedResult
        return PaginatedResult(
            total_count=total_count,
            page=page,
            page_size=page_size,
            journeys=journeys,
        )

    async def get_history(self, operating_day: date) -> list[JourneyPlanModel]:
        """Get all plan versions for an operating day in chronological order.

        Retrieves all plan versions (including archived) for the specified
        operating day and returns them ordered by plan_version ascending.

        Args:
            operating_day: The date to retrieve history for.

        Returns:
            A list of JourneyPlanModel ordered by plan_version ascending.
        """
        operating_day_str = operating_day.isoformat()

        # Get all plan versions for this day including archived
        plans = await repo.list_journey_plans(
            operating_day=operating_day_str, include_archived=True
        )

        # Build full JourneyPlanModel for each plan with its journeys
        result: list[JourneyPlanModel] = []
        for plan in plans:
            journeys = await repo.get_journeys_by_plan(plan["id"])
            journey_models = [_row_to_journey_model(j) for j in journeys]

            result.append(
                JourneyPlanModel(
                    id=plan["id"],
                    operating_day=plan["operating_day"],
                    plan_version=plan["plan_version"],
                    creation_reason=PlanCreationReason(plan["creation_reason"]),
                    is_archived=bool(plan["is_archived"]),
                    archived_at=plan.get("archived_at"),
                    created_at=plan["created_at"],
                    journeys=journey_models,
                )
            )

        # Sort by plan_version ascending (chronological order)
        result.sort(key=lambda p: p.plan_version)

        return result

    async def get_date_range_summary(
        self, start: date, end: date
    ) -> list[DaySummary]:
        """Get summary stats for each day in a date range.

        Validates the date range (start <= end, max 90 days), then for each
        day computes plan version count, total planned/completed journeys,
        and average departure/distance variance.

        Args:
            start: Start date of the range (inclusive).
            end: End date of the range (inclusive).

        Returns:
            A list of DaySummary for each day that has data.

        Raises:
            HTTPException: 422 if start > end or range exceeds 90 days.
        """
        # Validate: start <= end
        if start > end:
            raise HTTPException(
                status_code=422,
                detail="Start date must be on or before end date.",
            )

        # Validate: range <= 90 days
        if (end - start).days > 90:
            raise HTTPException(
                status_code=422,
                detail="Date range must not exceed 90 days.",
            )

        summaries: list[DaySummary] = []

        # Iterate through each day in the range
        current = start
        while current <= end:
            current_str = current.isoformat()

            # Get all plan versions for this day (including archived)
            plans = await repo.list_journey_plans(
                operating_day=current_str, include_archived=True
            )

            if plans:
                plan_version_count = len(plans)

                # Get journeys from the latest plan version
                latest_plan = max(plans, key=lambda p: p["plan_version"])
                latest_journeys = await repo.get_journeys_by_plan(latest_plan["id"])
                total_planned_journeys = len(latest_journeys)

                # Get actual journeys for this day
                actuals = await repo.get_actual_journeys_by_day(current_str)
                total_completed_journeys = len(actuals)

                # Calculate average variances across matched pairs
                departure_variances: list[float] = []
                distance_variances: list[float] = []

                # Build lookup of planned journeys by ID for variance calc
                planned_by_id = {j["id"]: j for j in latest_journeys}

                for actual in actuals:
                    journey_id = actual.get("journey_id")
                    if journey_id is not None and journey_id in planned_by_id:
                        planned = planned_by_id[journey_id]

                        # Departure variance in minutes
                        planned_dep = datetime.fromisoformat(
                            planned["planned_departure"]
                        )
                        actual_dep = datetime.fromisoformat(
                            actual["actual_departure"]
                        )
                        dep_variance = (
                            actual_dep - planned_dep
                        ).total_seconds() / 60
                        departure_variances.append(dep_variance)

                        # Distance variance in miles
                        dist_variance = (
                            actual["actual_distance_miles"]
                            - planned["planned_distance_miles"]
                        )
                        distance_variances.append(dist_variance)

                avg_departure_variance_minutes = (
                    round(
                        sum(departure_variances) / len(departure_variances), 1
                    )
                    if departure_variances
                    else None
                )
                avg_distance_variance_miles = (
                    round(
                        sum(distance_variances) / len(distance_variances), 1
                    )
                    if distance_variances
                    else None
                )

                summaries.append(
                    DaySummary(
                        operating_day=current_str,
                        plan_version_count=plan_version_count,
                        total_planned_journeys=total_planned_journeys,
                        total_completed_journeys=total_completed_journeys,
                        avg_departure_variance_minutes=avg_departure_variance_minutes,
                        avg_distance_variance_miles=avg_distance_variance_miles,
                    )
                )

            current += timedelta(days=1)

        return summaries


def _parse_time_to_datetime(day: date, time_str: str) -> datetime:
    """Convert a HH:MM time string to a full datetime on the given day.

    Args:
        day: The operating day date.
        time_str: Time in HH:MM format.

    Returns:
        A datetime combining the day and time.
    """
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1])
    return datetime(day.year, day.month, day.day, hour, minute)


def _row_to_journey_model(row: dict) -> JourneyModel:
    """Convert a raw database row dict to a JourneyModel.

    Args:
        row: Dictionary with journey column data.

    Returns:
        A JourneyModel instance.
    """
    return JourneyModel(
        id=row["id"],
        plan_id=row["plan_id"],
        carer_id=row["carer_id"],
        visit_id=row.get("visit_id"),
        origin_lat=row["origin_lat"],
        origin_lng=row["origin_lng"],
        origin_label=row.get("origin_label"),
        destination_lat=row["destination_lat"],
        destination_lng=row["destination_lng"],
        destination_label=row.get("destination_label"),
        planned_departure=row["planned_departure"],
        planned_arrival=row["planned_arrival"],
        planned_distance_miles=row["planned_distance_miles"],
        status=JourneyStatus(row["status"]),
        cancelled_at=row.get("cancelled_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_actual_model(row: dict) -> ActualJourneyModel:
    """Convert a raw database row dict to an ActualJourneyModel.

    Args:
        row: Dictionary with actual journey column data.

    Returns:
        An ActualJourneyModel instance.
    """
    import json

    route_coordinates = row.get("route_coordinates", "[]")
    if isinstance(route_coordinates, str):
        route_coordinates = json.loads(route_coordinates)

    return ActualJourneyModel(
        id=row["id"],
        journey_id=row.get("journey_id"),
        carer_id=row["carer_id"],
        operating_day=row["operating_day"],
        actual_departure=row["actual_departure"],
        actual_arrival=row["actual_arrival"],
        actual_distance_miles=row["actual_distance_miles"],
        route_coordinates=route_coordinates,
        match_status=MatchStatus(row["match_status"]),
        created_at=row["created_at"],
    )
