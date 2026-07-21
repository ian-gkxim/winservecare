"""OR-Tools VRP optimisation engine for care visit routing."""

from __future__ import annotations

import asyncio
import queue
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

if TYPE_CHECKING:
    from backend.app.services.progress import ProgressService

from backend.app.models.carer import CarerModel
from backend.app.models.constraint import ConstraintModel
from backend.app.models.optimisation import (
    InfeasibilityReason,
    KPIMetrics,
    OptimisationResult,
    RecommendationModel,
    RouteModel,
    RouteStop,
    TravelTimeMatrix,
)
from backend.app.models.patient import PatientModel
from backend.app.models.visit import VisitModel
from backend.app.services.recommendations import generate_recommendations


# Large penalty for constraint violations (used in disjunctions for unassignable visits)
PENALTY_UNASSIGNED = 100_000

# Time dimension name used across the model
TIME_DIMENSION = "Time"

# Metres-to-miles conversion factor
METRES_PER_MILE = 1609.34

# Cost rates for route costing
COST_PER_MILE = 0.45  # £ per mile
COST_PER_HOUR_TRAVEL = 15.0  # £ per hour of travel time

# Objective function weights (minimise positive terms, maximise negative terms)
# Formula: w1*travel_time + w2*mileage + w3*overtime
#         - w4*continuity - w5*preference - w6*balance - w7*punctuality
W_TRAVEL_TIME = 1.0
W_MILEAGE = 0.5
W_OVERTIME = 2.0
W_CONTINUITY = 1.5
W_PREFERENCE = 1.0
W_BALANCE = 0.8
W_PUNCTUALITY = 0.7


def _time_str_to_minutes(time_str: str) -> int:
    """Convert HH:MM string to minutes from midnight."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time_str(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


@dataclass
class SolutionEvent:
    """Thread-safe event pushed from solver thread to async loop."""

    solutions_found: int
    objective_value: int  # raw OR-Tools objective (cost)
    wall_time_seconds: float


class SolverSolutionCallback:
    """Captures intermediate solutions during OR-Tools search.

    Runs in the solver's thread. Pushes SolutionEvent objects
    to a thread-safe queue for the async event loop to consume.

    Usage: register with routing.AddAtSolutionCallback(callback)
    """

    def __init__(self, event_queue: queue.Queue, routing: pywrapcp.RoutingModel) -> None:
        self._queue = event_queue
        self._routing = routing
        self._solutions_found = 0
        self._start_time = time.monotonic()

    def __call__(self) -> None:
        """Called each time the solver finds an improved solution."""
        self._solutions_found += 1
        self._queue.put(
            SolutionEvent(
                solutions_found=self._solutions_found,
                objective_value=self._routing.CostVar().Max(),
                wall_time_seconds=time.monotonic() - self._start_time,
            )
        )


@dataclass
class RoutingModel:
    """Container for the OR-Tools routing model and associated metadata.

    Provides the routing model, index manager, search parameters, and
    contextual data needed by extract_routes() to convert the solver's
    solution into domain objects.
    """

    manager: pywrapcp.RoutingIndexManager
    routing: pywrapcp.RoutingModel
    search_parameters: pywrapcp.DefaultRoutingSearchParameters
    carers: list[CarerModel]
    visits: list[VisitModel]
    travel_matrix: TravelTimeMatrix
    # Ordered list of carer IDs (matching vehicle indices)
    carer_ids: list[int] = field(default_factory=list)
    # Mapping from visit ID to solver node index
    visit_index_map: dict[int, int] = field(default_factory=dict)


class OptimisationEngine:
    """Builds and solves OR-Tools VRP models for care visit scheduling."""

    async def run(
        self,
        carers: list[CarerModel],
        visits: list[VisitModel],
        patients: list[PatientModel],
        constraints: list[ConstraintModel],
        travel_matrix: TravelTimeMatrix,
        on_step: Callable[[dict], Awaitable[None]],
        on_progress: Callable[[dict], Awaitable[None]],
        progress: ProgressService | None = None,
    ) -> OptimisationResult:
        """Execute VRP optimisation with step-by-step callbacks.

        Orchestrates the full optimisation flow:
        1. Emit location data (carers + patients)
        2. Emit travel matrix info
        3. Compute feasible assignments and emit edges
        4. Apply constraint pruning and emit removed edges
        5. Run the solver and emit candidate route evaluations
        6. Emit improvement iterations
        7. Emit the winning solution
        8. Emit route animation data

        Args:
            carers: Available carers for the schedule.
            visits: Visits to be assigned.
            patients: Patients associated with visits.
            constraints: Hard constraints (enabled/disabled).
            travel_matrix: Pre-computed travel durations/distances.
            on_step: Async callback receiving animation step payloads.
            on_progress: Async callback receiving progress updates.

        Returns:
            OptimisationResult with routes, KPIs, recommendations, and infeasibility info.
        """
        num_carers = len(carers)
        num_visits = len(visits)
        patient_map = {p.id: p for p in patients}

        # --- Step 1: Locations plotted ---
        await on_step({
            "stepNumber": 1,
            "stepName": "Locations plotted",
            "data": {
                "type": "locations",
                "carers": [
                    {"id": c.id, "name": c.name, "lat": c.home_lat, "lng": c.home_lng}
                    for c in carers
                ],
                "patients": [
                    {"id": p.id, "name": p.name, "lat": p.lat, "lng": p.lng}
                    for p in patients
                ],
            },
        })
        await on_progress({"step": 1, "name": "Locations plotted", "score": 0.0})

        # --- Step 2: Matrix retrieved ---
        pair_count = len(travel_matrix.locations) ** 2
        await on_step({
            "stepNumber": 2,
            "stepName": "Matrix retrieved",
            "data": {
                "type": "matrix",
                "pairCount": pair_count,
            },
        })
        await on_progress({"step": 2, "name": "Matrix retrieved", "score": 0.0})

        # --- Step 3: Feasible assignments ---
        # Build all possible carer-visit assignment edges
        all_edges: list[dict] = []
        for carer in carers:
            for visit in visits:
                all_edges.append({
                    "carerId": carer.id,
                    "visitId": visit.id,
                    "carerName": carer.name,
                    "patientId": visit.patient_id,
                })

        await on_step({
            "stepNumber": 3,
            "stepName": "Feasible assignments",
            "data": {
                "type": "assignments",
                "edges": all_edges,
            },
        })
        await on_progress({"step": 3, "name": "Feasible assignments", "score": 0.0})

        # --- Step 4: Constraint pruning ---
        # Determine which edges get pruned by enabled constraints
        enabled_constraints = [c for c in constraints if c.is_enabled]
        enabled_names = {c.name.lower() for c in enabled_constraints}

        removed_edges: list[dict] = []
        pruning_reason_parts: list[str] = []

        # Skill-based pruning
        skill_matching_enabled = (
            "skill_matching" in enabled_names
            or "medication_competency" in enabled_names
            or "required_competency" in enabled_names
            or "competency" in enabled_names
        )

        if skill_matching_enabled:
            for carer in carers:
                carer_skills = set(carer.skills)
                for visit in visits:
                    if visit.required_skills:
                        required = set(visit.required_skills)
                        if not required.issubset(carer_skills):
                            removed_edges.append({
                                "carerId": carer.id,
                                "visitId": visit.id,
                                "reason": "skill_mismatch",
                            })
            if removed_edges:
                pruning_reason_parts.append("skill mismatch")

        # Time window pruning - visits unreachable from carer's home
        time_window_removals: list[dict] = []
        for v_idx, visit in enumerate(visits):
            window_start = _time_str_to_minutes(visit.window_start)
            window_end = _time_str_to_minutes(visit.window_end)
            latest_start = window_end - visit.duration_minutes

            for c_idx, carer in enumerate(carers):
                # Carer depot is at matrix index c_idx,
                # Visit location is at matrix index num_carers + v_idx
                depot_loc = c_idx
                visit_loc = num_carers + v_idx
                travel_seconds = travel_matrix.durations[depot_loc][visit_loc]
                travel_minutes = (travel_seconds + 59) // 60

                if travel_minutes > latest_start:
                    edge = {
                        "carerId": carer.id,
                        "visitId": visit.id,
                        "reason": "time_window_unreachable",
                    }
                    # Avoid duplicates from skill pruning
                    if not any(
                        e["carerId"] == carer.id and e["visitId"] == visit.id
                        for e in removed_edges
                    ):
                        time_window_removals.append(edge)

        if time_window_removals:
            removed_edges.extend(time_window_removals)
            pruning_reason_parts.append("time window unreachable")

        pruning_reason = "; ".join(pruning_reason_parts) if pruning_reason_parts else "constraints applied"

        await on_step({
            "stepNumber": 4,
            "stepName": "Constraint pruning",
            "data": {
                "type": "pruning",
                "removedEdges": removed_edges,
                "reason": pruning_reason,
            },
        })
        await on_progress({"step": 4, "name": "Constraint pruning", "score": 0.0})

        # --- Build and solve the model ---
        model = self.build_model(carers, visits, travel_matrix, enabled_constraints)

        if progress is not None:
            solution = await self.run_solver_in_background(model, progress)
        else:
            solution = model.routing.SolveWithParameters(model.search_parameters)

        # If no solution found, emit steps 5-8 as empty and return error result
        if solution is None:
            # Emit remaining steps with empty data
            await on_step({
                "stepNumber": 5,
                "stepName": "Route evaluation",
                "data": {"type": "evaluation", "candidateRoutes": []},
            })
            await on_progress({"step": 5, "name": "Route evaluation", "score": 0.0})

            await on_step({
                "stepNumber": 6,
                "stepName": "Improvement iterations",
                "data": {"type": "improvement", "iterations": []},
            })
            await on_progress({"step": 6, "name": "Improvement iterations", "score": 0.0})

            await on_step({
                "stepNumber": 7,
                "stepName": "Winning solution",
                "data": {"type": "solution", "routes": [], "finalScore": 0.0},
            })
            await on_progress({"step": 7, "name": "Winning solution", "score": 0.0})

            await on_step({
                "stepNumber": 8,
                "stepName": "Route animation",
                "data": {"type": "animation", "routes": []},
            })
            await on_progress({"step": 8, "name": "Route animation", "score": 0.0})

            # Detect infeasibility for all visits
            unassigned_ids, reasons = self.detect_infeasibility(None, model)

            return OptimisationResult(
                routes=[],
                objective_score=0.0,
                kpis=KPIMetrics(
                    total_visits=num_visits,
                    carers_available=num_carers,
                    travel_hours=0.0,
                    mileage=0.0,
                    overtime=0.0,
                    continuity_score=0.0,
                ),
                recommendations=[],
                unassigned_visits=unassigned_ids,
                infeasibility_reasons=reasons,
            )

        # --- Extract routes from the solution ---
        routes = self.extract_routes(solution, model)

        # --- Step 5: Route evaluation ---
        # Show candidate routes (the routes the solver evaluated)
        candidate_routes_data = [
            {
                "carerId": route.carer_id,
                "stops": [{"visitId": s.visit_id, "startTime": s.start_time} for s in route.stops],
                "travelMinutes": route.total_travel_minutes,
            }
            for route in routes
        ]
        await on_step({
            "stepNumber": 5,
            "stepName": "Route evaluation",
            "data": {
                "type": "evaluation",
                "candidateRoutes": candidate_routes_data,
            },
        })

        # Calculate objective for progress reporting
        unassigned_ids, reasons = self.detect_infeasibility(solution, model)

        # Compute continuity score: proportion of visits assigned to the patient's usual carer
        continuity_matches = 0
        total_assigned = 0
        for route in routes:
            for stop in route.stops:
                total_assigned += 1
                patient = patient_map.get(stop.patient_id)
                if patient and patient.usual_carer_id == route.carer_id:
                    continuity_matches += 1
        continuity_score = continuity_matches / total_assigned if total_assigned > 0 else 0.0

        # Compute preference score: proportion of visits assigned to patient's preferred carer
        preference_matches = 0
        for route in routes:
            for stop in route.stops:
                patient = patient_map.get(stop.patient_id)
                if patient and patient.preferred_carer_id == route.carer_id:
                    preference_matches += 1
        preference_score = preference_matches / total_assigned if total_assigned > 0 else 0.0

        # Compute punctuality score: proportion of visits starting within 15 min of preferred time
        punctuality_matches = 0
        visit_map = {v.id: v for v in visits}
        for route in routes:
            for stop in route.stops:
                visit = visit_map.get(stop.visit_id)
                if visit and visit.preferred_time:
                    preferred_minutes = _time_str_to_minutes(visit.preferred_time)
                    start_minutes = _time_str_to_minutes(stop.start_time)
                    if abs(start_minutes - preferred_minutes) <= 15:
                        punctuality_matches += 1
        punctuality_score = punctuality_matches / total_assigned if total_assigned > 0 else 0.0

        objective_score = self.calculate_objective(
            routes, model, continuity_score, preference_score, punctuality_score
        )

        await on_progress({"step": 5, "name": "Route evaluation", "score": objective_score})

        # --- Step 6: Improvement iterations ---
        # The solver already performed local search improvements internally.
        # We emit the final score as a single iteration representing the solver's work.
        iterations = [{"score": objective_score}]
        await on_step({
            "stepNumber": 6,
            "stepName": "Improvement iterations",
            "data": {
                "type": "improvement",
                "iterations": iterations,
            },
        })
        await on_progress({"step": 6, "name": "Improvement iterations", "score": objective_score})

        # --- Step 7: Winning solution ---
        routes_data = [route.model_dump() for route in routes]
        await on_step({
            "stepNumber": 7,
            "stepName": "Winning solution",
            "data": {
                "type": "solution",
                "routes": routes_data,
                "finalScore": objective_score,
            },
        })
        await on_progress({"step": 7, "name": "Winning solution", "score": objective_score})

        # --- Step 8: Route animation ---
        await on_step({
            "stepNumber": 8,
            "stepName": "Route animation",
            "data": {
                "type": "animation",
                "routes": routes_data,
            },
        })
        await on_progress({"step": 8, "name": "Route animation", "score": objective_score})

        # --- Generate recommendations ---
        recommendations = generate_recommendations(
            routes, carers, visits, unassigned_ids
        )

        # --- Compute KPIs ---
        total_travel_hours = sum(r.total_travel_minutes for r in routes) / 60.0
        total_mileage = sum(r.total_mileage for r in routes)

        # Calculate overtime
        total_overtime = 0.0
        for route in routes:
            visit_duration_mins = sum(
                self._get_visit_duration(stop.visit_id, visits)
                for stop in route.stops
            )
            total_working_mins = visit_duration_mins + route.total_travel_minutes
            total_working_hours = total_working_mins / 60.0
            carer_max = self._get_carer_max_hours(route.carer_id, carers)
            if total_working_hours > carer_max:
                total_overtime += total_working_hours - carer_max

        kpis = KPIMetrics(
            total_visits=num_visits,
            carers_available=num_carers,
            travel_hours=round(total_travel_hours, 1),
            mileage=round(total_mileage, 1),
            overtime=round(total_overtime, 1),
            continuity_score=round(continuity_score * 100, 0),
        )

        return OptimisationResult(
            routes=routes,
            objective_score=objective_score,
            kpis=kpis,
            recommendations=recommendations,
            unassigned_visits=unassigned_ids,
            infeasibility_reasons=reasons,
        )

    def _solve_blocking(
        self,
        model: RoutingModel,
        callback: SolverSolutionCallback,
    ) -> pywrapcp.Assignment | None:
        """Run the solver synchronously in a background thread.

        Registers the solution callback and calls SolveWithParameters.
        """
        model.routing.AddAtSolutionCallback(callback)
        return model.routing.SolveWithParameters(model.search_parameters)

    async def run_solver_in_background(
        self,
        model: RoutingModel,
        progress: ProgressService,
    ) -> pywrapcp.Assignment | None:
        """Run the solver in a thread pool, emitting progress from the event loop.

        Uses asyncio.get_event_loop().run_in_executor() to run the blocking
        solver in the default thread pool. Concurrently polls a queue for
        SolutionEvent objects and emits solver progress ticks every ~1 second.
        """
        event_queue: queue.Queue[SolutionEvent] = queue.Queue()
        callback = SolverSolutionCallback(event_queue, model.routing)

        # Start solver in background thread
        loop = asyncio.get_event_loop()
        solver_future = loop.run_in_executor(
            None,
            self._solve_blocking,
            model,
            callback,
        )

        # Concurrent progress emission
        await progress.start_solver_phase()
        start_time = time.monotonic()

        while not solver_future.done():
            # Poll solution events from the queue
            while not event_queue.empty():
                event = event_queue.get_nowait()
                await progress.on_solution_found(
                    event.solutions_found, event.objective_value
                )

            # Emit elapsed-time tick
            elapsed = int(time.monotonic() - start_time)
            await progress.emit_solver_tick(elapsed)

            # Wait ~1 second before next poll
            await asyncio.sleep(1.0)

        # Drain remaining events after solver completes
        while not event_queue.empty():
            event = event_queue.get_nowait()
            await progress.on_solution_found(
                event.solutions_found, event.objective_value
            )

        # Calculate final elapsed time
        elapsed = int(time.monotonic() - start_time)

        # Get the solver result
        result = solver_future.result()

        # Emit completion
        if result is None:
            await progress.complete_solver_phase(elapsed, 0, None)
        else:
            solutions_found = callback._solutions_found
            # Determine best score from the objective value of the solution
            best_score: int | None = None
            if solutions_found > 0:
                best_score = result.ObjectiveValue()
            await progress.complete_solver_phase(
                elapsed, solutions_found, best_score
            )

        return result

    def build_model(
        self,
        carers: list[CarerModel],
        visits: list[VisitModel],
        travel_matrix: TravelTimeMatrix,
        enabled_constraints: list[ConstraintModel],
    ) -> RoutingModel:
        """Construct the OR-Tools routing model with constraints.

        The model maps each carer to a vehicle and each visit to a node.
        Locations in the travel_matrix are ordered as:
          [carer_0_home, carer_1_home, ..., carer_N_home, visit_0_loc, visit_1_loc, ...]

        However, in the solver node layout, visit nodes come first (0..num_visits-1)
        followed by depot nodes (num_visits..num_visits+num_vehicles-1).

        Args:
            carers: List of available carers (vehicles).
            visits: List of visits to schedule (nodes).
            travel_matrix: Pre-computed travel durations/distances between all locations.
            enabled_constraints: List of currently active hard constraints.

        Returns:
            RoutingModel containing the model, manager, search parameters, and metadata.
        """
        num_vehicles = len(carers)
        num_visits = len(visits)

        # Total number of nodes: visits + one depot per vehicle
        num_nodes = num_visits + num_vehicles

        # Node layout:
        # Nodes [0, num_visits-1] = visit nodes
        # Nodes [num_visits, num_visits+num_vehicles-1] = depot nodes (carer homes)
        # Each vehicle starts and ends at its own depot.
        starts = [num_visits + v for v in range(num_vehicles)]
        ends = [num_visits + v for v in range(num_vehicles)]

        # Create the routing index manager
        manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, starts, ends)

        # Create the routing model
        routing = pywrapcp.RoutingModel(manager)

        # Build visit_index_map: visit_id → solver node index
        visit_index_map: dict[int, int] = {}
        for visit_idx, visit in enumerate(visits):
            visit_index_map[visit.id] = visit_idx

        # Build the location mapping from solver nodes to travel_matrix indices.
        # The travel_matrix is ordered: [carer_homes..., visit_locations...]
        # So carer i's home is at travel_matrix index i,
        # and visit j's location is at travel_matrix index num_vehicles + j.
        def _node_to_matrix_idx(node: int) -> int:
            """Map solver node to travel_matrix location index."""
            if node < num_visits:
                # Visit node: its travel_matrix index is num_vehicles + node
                return num_vehicles + node
            else:
                # Depot node: its travel_matrix index is (node - num_visits)
                return node - num_visits

        # Determine which constraints are enabled by name
        enabled_names = {c.name.lower() for c in enabled_constraints if c.is_enabled}

        # --- Transit callbacks ---

        def travel_time_callback(from_index: int, to_index: int) -> int:
            """Return travel time in minutes between two nodes."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            from_loc = _node_to_matrix_idx(from_node)
            to_loc = _node_to_matrix_idx(to_node)
            # Travel matrix durations are in seconds; convert to minutes (ceiling)
            duration_seconds = travel_matrix.durations[from_loc][to_loc]
            return (duration_seconds + 59) // 60

        transit_callback_index = routing.RegisterTransitCallback(travel_time_callback)

        # Set the default cost of travel (arc cost evaluator)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # --- Time dimension ---
        # Tracks cumulative time (travel + service) to enforce time windows and sequencing.

        def time_callback(from_index: int, to_index: int) -> int:
            """Return travel time + service time at from_node (in minutes)."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            from_loc = _node_to_matrix_idx(from_node)
            to_loc = _node_to_matrix_idx(to_node)

            # Travel time in minutes (ceiling)
            duration_seconds = travel_matrix.durations[from_loc][to_loc]
            travel_minutes = (duration_seconds + 59) // 60

            # Add service (visit) duration at from_node if it's a visit node
            service_time = 0
            if from_node < num_visits:
                service_time = visits[from_node].duration_minutes

            return travel_minutes + service_time

        time_callback_index = routing.RegisterTransitCallback(time_callback)

        # The maximum horizon is a full day in minutes (24h = 1440 min).
        max_horizon = 1440

        routing.AddDimension(
            time_callback_index,
            max_horizon,  # max waiting time (slack) at each node
            max_horizon,  # max cumulative time per vehicle
            False,  # don't force start cumul to zero (allow flexible start times)
            TIME_DIMENSION,
        )
        time_dimension = routing.GetDimensionOrDie(TIME_DIMENSION)

        # --- Time window constraints per visit node ---
        for visit_idx, visit in enumerate(visits):
            index = manager.NodeToIndex(visit_idx)

            window_start = _time_str_to_minutes(visit.window_start)
            window_end = _time_str_to_minutes(visit.window_end)

            # The time dimension cumul at a visit node represents arrival/start time.
            # Visit must start within [window_start, window_end - duration]
            # to ensure it completes by window_end.
            latest_start = window_end - visit.duration_minutes
            if latest_start < window_start:
                latest_start = window_start

            time_dimension.CumulVar(index).SetRange(window_start, latest_start)

        # --- Depot time windows (carer availability) ---
        for vehicle_id in range(num_vehicles):
            start_index = routing.Start(vehicle_id)
            end_index = routing.End(vehicle_id)
            # Carers can start from 0 (midnight) up to max_horizon
            time_dimension.CumulVar(start_index).SetRange(0, max_horizon)
            time_dimension.CumulVar(end_index).SetRange(0, max_horizon)

        # --- Maximum working hours constraint ---
        max_hours_enabled = (
            "max_working_hours" in enabled_names
            or "maximum_working_hours" in enabled_names
            or "working_hours" in enabled_names
        )

        if max_hours_enabled:
            # Enforce working hours via time dimension span upper bound.
            # Total working time = end_time - start_time for each vehicle.
            for vehicle_id, carer in enumerate(carers):
                max_minutes = int(carer.max_working_hours * 60)
                time_dimension.SetSpanUpperBoundForVehicle(max_minutes, vehicle_id)

        # --- Skill matching constraint ---
        skill_matching_enabled = (
            "skill_matching" in enabled_names
            or "medication_competency" in enabled_names
            or "required_competency" in enabled_names
            or "competency" in enabled_names
        )

        if skill_matching_enabled:
            self._apply_skill_constraints(
                routing, manager, carers, visits, num_visits
            )

        # --- Break scheduling for continuous work limits ---
        break_enabled = (
            "mandatory_breaks" in enabled_names
            or "break" in enabled_names
            or "continuous_work" in enabled_names
        )

        if break_enabled:
            self._apply_break_constraints(routing, manager, carers, time_dimension)

        # --- Allow visits to be unassigned (with penalty) ---
        # This enables the solver to leave infeasible visits unassigned rather
        # than failing entirely (no-overlap is implicitly handled by disjunction).
        for visit_idx in range(num_visits):
            index = manager.NodeToIndex(visit_idx)
            routing.AddDisjunction([index], PENALTY_UNASSIGNED)

        # --- Search parameters ---
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.FromSeconds(10)

        return RoutingModel(
            manager=manager,
            routing=routing,
            search_parameters=search_parameters,
            carers=carers,
            visits=visits,
            travel_matrix=travel_matrix,
            carer_ids=[c.id for c in carers],
            visit_index_map=visit_index_map,
        )

    def _apply_skill_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        carers: list[CarerModel],
        visits: list[VisitModel],
        num_visits: int,
    ) -> None:
        """Apply skill-matching constraints: visits can only be assigned to
        carers who possess ALL required skills for that visit.

        Uses VehicleVar.SetValues() to restrict which vehicles can serve each
        visit node based on skill matching.
        """
        for visit_idx, visit in enumerate(visits):
            if not visit.required_skills:
                continue

            required = set(visit.required_skills)

            # Find which vehicles (carers) have all required skills
            allowed_vehicles: list[int] = []
            for vehicle_id, carer in enumerate(carers):
                carer_skills = set(carer.skills)
                if required.issubset(carer_skills):
                    allowed_vehicles.append(vehicle_id)

            # If some carers cannot serve this visit, restrict the assignment.
            # Use VehicleVar.SetValues() which is compatible with all OR-Tools versions.
            if len(allowed_vehicles) < len(carers):
                index = manager.NodeToIndex(visit_idx)
                routing.VehicleVar(index).SetValues(allowed_vehicles)

    def _apply_break_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        carers: list[CarerModel],
        time_dimension: pywrapcp.RoutingDimension,
    ) -> None:
        """Apply mandatory break constraints.

        If a carer works continuously for more than max_continuous_hours,
        they must take a break of at least min_break_minutes.

        OR-Tools supports break intervals through the RoutingDimension's
        break constraint mechanism.
        """
        solver = routing.solver()

        for vehicle_id, carer in enumerate(carers):
            max_continuous_minutes = int(carer.max_continuous_hours * 60)
            min_break_duration = carer.min_break_minutes

            # Create a break interval that must be scheduled if the carer
            # works beyond their continuous limit.
            # The break can happen anytime within the working day (0 to 1440).
            break_interval = solver.FixedDurationIntervalVar(
                0,  # earliest start
                1440,  # latest start
                min_break_duration,  # duration
                True,  # optional (solver decides if needed)
                f"break_vehicle_{vehicle_id}",
            )

            # Add the break constraint to the time dimension for this vehicle.
            # The pre-travel values list controls when breaks are triggered:
            # a break must occur before the continuous stretch exceeds the limit.
            time_dimension.SetBreakIntervalsOfVehicle(
                [break_interval],  # list of break intervals
                vehicle_id,
                [max_continuous_minutes],  # node_visit_transits pre-travel values
            )

    def extract_routes(
        self,
        solution: pywrapcp.Assignment,
        model: RoutingModel,
    ) -> list[RouteModel]:
        """Extract ordered route sequences from a solved OR-Tools model.

        Converts the OR-Tools Assignment into a list of RouteModel objects,
        each containing ordered stops with travel times, mileage, and cost.

        Args:
            solution: The Assignment object from routing.SolveWithParameters().
            model: The RoutingModel containing manager, routing, and metadata.

        Returns:
            List of RouteModel objects, one per carer that has assigned visits.
        """
        routes: list[RouteModel] = []
        time_dimension = model.routing.GetDimensionOrDie(TIME_DIMENSION)
        num_vehicles = len(model.carer_ids)
        num_visits = len(model.visits)

        for vehicle_id in range(num_vehicles):
            stops: list[RouteStop] = []
            total_travel_minutes = 0
            total_mileage = 0.0

            # Traverse the route for this vehicle
            index = model.routing.Start(vehicle_id)
            prev_node = model.manager.IndexToNode(index)

            # Move past the start depot
            index = solution.Value(model.routing.NextVar(index))

            while not model.routing.IsEnd(index):
                node = model.manager.IndexToNode(index)

                # Only process visit nodes (not depot nodes)
                if node < num_visits:
                    visit = model.visits[node]

                    # Calculate travel time from previous location
                    prev_loc = self._node_to_matrix_idx(prev_node, num_visits, num_vehicles)
                    curr_loc = self._node_to_matrix_idx(node, num_visits, num_vehicles)

                    travel_seconds = model.travel_matrix.durations[prev_loc][curr_loc]
                    travel_minutes = (travel_seconds + 59) // 60

                    # Calculate mileage from previous location (metres → miles)
                    distance_metres = model.travel_matrix.distances[prev_loc][curr_loc]
                    mileage = distance_metres / METRES_PER_MILE

                    # Get arrival/start time from time dimension
                    time_var = time_dimension.CumulVar(index)
                    arrival_minutes = solution.Min(time_var)
                    start_minutes = solution.Value(time_var)
                    end_minutes = start_minutes + visit.duration_minutes

                    stops.append(
                        RouteStop(
                            visit_id=visit.id,
                            patient_id=visit.patient_id,
                            arrival_time=_minutes_to_time_str(arrival_minutes),
                            start_time=_minutes_to_time_str(start_minutes),
                            end_time=_minutes_to_time_str(end_minutes),
                            travel_time_from_prev=travel_minutes,
                            mileage_from_prev=round(mileage, 2),
                        )
                    )

                    total_travel_minutes += travel_minutes
                    total_mileage += mileage

                prev_node = node
                index = solution.Value(model.routing.NextVar(index))

            # Only include routes that have at least one stop
            if stops:
                total_cost = self._calculate_route_cost(
                    total_travel_minutes, total_mileage
                )
                routes.append(
                    RouteModel(
                        carer_id=model.carer_ids[vehicle_id],
                        stops=stops,
                        total_travel_minutes=total_travel_minutes,
                        total_mileage=round(total_mileage, 2),
                        total_cost=round(total_cost, 2),
                    )
                )

        return routes

    def detect_infeasibility(
        self,
        solution: pywrapcp.Assignment | None,
        model: RoutingModel,
    ) -> tuple[list[int], list[InfeasibilityReason]]:
        """Detect unassigned visits and determine infeasibility reasons.

        Checks which visits are not present in the solution and analyses
        which constraints prevented their assignment.

        Args:
            solution: The Assignment from the solver (may be None if no solution).
            model: The RoutingModel with all metadata.

        Returns:
            Tuple of (unassigned_visit_ids, infeasibility_reasons).
        """
        unassigned_ids: list[int] = []
        reasons: list[InfeasibilityReason] = []
        num_visits = len(model.visits)

        if solution is None:
            # No solution at all — all visits are unassigned
            for visit in model.visits:
                unassigned_ids.append(visit.id)
                reasons.append(
                    InfeasibilityReason(
                        visit_id=visit.id,
                        carer_ids=model.carer_ids,
                        constraint_name="all_constraints",
                        reason="No feasible solution found satisfying all constraints",
                    )
                )
            return unassigned_ids, reasons

        # Check each visit node to see if it's assigned
        for visit_idx, visit in enumerate(model.visits):
            index = model.manager.NodeToIndex(visit_idx)
            # If the visit is unassigned, VehicleVar returns -1 (unperformed)
            vehicle_var = model.routing.VehicleVar(index)
            if solution.Value(vehicle_var) == -1:
                unassigned_ids.append(visit.id)
                # Determine why it couldn't be assigned
                reason = self._determine_infeasibility_reason(
                    visit, visit_idx, model
                )
                reasons.append(reason)

        return unassigned_ids, reasons

    def calculate_objective(
        self,
        routes: list[RouteModel],
        model: RoutingModel,
        continuity_score: float = 0.0,
        preference_score: float = 0.0,
        punctuality_score: float = 0.0,
    ) -> float:
        """Calculate the objective function as a weighted sum.

        Formula: w1*travel_time + w2*mileage + w3*overtime
                - w4*continuity - w5*preference - w6*balance - w7*punctuality

        Lower values are better (minimisation).

        Args:
            routes: List of computed routes.
            model: The RoutingModel with carer info for overtime calculation.
            continuity_score: Proportion of visits assigned to usual carer (0-1).
            preference_score: Proportion of visits assigned to preferred carer (0-1).
            punctuality_score: Proportion of visits starting within 15 min of preferred time (0-1).

        Returns:
            The objective function score (lower is better).
        """
        total_travel_time = sum(r.total_travel_minutes for r in routes) / 60.0  # hours
        total_mileage = sum(r.total_mileage for r in routes)

        # Calculate overtime per carer
        total_overtime = 0.0
        carer_hours: list[float] = []

        for route in routes:
            # Total working time = visit durations + travel time
            visit_duration_mins = sum(
                self._get_visit_duration(stop.visit_id, model.visits)
                for stop in route.stops
            )
            total_working_mins = visit_duration_mins + route.total_travel_minutes
            total_working_hours = total_working_mins / 60.0
            carer_hours.append(total_working_hours)

            # Find carer's max hours
            carer_max = self._get_carer_max_hours(route.carer_id, model.carers)
            if total_working_hours > carer_max:
                total_overtime += total_working_hours - carer_max

        # Workload balance: minimise difference between most and least loaded
        if carer_hours:
            balance_score = 1.0 - (
                (max(carer_hours) - min(carer_hours)) / max(max(carer_hours), 1.0)
            )
        else:
            balance_score = 1.0

        # Compute weighted sum
        objective = (
            W_TRAVEL_TIME * total_travel_time
            + W_MILEAGE * total_mileage
            + W_OVERTIME * total_overtime
            - W_CONTINUITY * continuity_score
            - W_PREFERENCE * preference_score
            - W_BALANCE * balance_score
            - W_PUNCTUALITY * punctuality_score
        )

        return round(objective, 4)

    # --- Private helpers ---

    @staticmethod
    def _node_to_matrix_idx(node: int, num_visits: int, num_vehicles: int) -> int:
        """Map solver node to travel_matrix location index.

        Travel matrix layout: [carer_0_home, ..., carer_N_home, visit_0, ..., visit_M]
        Solver node layout: [visit_0, ..., visit_M, depot_0, ..., depot_N]
        """
        if node < num_visits:
            # Visit node → travel_matrix index is num_vehicles + node
            return num_vehicles + node
        else:
            # Depot node → travel_matrix index is (node - num_visits)
            return node - num_visits

    @staticmethod
    def _calculate_route_cost(travel_minutes: int, mileage: float) -> float:
        """Calculate route cost from mileage and travel time.

        Cost = £0.45/mile + £15/hour of travel time.
        """
        travel_hours = travel_minutes / 60.0
        return (COST_PER_MILE * mileage) + (COST_PER_HOUR_TRAVEL * travel_hours)

    @staticmethod
    def _get_visit_duration(visit_id: int, visits: list[VisitModel]) -> int:
        """Get the duration in minutes for a visit by ID."""
        for visit in visits:
            if visit.id == visit_id:
                return visit.duration_minutes
        return 0

    @staticmethod
    def _get_carer_max_hours(carer_id: int, carers: list[CarerModel]) -> float:
        """Get a carer's max working hours by ID."""
        for carer in carers:
            if carer.id == carer_id:
                return carer.max_working_hours
        return 8.0  # Default fallback

    def _determine_infeasibility_reason(
        self,
        visit: VisitModel,
        visit_idx: int,
        model: RoutingModel,
    ) -> InfeasibilityReason:
        """Determine which constraint prevented a visit from being assigned.

        Analyses skill matching, time windows, and capacity to identify
        the most likely reason for infeasibility.
        """
        num_vehicles = len(model.carers)
        num_visits = len(model.visits)

        # Check skill matching first
        if visit.required_skills:
            required = set(visit.required_skills)
            qualified_carers = [
                carer.id
                for carer in model.carers
                if required.issubset(set(carer.skills))
            ]
            if not qualified_carers:
                return InfeasibilityReason(
                    visit_id=visit.id,
                    carer_ids=model.carer_ids,
                    constraint_name="skill_matching",
                    reason=f"No carer has required skills: {', '.join(visit.required_skills)}",
                )

        # Check time window feasibility (can any carer reach within the window?)
        window_start = _time_str_to_minutes(visit.window_start)
        window_end = _time_str_to_minutes(visit.window_end)
        latest_start = window_end - visit.duration_minutes

        unreachable_carers: list[int] = []
        for vehicle_id, carer in enumerate(model.carers):
            # Check if carer can reach the visit from their depot within the window
            depot_loc = vehicle_id  # carer home is at index vehicle_id in matrix
            visit_loc = num_vehicles + visit_idx
            travel_seconds = model.travel_matrix.durations[depot_loc][visit_loc]
            travel_minutes = (travel_seconds + 59) // 60

            # Earliest possible arrival from depot
            if travel_minutes > latest_start:
                unreachable_carers.append(carer.id)

        if len(unreachable_carers) == num_vehicles:
            return InfeasibilityReason(
                visit_id=visit.id,
                carer_ids=unreachable_carers,
                constraint_name="time_window",
                reason=f"No carer can reach visit within window {visit.window_start}-{visit.window_end}",
            )

        # Check working hours capacity
        overloaded_carers: list[int] = []
        for carer in model.carers:
            max_minutes = int(carer.max_working_hours * 60)
            if visit.duration_minutes > max_minutes:
                overloaded_carers.append(carer.id)

        if len(overloaded_carers) == num_vehicles:
            return InfeasibilityReason(
                visit_id=visit.id,
                carer_ids=overloaded_carers,
                constraint_name="max_working_hours",
                reason=f"Visit duration ({visit.duration_minutes} min) exceeds all carers' available capacity",
            )

        # Default: combination of constraints
        return InfeasibilityReason(
            visit_id=visit.id,
            carer_ids=model.carer_ids,
            constraint_name="combined_constraints",
            reason="Visit cannot be assigned due to combination of time window, capacity, and skill constraints",
        )
