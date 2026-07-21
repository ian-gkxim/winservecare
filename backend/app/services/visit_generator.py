"""Visit Generation Engine.

Evaluates active care contracts against a target date and produces
generated visits for the existing optimisation pipeline.
"""

from datetime import date

from backend.app.db.contract_repository import get_all_contracts
from backend.app.db.repositories import (
    delete_visits_by_date,
    get_visits_by_date,
    insert_generated_visits,
)
from backend.app.models.contract import (
    CareContractModel,
    DayOfWeek,
    GenerateVisitsResponse,
    VisitFrequency,
)

# Map DayOfWeek enum values to Python weekday integers (Monday=0 ... Sunday=6)
_DAY_TO_WEEKDAY: dict[str, int] = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class VisitGenerator:
    """Pure-logic engine that produces visits from care contracts for a target date."""

    def check_frequency(
        self,
        frequency: VisitFrequency,
        start_date: date,
        target_date: date,
        days_of_week: list[DayOfWeek] | None,
    ) -> bool:
        """Evaluate whether the target_date satisfies the contract's frequency rule.

        Rules:
        - daily: always True
        - weekdays_only: Mon-Fri only (weekday() < 5)
        - specific_days: target's weekday must be in days_of_week
        - alternate_days: (target_date - start_date).days % 2 == 0
        - weekly: target_date.weekday() == start_date.weekday()
        """
        if frequency == VisitFrequency.DAILY:
            return True

        if frequency == VisitFrequency.WEEKDAYS_ONLY:
            return target_date.weekday() < 5

        if frequency == VisitFrequency.SPECIFIC_DAYS:
            if not days_of_week:
                return False
            target_weekday = target_date.weekday()
            allowed_weekdays = [_DAY_TO_WEEKDAY[d.value] for d in days_of_week]
            return target_weekday in allowed_weekdays

        if frequency == VisitFrequency.ALTERNATE_DAYS:
            delta_days = (target_date - start_date).days
            return delta_days % 2 == 0

        if frequency == VisitFrequency.WEEKLY:
            return target_date.weekday() == start_date.weekday()

        return False

    def is_contract_eligible(
        self, contract: CareContractModel, target_date: date
    ) -> bool:
        """Determine if a contract should generate visits for the given date.

        A contract is eligible iff:
        1. target_date >= contract.start_date
        2. contract.end_date is None OR target_date <= contract.end_date
        3. target_date not in contract.excluded_dates
        4. check_frequency passes
        """
        # 1. Must be on or after start date
        if target_date < contract.start_date:
            return False

        # 2. Must be on or before end date (if set)
        if contract.end_date is not None and target_date > contract.end_date:
            return False

        # 3. Must not be an excluded date
        if target_date in contract.excluded_dates:
            return False

        # 4. Frequency check
        return self.check_frequency(
            contract.visit_frequency,
            contract.start_date,
            target_date,
            contract.days_of_week,
        )

    async def generate_visits(self, target_date: date) -> GenerateVisitsResponse:
        """Generate all visits for the target date from active contracts.

        Steps:
        1. Fetch all contracts via get_all_contracts()
        2. Evaluate eligibility for each contract
        3. Delete existing visits for target_date via delete_visits_by_date()
        4. For eligible contracts, create visit dicts from each visit_slot
        5. Insert all via insert_generated_visits()
        6. Return GenerateVisitsResponse with visits, counts
        """
        # 1. Fetch all contracts
        contracts = await get_all_contracts()
        total_contracts_evaluated = len(contracts)

        # 2. Evaluate eligibility
        eligible_contracts = [
            c for c in contracts if self.is_contract_eligible(c, target_date)
        ]
        eligible_count = len(eligible_contracts)

        # 3. Delete existing visits for this target date
        await delete_visits_by_date(target_date.isoformat())

        # 4. Build visit dicts from eligible contracts' slots
        visits_to_insert: list[dict] = []
        for contract in eligible_contracts:
            for slot in contract.visit_slots:
                visits_to_insert.append(
                    {
                        "patient_id": contract.patient_id,
                        "duration_minutes": slot.duration_minutes,
                        "window_start": slot.earliest_start,
                        "window_end": slot.latest_start,
                        "required_skills": slot.required_skills,
                        "preferred_time": None,
                        "target_date": target_date.isoformat(),
                        "contract_id": contract.id,
                    }
                )

        # 5. Insert generated visits
        await insert_generated_visits(visits_to_insert)

        # 6. Fetch the inserted visits back (with patient names) for the response
        visit_rows = await get_visits_by_date(target_date.isoformat())

        return GenerateVisitsResponse(
            visits=visit_rows,
            scheduled_count=len(visits_to_insert),
            total_contracts_evaluated=total_contracts_evaluated,
            eligible_contracts=eligible_count,
        )
