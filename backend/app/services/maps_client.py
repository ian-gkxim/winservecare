"""Google Maps Distance Matrix API client for travel time/distance computation."""

import asyncio
import logging
from typing import Optional

import googlemaps
from googlemaps.exceptions import ApiError, TransportError, Timeout

from backend.app.db.repositories import get_config
from backend.app.models.optimisation import TravelTimeMatrix

logger = logging.getLogger(__name__)

# Type alias for a geographic location (latitude, longitude)
Location = tuple[float, float]


class MapsAPIError(Exception):
    """Custom exception for Google Maps API failures.

    Raised when the Distance Matrix API returns an error, times out,
    or returns partial failures (unresolvable origin-destination pairs).
    """

    def __init__(self, message: str, failed_pairs: list[tuple[int, int]] | None = None):
        super().__init__(message)
        self.message = message
        self.failed_pairs = failed_pairs or []


class GoogleMapsClient:
    """Async-friendly client for the Google Maps Distance Matrix API.

    Wraps the synchronous `googlemaps` Python library using asyncio.wait_for
    and asyncio.to_thread to avoid blocking the event loop. Fetches the API
    key from the database config table on each call to support runtime key
    updates, unless an explicit key is provided at construction.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialise the client with an optional API key.

        Args:
            api_key: Google Maps API key. If not provided, will be fetched
                     from application config on each call.
        """
        self._api_key = api_key

    async def get_distance_matrix(
        self,
        origins: list[Location],
        destinations: list[Location],
        mode: str = "driving",
        timeout: float = 30.0,
    ) -> TravelTimeMatrix:
        """Fetch travel time/distance matrix from the Distance Matrix API.

        Args:
            origins: List of (lat, lng) tuples for origin locations.
            destinations: List of (lat, lng) tuples for destination locations.
            mode: Travel mode (default "driving").
            timeout: Request timeout in seconds (default 30).

        Returns:
            TravelTimeMatrix with durations (seconds) and distances (metres).

        Raises:
            MapsAPIError: On API key missing, API errors, timeouts, or
                partial failures where some pairs cannot be resolved.
        """
        # Retrieve the API key
        api_key = await self._get_api_key()

        # Format locations as "lat,lng" strings for the API
        origin_strings = [f"{lat},{lng}" for lat, lng in origins]
        destination_strings = [f"{lat},{lng}" for lat, lng in destinations]

        # Call the Google Maps API in a thread with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._call_distance_matrix,
                    api_key=api_key,
                    origins=origin_strings,
                    destinations=destination_strings,
                    mode=mode,
                    timeout=timeout,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise MapsAPIError(
                f"Google Maps Distance Matrix API request timed out after {timeout} seconds"
            )

        # Validate top-level API response status
        status = result.get("status", "UNKNOWN")
        if status != "OK":
            raise MapsAPIError(
                f"Distance Matrix API returned top-level error status: {status}"
            )

        # Parse response and check for partial failures
        rows = result.get("rows", [])
        durations: list[list[int]] = []
        distances: list[list[int]] = []
        failed_pairs: list[tuple[int, int]] = []
        failed_descriptions: list[str] = []

        for i, row in enumerate(rows):
            duration_row: list[int] = []
            distance_row: list[int] = []
            elements = row.get("elements", [])

            for j, element in enumerate(elements):
                element_status = element.get("status", "UNKNOWN")

                if element_status == "OK":
                    duration_row.append(element["duration"]["value"])
                    distance_row.append(element["distance"]["value"])
                else:
                    # Mark as failed pair with placeholder values
                    duration_row.append(-1)
                    distance_row.append(-1)
                    failed_pairs.append((i, j))
                    failed_descriptions.append(
                        f"origin[{i}] -> destination[{j}] (status: {element_status})"
                    )

            durations.append(duration_row)
            distances.append(distance_row)

        if failed_pairs:
            raise MapsAPIError(
                f"Distance Matrix API returned invalid results for {len(failed_pairs)} "
                f"origin-destination pair(s): {'; '.join(failed_descriptions)}",
                failed_pairs=failed_pairs,
            )

        # Build the combined unique locations list preserving order
        all_locations = list(origins)
        seen: set[tuple[float, float]] = set(origins)
        for loc in destinations:
            if loc not in seen:
                all_locations.append(loc)
                seen.add(loc)

        return TravelTimeMatrix(
            locations=all_locations,
            durations=durations,
            distances=distances,
        )

    async def _get_api_key(self) -> str:
        """Retrieve the Google Maps API key.

        Uses the constructor-provided key if available, otherwise fetches
        from the database config table.

        Raises:
            MapsAPIError: If the API key is not configured.
        """
        if self._api_key:
            return self._api_key

        config = await get_config()
        api_key = config.get("google_maps_api_key", "").strip()
        if not api_key:
            raise MapsAPIError(
                "Google Maps API key is not configured. "
                "Please set it in the Configuration screen."
            )
        return api_key

    def _call_distance_matrix(
        self,
        api_key: str,
        origins: list[str],
        destinations: list[str],
        mode: str,
        timeout: float,
    ) -> dict:
        """Synchronous call to the Google Maps Distance Matrix API.

        This method runs in a separate thread via asyncio.to_thread.

        Raises:
            MapsAPIError: On API errors or transport failures.
        """
        try:
            client = googlemaps.Client(key=api_key, timeout=timeout)
            result = client.distance_matrix(
                origins=origins,
                destinations=destinations,
                mode=mode,
            )
            return result
        except Timeout as e:
            raise MapsAPIError(
                f"Google Maps Distance Matrix API request timed out after {timeout} seconds"
            ) from e
        except ApiError as e:
            raise MapsAPIError(
                f"Google Maps API error: {e.message}"
            ) from e
        except TransportError as e:
            raise MapsAPIError(
                f"Google Maps API transport error: {str(e)}"
            ) from e
        except Exception as e:
            raise MapsAPIError(
                f"Unexpected error calling Google Maps API: {str(e)}"
            ) from e
