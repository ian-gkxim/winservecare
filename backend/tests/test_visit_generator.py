"""Unit tests for the Visit Generation Engine."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from backend.app.db import database
from backend.app.models.contract import (
    CareContractModel,
    DayOfWeek,
    GenerateVisitsResponse,
    VisitFrequency,
    VisitSlotModel,
)
from backend.app.services.visit_generator import VisitGenerator


# --- Pure function tests (no DB needed) ---


class TestCheckFrequency:
    """Tests for VisitGenerator.check_frequency()."""

    def setup_method(self):
        self.vg = VisitGenerator()

    def test_daily_always_true(self):
        """Daily frequency is always eligible."""
        assert self.vg.check_frequency(
            VisitFrequency.DAILY, date(2025, 1, 1), date(2025, 7, 15), None
        ) is True

    def test_weekdays_only_monday(self):
        """Weekdays_only is True for Monday."""
        # 2025-07-14 is a Monday
        assert self.vg.check_frequency(
            VisitFrequency.WEEKDAYS_ONLY, date(2025, 1, 1), date(2025, 7, 14), None
        ) is True

    def test_weekdays_only_friday(self):
        """Weekdays_only is True for Friday."""
        # 2025-07-18 is a Friday
        assert self.vg.check_frequency(
            VisitFrequency.WEEKDAYS_ONLY, date(2025, 1, 1), date(2025, 7, 18), None
        ) is True

    def test_weekdays_only_saturday(self):
        """Weekdays_only is False for Saturday."""
        # 2025-07-19 is a Saturday
        assert self.vg.check_frequency(
            VisitFrequency.WEEKDAYS_ONLY, date(2025, 1, 1), date(2025, 7, 19), None
        ) is False

    def test_weekdays_only_sunday(self):
        """Weekdays_only is False for Sunday."""
        # 2025-07-20 is a Sunday
        assert self.vg.check_frequency(
            VisitFrequency.WEEKDAYS_ONLY, date(2025, 1, 1), date(2025, 7, 20), None
        ) is False

    def test_specific_days_matching(self):
        """Specific_days is True when target's day is in the list."""
        # 2025-07-14 is Monday
        assert self.vg.check_frequency(
            VisitFrequency.SPECIFIC_DAYS,
            date(2025, 1, 1),
            date(2025, 7, 14),
            [DayOfWeek.MON, DayOfWeek.WED, DayOfWeek.FRI],
        ) is True

    def test_specific_days_not_matching(self):
        """Specific_days is False when target's day is not in the list."""
        # 2025-07-15 is Tuesday
        assert self.vg.check_frequency(
            VisitFrequency.SPECIFIC_DAYS,
            date(2025, 1, 1),
            date(2025, 7, 15),
            [DayOfWeek.MON, DayOfWeek.WED, DayOfWeek.FRI],
        ) is False

    def test_specific_days_empty_list(self):
        """Specific_days is False when days_of_week is empty."""
        assert self.vg.check_frequency(
            VisitFrequency.SPECIFIC_DAYS, date(2025, 1, 1), date(2025, 7, 14), None
        ) is False

    def test_alternate_days_even_delta(self):
        """Alternate_days is True when delta is even (including 0)."""
        start = date(2025, 1, 1)
        # Delta 0 (same day)
        assert self.vg.check_frequency(
            VisitFrequency.ALTERNATE_DAYS, start, date(2025, 1, 1), None
        ) is True
        # Delta 2
        assert self.vg.check_frequency(
            VisitFrequency.ALTERNATE_DAYS, start, date(2025, 1, 3), None
        ) is True

    def test_alternate_days_odd_delta(self):
        """Alternate_days is False when delta is odd."""
        start = date(2025, 1, 1)
        # Delta 1
        assert self.vg.check_frequency(
            VisitFrequency.ALTERNATE_DAYS, start, date(2025, 1, 2), None
        ) is False
        # Delta 3
        assert self.vg.check_frequency(
            VisitFrequency.ALTERNATE_DAYS, start, date(2025, 1, 4), None
        ) is False

    def test_weekly_same_weekday(self):
        """Weekly is True when target has same weekday as start."""
        # 2025-01-06 is Monday, 2025-01-13 is also Monday
        assert self.vg.check_frequency(
            VisitFrequency.WEEKLY, date(2025, 1, 6), date(2025, 1, 13), None
        ) is True

    def test_weekly_different_weekday(self):
        """Weekly is False when target has different weekday from start."""
        # 2025-01-06 is Monday, 2025-01-14 is Tuesday
        assert self.vg.check_frequency(
            VisitFrequency.WEEKLY, date(2025, 1, 6), date(2025, 1, 14), None
        ) is False


class TestIsContractEligible:
    """Tests for VisitGenerator.is_contract_eligible()."""

    def setup_method(self):
        self.vg = VisitGenerator()

    def _make_contract(self, **kwargs) -> CareContractModel:
        """Helper to create a contract with sensible defaults."""
        defaults = {
            "id": 1,
            "patient_id": 1,
            "visit_frequency": VisitFrequency.DAILY,
            "days_of_week": None,
            "visits_per_day": 1,
            "start_date": date(2025, 1, 1),
            "end_date": None,
            "excluded_dates": [],
            "visit_slots": [],
        }
        defaults.update(kwargs)
        return CareContractModel(**defaults)

    def test_eligible_basic(self):
        """Contract is eligible when all conditions met."""
        contract = self._make_contract()
        assert self.vg.is_contract_eligible(contract, date(2025, 6, 15)) is True

    def test_not_eligible_before_start(self):
        """Contract not eligible before start_date."""
        contract = self._make_contract(start_date=date(2025, 6, 1))
        assert self.vg.is_contract_eligible(contract, date(2025, 5, 31)) is False

    def test_eligible_on_start_date(self):
        """Contract is eligible on exactly the start_date."""
        contract = self._make_contract(start_date=date(2025, 6, 1))
        assert self.vg.is_contract_eligible(contract, date(2025, 6, 1)) is True

    def test_not_eligible_after_end(self):
        """Contract not eligible after end_date."""
        contract = self._make_contract(end_date=date(2025, 6, 30))
        assert self.vg.is_contract_eligible(contract, date(2025, 7, 1)) is False

    def test_eligible_on_end_date(self):
        """Contract is eligible on exactly the end_date."""
        contract = self._make_contract(end_date=date(2025, 6, 30))
        assert self.vg.is_contract_eligible(contract, date(2025, 6, 30)) is True

    def test_not_eligible_excluded_date(self):
        """Contract not eligible on an excluded date."""
        contract = self._make_contract(excluded_dates=[date(2025, 7, 4)])
        assert self.vg.is_contract_eligible(contract, date(2025, 7, 4)) is False

    def test_not_eligible_frequency_mismatch(self):
        """Contract not eligible when frequency check fails."""
        # Weekly starting Monday, checking a Tuesday
        contract = self._make_contract(
            visit_frequency=VisitFrequency.WEEKLY,
            start_date=date(2025, 1, 6),  # Monday
        )
        assert self.vg.is_contract_eligible(contract, date(2025, 1, 14)) is False  # Tuesday


class TestGenerateVisits:
    """Tests for VisitGenerator.generate_visits() with mocked DB calls."""

    def setup_method(self):
        self.vg = VisitGenerator()

    @pytest.mark.asyncio
    async def test_generates_visits_for_eligible_contracts(self):
        """Generates correct visits from eligible contracts."""
        contract = CareContractModel(
            id=1,
            patient_id=10,
            visit_frequency=VisitFrequency.DAILY,
            days_of_week=None,
            visits_per_day=2,
            start_date=date(2025, 1, 1),
            end_date=None,
            excluded_dates=[],
            visit_slots=[
                VisitSlotModel(
                    id=1, contract_id=1, slot_index=0, label="Morning",
                    earliest_start="08:00", latest_start="10:00",
                    duration_minutes=30, required_skills=["medication"],
                ),
                VisitSlotModel(
                    id=2, contract_id=1, slot_index=1, label="Evening",
                    earliest_start="17:00", latest_start="19:00",
                    duration_minutes=45, required_skills=["personal_care"],
                ),
            ],
        )

        mock_visits_response = [
            {"id": 100, "patient_id": 10, "patient_name": "Patient A",
             "duration_minutes": 30, "window_start": "08:00", "window_end": "10:00",
             "required_skills": ["medication"], "preferred_time": None,
             "is_cancelled": False, "target_date": "2025-07-14", "contract_id": 1},
            {"id": 101, "patient_id": 10, "patient_name": "Patient A",
             "duration_minutes": 45, "window_start": "17:00", "window_end": "19:00",
             "required_skills": ["personal_care"], "preferred_time": None,
             "is_cancelled": False, "target_date": "2025-07-14", "contract_id": 1},
        ]

        with patch("backend.app.services.visit_generator.get_all_contracts", new_callable=AsyncMock) as mock_get, \
             patch("backend.app.services.visit_generator.delete_visits_by_date", new_callable=AsyncMock) as mock_delete, \
             patch("backend.app.services.visit_generator.insert_generated_visits", new_callable=AsyncMock) as mock_insert, \
             patch("backend.app.services.visit_generator.get_visits_by_date", new_callable=AsyncMock) as mock_get_visits:

            mock_get.return_value = [contract]
            mock_delete.return_value = 0
            mock_insert.return_value = [100, 101]
            mock_get_visits.return_value = mock_visits_response

            result = await self.vg.generate_visits(date(2025, 7, 14))

            assert result.total_contracts_evaluated == 1
            assert result.eligible_contracts == 1
            assert result.scheduled_count == 2
            assert len(result.visits) == 2

            # Verify delete was called
            mock_delete.assert_called_once_with("2025-07-14")

            # Verify insert was called with correct data
            inserted = mock_insert.call_args[0][0]
            assert len(inserted) == 2
            assert inserted[0]["patient_id"] == 10
            assert inserted[0]["window_start"] == "08:00"
            assert inserted[0]["window_end"] == "10:00"
            assert inserted[0]["duration_minutes"] == 30
            assert inserted[0]["required_skills"] == ["medication"]
            assert inserted[0]["contract_id"] == 1
            assert inserted[0]["target_date"] == "2025-07-14"
            assert inserted[1]["window_start"] == "17:00"
            assert inserted[1]["duration_minutes"] == 45

    @pytest.mark.asyncio
    async def test_no_eligible_contracts(self):
        """Returns empty when no contracts are eligible."""
        # Contract that starts in the future
        contract = CareContractModel(
            id=1,
            patient_id=10,
            visit_frequency=VisitFrequency.DAILY,
            days_of_week=None,
            visits_per_day=1,
            start_date=date(2026, 1, 1),
            end_date=None,
            excluded_dates=[],
            visit_slots=[],
        )

        with patch("backend.app.services.visit_generator.get_all_contracts", new_callable=AsyncMock) as mock_get, \
             patch("backend.app.services.visit_generator.delete_visits_by_date", new_callable=AsyncMock) as mock_delete, \
             patch("backend.app.services.visit_generator.insert_generated_visits", new_callable=AsyncMock) as mock_insert, \
             patch("backend.app.services.visit_generator.get_visits_by_date", new_callable=AsyncMock) as mock_get_visits:

            mock_get.return_value = [contract]
            mock_delete.return_value = 0
            mock_insert.return_value = []
            mock_get_visits.return_value = []

            result = await self.vg.generate_visits(date(2025, 7, 14))

            assert result.total_contracts_evaluated == 1
            assert result.eligible_contracts == 0
            assert result.scheduled_count == 0
            assert result.visits == []

    @pytest.mark.asyncio
    async def test_mixed_eligibility(self):
        """Only eligible contracts produce visits."""
        eligible_contract = CareContractModel(
            id=1,
            patient_id=10,
            visit_frequency=VisitFrequency.DAILY,
            days_of_week=None,
            visits_per_day=1,
            start_date=date(2025, 1, 1),
            end_date=None,
            excluded_dates=[],
            visit_slots=[
                VisitSlotModel(
                    id=1, contract_id=1, slot_index=0, label="Morning",
                    earliest_start="08:00", latest_start="10:00",
                    duration_minutes=30, required_skills=[],
                ),
            ],
        )

        ineligible_contract = CareContractModel(
            id=2,
            patient_id=20,
            visit_frequency=VisitFrequency.WEEKLY,
            days_of_week=None,
            visits_per_day=1,
            start_date=date(2025, 1, 6),  # Monday
            end_date=None,
            excluded_dates=[],
            visit_slots=[
                VisitSlotModel(
                    id=2, contract_id=2, slot_index=0, label="Weekly",
                    earliest_start="09:00", latest_start="11:00",
                    duration_minutes=60, required_skills=[],
                ),
            ],
        )

        mock_visits_response = [
            {"id": 100, "patient_id": 10, "patient_name": "Patient A",
             "duration_minutes": 30, "window_start": "08:00", "window_end": "10:00",
             "required_skills": [], "preferred_time": None,
             "is_cancelled": False, "target_date": "2025-07-15", "contract_id": 1},
        ]

        with patch("backend.app.services.visit_generator.get_all_contracts", new_callable=AsyncMock) as mock_get, \
             patch("backend.app.services.visit_generator.delete_visits_by_date", new_callable=AsyncMock) as mock_delete, \
             patch("backend.app.services.visit_generator.insert_generated_visits", new_callable=AsyncMock) as mock_insert, \
             patch("backend.app.services.visit_generator.get_visits_by_date", new_callable=AsyncMock) as mock_get_visits:

            mock_get.return_value = [eligible_contract, ineligible_contract]
            mock_delete.return_value = 0
            mock_insert.return_value = [100]
            mock_get_visits.return_value = mock_visits_response

            # 2025-07-15 is Tuesday, so weekly (Monday start) is not eligible
            result = await self.vg.generate_visits(date(2025, 7, 15))

            assert result.total_contracts_evaluated == 2
            assert result.eligible_contracts == 1
            assert result.scheduled_count == 1

            # Only the eligible contract's visit should be inserted
            inserted = mock_insert.call_args[0][0]
            assert len(inserted) == 1
            assert inserted[0]["patient_id"] == 10
