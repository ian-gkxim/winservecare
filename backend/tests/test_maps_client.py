"""Tests for the Google Maps client service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.services.maps_client import (
    GoogleMapsClient,
    MapsAPIError,
    Location,
)
from backend.app.models.optimisation import TravelTimeMatrix


@pytest.fixture
def client():
    return GoogleMapsClient(api_key="test-api-key")


@pytest.fixture
def sample_origins() -> list[Location]:
    return [(51.5074, -0.1278), (51.5155, -0.1419)]


@pytest.fixture
def sample_destinations() -> list[Location]:
    return [(51.5225, -0.1553), (51.4975, -0.1357)]


@pytest.fixture
def valid_api_response():
    """A valid Distance Matrix API response for 2 origins x 2 destinations."""
    return {
        "status": "OK",
        "origin_addresses": ["London, UK", "London, UK"],
        "destination_addresses": ["London, UK", "London, UK"],
        "rows": [
            {
                "elements": [
                    {
                        "status": "OK",
                        "duration": {"value": 600, "text": "10 mins"},
                        "distance": {"value": 3200, "text": "3.2 km"},
                    },
                    {
                        "status": "OK",
                        "duration": {"value": 480, "text": "8 mins"},
                        "distance": {"value": 2500, "text": "2.5 km"},
                    },
                ]
            },
            {
                "elements": [
                    {
                        "status": "OK",
                        "duration": {"value": 720, "text": "12 mins"},
                        "distance": {"value": 4100, "text": "4.1 km"},
                    },
                    {
                        "status": "OK",
                        "duration": {"value": 540, "text": "9 mins"},
                        "distance": {"value": 2800, "text": "2.8 km"},
                    },
                ]
            },
        ],
    }


@pytest.fixture
def partial_failure_response():
    """A Distance Matrix API response with two pairs returning errors."""
    return {
        "status": "OK",
        "rows": [
            {
                "elements": [
                    {
                        "status": "OK",
                        "duration": {"value": 600, "text": "10 mins"},
                        "distance": {"value": 3200, "text": "3.2 km"},
                    },
                    {
                        "status": "ZERO_RESULTS",
                    },
                ]
            },
            {
                "elements": [
                    {
                        "status": "OK",
                        "duration": {"value": 720, "text": "12 mins"},
                        "distance": {"value": 4100, "text": "4.1 km"},
                    },
                    {
                        "status": "NOT_FOUND",
                    },
                ]
            },
        ],
    }


class TestGoogleMapsClientSuccess:
    """Tests for successful Distance Matrix API calls."""

    @pytest.mark.asyncio
    async def test_get_distance_matrix_returns_travel_time_matrix(
        self, client, sample_origins, sample_destinations, valid_api_response
    ):
        """Successful call returns a TravelTimeMatrix with correct dimensions."""
        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ):
            result = await client.get_distance_matrix(
                origins=sample_origins,
                destinations=sample_destinations,
            )

        assert isinstance(result, TravelTimeMatrix)
        assert len(result.durations) == 2  # 2 origins
        assert len(result.durations[0]) == 2  # 2 destinations
        assert len(result.distances) == 2
        assert len(result.distances[0]) == 2

    @pytest.mark.asyncio
    async def test_get_distance_matrix_correct_durations(
        self, client, sample_origins, sample_destinations, valid_api_response
    ):
        """Durations are correctly extracted as seconds."""
        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ):
            result = await client.get_distance_matrix(
                origins=sample_origins,
                destinations=sample_destinations,
            )

        assert result.durations[0][0] == 600
        assert result.durations[0][1] == 480
        assert result.durations[1][0] == 720
        assert result.durations[1][1] == 540

    @pytest.mark.asyncio
    async def test_get_distance_matrix_correct_distances(
        self, client, sample_origins, sample_destinations, valid_api_response
    ):
        """Distances are correctly extracted as metres."""
        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ):
            result = await client.get_distance_matrix(
                origins=sample_origins,
                destinations=sample_destinations,
            )

        assert result.distances[0][0] == 3200
        assert result.distances[0][1] == 2500
        assert result.distances[1][0] == 4100
        assert result.distances[1][1] == 2800

    @pytest.mark.asyncio
    async def test_get_distance_matrix_locations_populated(
        self, client, sample_origins, sample_destinations, valid_api_response
    ):
        """Locations list contains all unique origin and destination coordinates."""
        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ):
            result = await client.get_distance_matrix(
                origins=sample_origins,
                destinations=sample_destinations,
            )

        # All 4 locations are unique in this case
        assert len(result.locations) == 4
        assert sample_origins[0] in result.locations
        assert sample_origins[1] in result.locations
        assert sample_destinations[0] in result.locations
        assert sample_destinations[1] in result.locations

    @pytest.mark.asyncio
    async def test_get_distance_matrix_deduplicates_overlapping_locations(
        self, client, valid_api_response
    ):
        """When origins and destinations overlap, locations are deduplicated."""
        shared_location: Location = (51.5074, -0.1278)
        origins = [shared_location, (51.5155, -0.1419)]
        destinations = [shared_location, (51.4975, -0.1357)]

        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ):
            result = await client.get_distance_matrix(
                origins=origins,
                destinations=destinations,
            )

        # Shared location should appear only once: 3 unique locations total
        assert len(result.locations) == 3

    @pytest.mark.asyncio
    async def test_get_distance_matrix_uses_driving_mode_by_default(
        self, client, sample_origins, sample_destinations, valid_api_response
    ):
        """Mode defaults to 'driving' when not specified."""
        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ) as mock_call:
            await client.get_distance_matrix(
                origins=sample_origins,
                destinations=sample_destinations,
            )

        # Check the mode argument passed to _call_distance_matrix
        call_kwargs = mock_call.call_args[1]
        assert call_kwargs["mode"] == "driving"

    @pytest.mark.asyncio
    async def test_get_distance_matrix_passes_custom_mode_and_timeout(
        self, client, sample_origins, sample_destinations, valid_api_response
    ):
        """Custom mode and timeout parameters are passed to the API call."""
        with patch.object(
            client, "_call_distance_matrix", return_value=valid_api_response
        ) as mock_call:
            await client.get_distance_matrix(
                origins=sample_origins,
                destinations=sample_destinations,
                mode="walking",
                timeout=15.0,
            )

        call_kwargs = mock_call.call_args[1]
        assert call_kwargs["mode"] == "walking"
        assert call_kwargs["timeout"] == 15.0


class TestGoogleMapsClientErrors:
    """Tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_raises_error_when_api_key_missing(
        self, sample_origins, sample_destinations
    ):
        """Raises MapsAPIError when no API key is configured."""
        client = GoogleMapsClient()  # No explicit api_key
        with patch(
            "backend.app.services.maps_client.get_config",
            new_callable=AsyncMock,
            return_value={},
        ):
            with pytest.raises(MapsAPIError, match="API key is not configured"):
                await client.get_distance_matrix(
                    origins=sample_origins,
                    destinations=sample_destinations,
                )

    @pytest.mark.asyncio
    async def test_raises_error_when_api_key_empty(
        self, sample_origins, sample_destinations
    ):
        """Raises MapsAPIError when API key is empty/whitespace."""
        client = GoogleMapsClient()  # No explicit api_key
        with patch(
            "backend.app.services.maps_client.get_config",
            new_callable=AsyncMock,
            return_value={"google_maps_api_key": "   "},
        ):
            with pytest.raises(MapsAPIError, match="API key is not configured"):
                await client.get_distance_matrix(
                    origins=sample_origins,
                    destinations=sample_destinations,
                )

    @pytest.mark.asyncio
    async def test_raises_error_on_partial_failure(
        self, client, sample_origins, sample_destinations, partial_failure_response
    ):
        """Raises MapsAPIError identifying failed pairs on partial failure."""
        with patch.object(
            client,
            "_call_distance_matrix",
            return_value=partial_failure_response,
        ):
            with pytest.raises(MapsAPIError) as exc_info:
                await client.get_distance_matrix(
                    origins=sample_origins,
                    destinations=sample_destinations,
                )

        error = exc_info.value
        assert "2 origin-destination pair(s)" in error.message
        assert len(error.failed_pairs) == 2
        assert (0, 1) in error.failed_pairs
        assert (1, 1) in error.failed_pairs

    @pytest.mark.asyncio
    async def test_raises_error_on_top_level_api_failure(
        self, client, sample_origins, sample_destinations
    ):
        """Raises MapsAPIError when top-level status is not OK."""
        error_response = {
            "status": "REQUEST_DENIED",
            "error_message": "The provided API key is invalid.",
            "rows": [],
        }
        with patch.object(
            client, "_call_distance_matrix", return_value=error_response
        ):
            with pytest.raises(MapsAPIError, match="REQUEST_DENIED"):
                await client.get_distance_matrix(
                    origins=sample_origins,
                    destinations=sample_destinations,
                )

    @pytest.mark.asyncio
    async def test_raises_error_on_timeout(
        self, client, sample_origins, sample_destinations
    ):
        """Raises MapsAPIError when the API call times out."""
        with patch.object(
            client,
            "_call_distance_matrix",
            side_effect=MapsAPIError(
                "Google Maps Distance Matrix API request timed out after 30 seconds"
            ),
        ):
            with pytest.raises(MapsAPIError, match="timed out"):
                await client.get_distance_matrix(
                    origins=sample_origins,
                    destinations=sample_destinations,
                )

    @pytest.mark.asyncio
    async def test_raises_error_on_transport_failure(
        self, client, sample_origins, sample_destinations
    ):
        """Raises MapsAPIError on network/transport failure."""
        with patch.object(
            client,
            "_call_distance_matrix",
            side_effect=MapsAPIError(
                "Google Maps API transport error: Connection refused"
            ),
        ):
            with pytest.raises(MapsAPIError, match="transport error"):
                await client.get_distance_matrix(
                    origins=sample_origins,
                    destinations=sample_destinations,
                )


class TestCallDistanceMatrix:
    """Tests for the synchronous API call wrapper."""

    def test_call_raises_maps_api_error_on_api_error(self, client):
        """_call_distance_matrix raises MapsAPIError on googlemaps.ApiError."""
        from googlemaps.exceptions import ApiError

        with patch("backend.app.services.maps_client.googlemaps.Client") as MockClient:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.side_effect = ApiError(
                "INVALID_REQUEST", "Bad request"
            )
            MockClient.return_value = mock_instance

            with pytest.raises(MapsAPIError, match="Google Maps API error"):
                client._call_distance_matrix(
                    api_key="test-key",
                    origins=["51.5,-0.1"],
                    destinations=["51.6,-0.2"],
                    mode="driving",
                    timeout=30.0,
                )

    def test_call_raises_maps_api_error_on_timeout(self, client):
        """_call_distance_matrix raises MapsAPIError on googlemaps.Timeout."""
        from googlemaps.exceptions import Timeout as GMTimeout

        with patch("backend.app.services.maps_client.googlemaps.Client") as MockClient:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.side_effect = GMTimeout()
            MockClient.return_value = mock_instance

            with pytest.raises(MapsAPIError, match="timed out"):
                client._call_distance_matrix(
                    api_key="test-key",
                    origins=["51.5,-0.1"],
                    destinations=["51.6,-0.2"],
                    mode="driving",
                    timeout=30.0,
                )

    def test_call_raises_maps_api_error_on_transport_error(self, client):
        """_call_distance_matrix raises MapsAPIError on TransportError."""
        from googlemaps.exceptions import TransportError

        with patch("backend.app.services.maps_client.googlemaps.Client") as MockClient:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.side_effect = TransportError(
                "Connection failed"
            )
            MockClient.return_value = mock_instance

            with pytest.raises(MapsAPIError, match="transport error"):
                client._call_distance_matrix(
                    api_key="test-key",
                    origins=["51.5,-0.1"],
                    destinations=["51.6,-0.2"],
                    mode="driving",
                    timeout=30.0,
                )

    def test_call_success_returns_response(self, client):
        """_call_distance_matrix returns the API response on success."""
        expected_response = {"status": "OK", "rows": []}

        with patch("backend.app.services.maps_client.googlemaps.Client") as MockClient:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.return_value = expected_response
            MockClient.return_value = mock_instance

            result = client._call_distance_matrix(
                api_key="test-key",
                origins=["51.5,-0.1"],
                destinations=["51.6,-0.2"],
                mode="driving",
                timeout=30.0,
            )

        assert result == expected_response

    def test_call_raises_maps_api_error_on_unexpected_exception(self, client):
        """_call_distance_matrix wraps unexpected exceptions in MapsAPIError."""
        with patch("backend.app.services.maps_client.googlemaps.Client") as MockClient:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.side_effect = RuntimeError("Something broke")
            MockClient.return_value = mock_instance

            with pytest.raises(MapsAPIError, match="Unexpected error"):
                client._call_distance_matrix(
                    api_key="test-key",
                    origins=["51.5,-0.1"],
                    destinations=["51.6,-0.2"],
                    mode="driving",
                    timeout=30.0,
                )
