"""Data access layer for Journey Lifecycle Management entities."""

from backend.app.db.database import get_db


# --- Journey Plan operations ---


async def create_journey_plan(
    operating_day: str, creation_reason: str, plan_version: int
) -> dict:
    """Create a new journey plan record.

    Args:
        operating_day: The operating day in YYYY-MM-DD format.
        creation_reason: One of 'initial_creation', 'manual_amendment', 're_optimisation'.
        plan_version: The version number for this plan.

    Returns:
        The newly created journey plan row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO journey_plans (operating_day, plan_version, creation_reason)
               VALUES (?, ?, ?)""",
            (operating_day, plan_version, creation_reason),
        )
        await db.commit()

        # Return the created record
        new_cursor = await db.execute(
            "SELECT * FROM journey_plans WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_journey_plan(plan_id: int) -> dict | None:
    """Retrieve a single journey plan by ID.

    Args:
        plan_id: The unique identifier of the journey plan.

    Returns:
        The journey plan row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM journey_plans WHERE id = ?", (plan_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def list_journey_plans(
    operating_day: str | None = None, include_archived: bool = False
) -> list[dict]:
    """List journey plans with optional filters.

    Args:
        operating_day: If provided, filter by this operating day.
        include_archived: If False (default), exclude archived plans.

    Returns:
        A list of journey plan rows as dicts.
    """
    async with get_db() as db:
        conditions = []
        params: list = []

        if not include_archived:
            conditions.append("is_archived = 0")

        if operating_day is not None:
            conditions.append("operating_day = ?")
            params.append(operating_day)

        query = "SELECT * FROM journey_plans"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY operating_day, plan_version"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_latest_plan_version(operating_day: str) -> int:
    """Get the highest plan version number for an operating day.

    Args:
        operating_day: The operating day in YYYY-MM-DD format.

    Returns:
        The maximum plan_version for the operating day, or 0 if none exist.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT MAX(plan_version) as max_version FROM journey_plans WHERE operating_day = ?",
            (operating_day,),
        )
        row = await cursor.fetchone()
        max_version = row["max_version"]
        return max_version if max_version is not None else 0


async def archive_journey_plan(plan_id: int, archived_at: str) -> bool:
    """Archive a journey plan by setting is_archived=1 and recording the archive timestamp.

    Args:
        plan_id: The unique identifier of the journey plan to archive.
        archived_at: The UTC ISO 8601 timestamp of archival.

    Returns:
        True if the row was updated, False if the plan was not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE journey_plans SET is_archived = 1, archived_at = ? WHERE id = ?",
            (archived_at, plan_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_archived_plans(operating_day: str | None = None) -> list[dict]:
    """Retrieve archived journey plans.

    Args:
        operating_day: If provided, filter archived plans by this operating day.

    Returns:
        A list of archived journey plan rows as dicts.
    """
    async with get_db() as db:
        conditions = ["is_archived = 1"]
        params: list = []

        if operating_day is not None:
            conditions.append("operating_day = ?")
            params.append(operating_day)

        query = "SELECT * FROM journey_plans WHERE " + " AND ".join(conditions)
        query += " ORDER BY operating_day, plan_version"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# --- Actual Journey operations ---


async def create_actual_journey(
    journey_id: int | None,
    carer_id: int,
    operating_day: str,
    actual_departure: str,
    actual_arrival: str,
    actual_distance_miles: float,
    route_coordinates: str,
    match_status: str = "matched",
) -> dict:
    """Create a new actual journey record.

    Args:
        journey_id: The matched planned journey ID, or None if unmatched.
        carer_id: The carer who performed the journey.
        operating_day: The operating day in YYYY-MM-DD format.
        actual_departure: ISO 8601 datetime of actual departure.
        actual_arrival: ISO 8601 datetime of actual arrival.
        actual_distance_miles: Distance travelled in miles.
        route_coordinates: JSON string of [lat, lng] coordinate pairs.
        match_status: One of 'matched' or 'unmatched'.

    Returns:
        The newly created actual journey row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO actual_journeys
               (journey_id, carer_id, operating_day, actual_departure,
                actual_arrival, actual_distance_miles, route_coordinates, match_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                journey_id,
                carer_id,
                operating_day,
                actual_departure,
                actual_arrival,
                actual_distance_miles,
                route_coordinates,
                match_status,
            ),
        )
        await db.commit()

        # Return the created record
        new_cursor = await db.execute(
            "SELECT * FROM actual_journeys WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_actual_journeys_by_day(operating_day: str) -> list[dict]:
    """Retrieve all actual journeys for a given operating day.

    Args:
        operating_day: The operating day in YYYY-MM-DD format.

    Returns:
        A list of actual journey rows as dicts.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM actual_journeys WHERE operating_day = ? ORDER BY actual_departure",
            (operating_day,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_actual_journey_by_journey_id(journey_id: int) -> dict | None:
    """Retrieve an actual journey matched to a specific planned journey ID.

    Args:
        journey_id: The planned journey ID to look up.

    Returns:
        The actual journey row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM actual_journeys WHERE journey_id = ?", (journey_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def find_matching_planned_journey(
    carer_id: int, operating_day: str, actual_departure: str
) -> dict | None:
    """Find the best matching planned journey for an actual journey.

    Uses carer_id + operating_day + 60-minute departure window to find the
    closest planned journey. Only considers journeys with status 'planned'
    from the latest plan version for the operating day.

    Args:
        carer_id: The carer ID to match.
        operating_day: The operating day in YYYY-MM-DD format.
        actual_departure: ISO 8601 datetime of actual departure.

    Returns:
        The closest matching planned journey row as a dict, or None if no match.
    """
    async with get_db() as db:
        # Find the latest plan version for this operating day
        version_cursor = await db.execute(
            """SELECT MAX(plan_version) as max_version
               FROM journey_plans
               WHERE operating_day = ? AND is_archived = 0""",
            (operating_day,),
        )
        version_row = await version_cursor.fetchone()
        max_version = version_row["max_version"] if version_row else None

        if max_version is None:
            return None

        # Find journeys for this carer on this operating day from the latest plan version,
        # within 60 minutes of the actual departure, ordered by closest departure time.
        # Match both 'planned' and 'in_progress' statuses to support departure and arrival reception.
        cursor = await db.execute(
            """SELECT j.* FROM journeys j
               INNER JOIN journey_plans jp ON j.plan_id = jp.id
               WHERE j.carer_id = ?
                 AND jp.operating_day = ?
                 AND jp.plan_version = ?
                 AND jp.is_archived = 0
                 AND j.status IN ('planned', 'in_progress')
                 AND ABS(julianday(j.planned_departure) - julianday(?)) * 24 * 60 <= 60
               ORDER BY ABS(julianday(j.planned_departure) - julianday(?)) ASC
               LIMIT 1""",
            (carer_id, operating_day, max_version, actual_departure, actual_departure),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


# --- Journey operations ---


async def create_journey(
    plan_id: int,
    carer_id: int,
    visit_id: int | None,
    origin_lat: float,
    origin_lng: float,
    origin_label: str | None,
    destination_lat: float,
    destination_lng: float,
    destination_label: str | None,
    planned_departure: str,
    planned_arrival: str,
    planned_distance_miles: float,
    status: str = "planned",
) -> dict:
    """Create a new journey record within a plan.

    Args:
        plan_id: The journey plan this journey belongs to.
        carer_id: The assigned carer's identifier.
        visit_id: The associated visit identifier (None for home legs).
        origin_lat: Origin latitude.
        origin_lng: Origin longitude.
        origin_label: Human-readable origin name.
        destination_lat: Destination latitude.
        destination_lng: Destination longitude.
        destination_label: Human-readable destination name.
        planned_departure: ISO 8601 datetime for planned departure.
        planned_arrival: ISO 8601 datetime for planned arrival.
        planned_distance_miles: Planned distance in miles.
        status: Initial journey status (default 'planned').

    Returns:
        The newly created journey row as a dict.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO journeys
               (plan_id, carer_id, visit_id, origin_lat, origin_lng, origin_label,
                destination_lat, destination_lng, destination_label,
                planned_departure, planned_arrival, planned_distance_miles, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_id,
                carer_id,
                visit_id,
                origin_lat,
                origin_lng,
                origin_label,
                destination_lat,
                destination_lng,
                destination_label,
                planned_departure,
                planned_arrival,
                planned_distance_miles,
                status,
            ),
        )
        await db.commit()

        new_cursor = await db.execute(
            "SELECT * FROM journeys WHERE id = ?", (cursor.lastrowid,)
        )
        row = await new_cursor.fetchone()
        return dict(row)


async def get_journey(journey_id: int) -> dict | None:
    """Retrieve a single journey by ID.

    Args:
        journey_id: The unique identifier of the journey.

    Returns:
        The journey row as a dict, or None if not found.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM journeys WHERE id = ?", (journey_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def update_journey_status(
    journey_id: int, status: str, cancelled_at: str | None = None
) -> None:
    """Update a journey's status and optionally its cancelled_at timestamp.

    Sets updated_at to the current time.

    Args:
        journey_id: The unique identifier of the journey.
        status: The new status value.
        cancelled_at: UTC ISO 8601 cancellation timestamp (if applicable).

    Raises:
        KeyError: If the journey with the given ID does not exist.
    """
    async with get_db() as db:
        from datetime import datetime

        # Check existence first
        cursor = await db.execute(
            "SELECT id FROM journeys WHERE id = ?", (journey_id,)
        )
        if not await cursor.fetchone():
            raise KeyError(f"Journey with id {journey_id} not found")

        now = datetime.now().isoformat()

        if cancelled_at is not None:
            await db.execute(
                """UPDATE journeys
                   SET status = ?, cancelled_at = ?, updated_at = ?
                   WHERE id = ?""",
                (status, cancelled_at, now, journey_id),
            )
        else:
            await db.execute(
                """UPDATE journeys
                   SET status = ?, updated_at = ?
                   WHERE id = ?""",
                (status, now, journey_id),
            )
        await db.commit()


async def get_journeys_by_plan(plan_id: int) -> list[dict]:
    """Retrieve all journeys for a given plan, ordered by planned departure ascending.

    Args:
        plan_id: The journey plan identifier.

    Returns:
        A list of journey rows as dicts ordered by planned_departure ASC.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM journeys WHERE plan_id = ? ORDER BY planned_departure ASC",
            (plan_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def query_journeys(
    operating_day: str | None = None,
    carer_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Query journeys with dynamic filters and pagination.

    Uses the latest plan_version per operating_day to select journeys.

    Args:
        operating_day: Filter by operating day (YYYY-MM-DD).
        carer_id: Filter by carer identifier.
        status: Filter by journey status.
        page: Page number (1-indexed).
        page_size: Number of results per page.

    Returns:
        A tuple of (list of journey dicts, total_count).
    """
    async with get_db() as db:
        # Build the base query using latest plan version per operating day
        # Subquery: get the latest plan_id per operating_day (non-archived)
        base_query = """
            SELECT j.* FROM journeys j
            INNER JOIN journey_plans jp ON j.plan_id = jp.id
            WHERE jp.is_archived = 0
              AND jp.id IN (
                  SELECT jp2.id FROM journey_plans jp2
                  WHERE jp2.is_archived = 0
                    AND jp2.plan_version = (
                        SELECT MAX(jp3.plan_version)
                        FROM journey_plans jp3
                        WHERE jp3.operating_day = jp2.operating_day
                          AND jp3.is_archived = 0
                    )
              )
        """

        conditions: list[str] = []
        params: list = []

        if operating_day is not None:
            conditions.append("jp.operating_day = ?")
            params.append(operating_day)

        if carer_id is not None:
            conditions.append("j.carer_id = ?")
            params.append(carer_id)

        if status is not None:
            conditions.append("j.status = ?")
            params.append(status)

        where_clause = ""
        if conditions:
            where_clause = " AND " + " AND ".join(conditions)

        # Count query
        count_query = f"""
            SELECT COUNT(*) as cnt FROM journeys j
            INNER JOIN journey_plans jp ON j.plan_id = jp.id
            WHERE jp.is_archived = 0
              AND jp.id IN (
                  SELECT jp2.id FROM journey_plans jp2
                  WHERE jp2.is_archived = 0
                    AND jp2.plan_version = (
                        SELECT MAX(jp3.plan_version)
                        FROM journey_plans jp3
                        WHERE jp3.operating_day = jp2.operating_day
                          AND jp3.is_archived = 0
                    )
              )
            {where_clause}
        """

        cursor = await db.execute(count_query, params)
        count_row = await cursor.fetchone()
        total_count = count_row["cnt"]

        # Data query with pagination
        offset = (page - 1) * page_size
        data_query = f"""
            {base_query}
            {where_clause}
            ORDER BY j.planned_departure DESC
            LIMIT ? OFFSET ?
        """

        cursor = await db.execute(data_query, params + [page_size, offset])
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total_count


async def get_overdue_in_progress_journeys(cutoff_time: str) -> list[dict]:
    """Retrieve in_progress journeys whose matched actual departure is before the cutoff time.

    This finds journeys that have been in_progress for longer than expected
    (i.e., the actual departure was before cutoff_time, indicating >4 hours have passed).

    Args:
        cutoff_time: ISO 8601 datetime. Journeys with actual departure before this
                     time and still in_progress are considered overdue.

    Returns:
        A list of journey rows as dicts that are overdue.
    """
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT j.* FROM journeys j
               INNER JOIN actual_journeys aj ON aj.journey_id = j.id
               WHERE j.status = 'in_progress'
                 AND aj.actual_departure < ?
               ORDER BY aj.actual_departure ASC""",
            (cutoff_time,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_journeys_by_carer(carer_id: int) -> list[dict]:
    """Retrieve all journeys for a specific carer across all operating days.

    Uses the latest plan version per operating day. Results are ordered by
    planned_departure descending.

    Args:
        carer_id: The carer identifier.

    Returns:
        A list of journey dicts ordered by planned_departure DESC.
    """
    async with get_db() as db:
        data_query = """
            SELECT j.* FROM journeys j
            INNER JOIN journey_plans jp ON j.plan_id = jp.id
            WHERE j.carer_id = ?
              AND jp.is_archived = 0
              AND jp.id IN (
                  SELECT jp2.id FROM journey_plans jp2
                  WHERE jp2.is_archived = 0
                    AND jp2.plan_version = (
                        SELECT MAX(jp3.plan_version)
                        FROM journey_plans jp3
                        WHERE jp3.operating_day = jp2.operating_day
                          AND jp3.is_archived = 0
                    )
              )
            ORDER BY j.planned_departure DESC
        """

        cursor = await db.execute(data_query, (carer_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
