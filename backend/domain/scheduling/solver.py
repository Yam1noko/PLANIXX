from dataclasses import dataclass
from datetime import datetime
from math import ceil
from time import monotonic

from ortools.sat.python import cp_model

from backend.domain.personalization.solver_preferences import SolverUserPreferences
from backend.domain.scheduling.time_slots import (
    datetime_to_slot,
    datetime_to_slot_floor,
    interval_inside_any_window,
    interval_overlaps_any_window,
    slot_to_datetime,
)
from backend.models.scheduling import (
    BusyInterval,
    PlanningRequest,
    PlanningResult,
    ScheduleVariant,
    ScheduledTask,
    TaskPlacementHint,
    TaskInput,
    TimeWindow,
    UnscheduledTask,
    Violation,
)


INTERNAL_VARIANT_MULTIPLIER = 1
MAX_INTERNAL_VARIANTS = 5
DIVERSITY_BONUS_MULTIPLIER = 240
MIN_VARIANT_DIFFERENCE_RATIO = 0.35
MIN_VARIANT_DIFFERENCE_FLOOR = 2


@dataclass
class PreparedTask:
    id: str
    task_id: str
    title: str
    source_task: TaskInput
    duration_slots: int
    duration_minutes: int
    effective_load_minutes: int
    priority: int
    is_mandatory: bool
    category: str | None
    energy_required: str | None
    split_part_index: int | None
    split_part_count: int | None
    allowed_starts: list[int]
    preferred_starts: set[int]


@dataclass(frozen=True)
class VariantStrategy:
    name: str
    quality_slack_multiplier: int
    preferred_block: str | None = None
    start_bias: int = 0
    duration_penalty_multiplier: int = 0


class OrToolsSchedulerSolver:
    def solve(
        self,
        request: PlanningRequest,
        user_preferences: SolverUserPreferences | None = None,
    ) -> PlanningResult:
        violations: list[Violation] = []
        solve_started_at = monotonic()

        total_slots = self._get_total_slots(request)
        if total_slots <= 0:
            return self._build_single_variant_result(
                request=request,
                scheduled_tasks=[],
                unscheduled_tasks=self._all_tasks_unscheduled(
                    request,
                    "INVALID_TIME_RANGE",
                ),
                violations=[
                    Violation(
                        code="INVALID_TIME_RANGE",
                        message="Invalid planning time range.",
                    )
                ],
                solver_status="INVALID_REQUEST",
                strategy="invalid_request_fallback",
            )

        available_prefix = self._build_slot_coverage_prefix(
            request=request,
            total_slots=total_slots,
            windows=request.available_windows,
        )
        busy_prefix = self._build_slot_coverage_prefix(
            request=request,
            total_slots=total_slots,
            windows=request.busy_intervals,
        )
        prepared_tasks, pre_unscheduled, pre_violations = self._prepare_tasks(
            request=request,
            total_slots=total_slots,
            available_prefix=available_prefix,
            busy_prefix=busy_prefix,
            user_preferences=user_preferences,
        )
        violations.extend(pre_violations)
        warm_start_hints = self._build_warm_start_hints(
            request=request,
            tasks_for_solver=prepared_tasks,
        )

        tasks_for_solver = [
            task
            for task in prepared_tasks
            if task.allowed_starts
        ]

        if not tasks_for_solver:
            return self._build_single_variant_result(
                request=request,
                scheduled_tasks=[],
                unscheduled_tasks=pre_unscheduled,
                violations=violations,
                solver_status="NO_TASKS_TO_SCHEDULE",
                strategy="empty_fallback",
            )

        base_start_scores = self._build_base_start_scores(
            request=request,
            tasks_for_solver=tasks_for_solver,
            user_preferences=user_preferences,
        )
        requested_variant_count = self._resolve_requested_variant_count(request)
        internal_variant_target = self._resolve_internal_variant_target(
            request=request,
            requested_variant_count=requested_variant_count,
        )
        strategies = self._build_variant_strategies(
            max_variants=internal_variant_target
        )

        def remaining_budget_seconds() -> float:
            return max(
                0.0,
                self._resolve_total_solve_budget_seconds(request)
                - (monotonic() - solve_started_at),
            )

        first_result, first_status_name = self._solve_variant(
            request=request,
            tasks_for_solver=tasks_for_solver,
            pre_unscheduled=pre_unscheduled,
            user_preferences=user_preferences,
            base_start_scores=base_start_scores,
            strategy=strategies[0],
            previous_solutions=[],
            best_base_score=None,
            variant_index=0,
            min_difference=0,
            warm_start_hints=warm_start_hints,
            enforce_mandatory=True,
            time_limit_seconds=remaining_budget_seconds(),
        )

        mandatory_constraints_relaxed = False
        if first_result is None:
            first_result, relaxed_status_name = self._solve_variant(
                request=request,
                tasks_for_solver=tasks_for_solver,
                pre_unscheduled=pre_unscheduled,
                user_preferences=user_preferences,
                base_start_scores=base_start_scores,
                strategy=strategies[0],
                previous_solutions=[],
                best_base_score=None,
                variant_index=0,
                min_difference=0,
                warm_start_hints=warm_start_hints,
                enforce_mandatory=False,
                time_limit_seconds=remaining_budget_seconds(),
            )
            mandatory_constraints_relaxed = first_result is not None
            last_solver_status = relaxed_status_name
        else:
            last_solver_status = first_status_name

        if first_result is None:
            return self._build_greedy_fallback_result(
                request=request,
                tasks_for_solver=tasks_for_solver,
                pre_unscheduled=pre_unscheduled,
                base_start_scores=base_start_scores,
                user_preferences=user_preferences,
                violations=violations,
                solver_status=last_solver_status,
            )

        if mandatory_constraints_relaxed:
            violations.append(
                Violation(
                    code="MANDATORY_CONSTRAINTS_RELAXED",
                    message="Mandatory constraints were relaxed to build a fallback schedule.",
                )
            )
            first_result["variant"].metadata = {
                **first_result["variant"].metadata,
                "mandatory_constraints_relaxed": True,
            }

        candidate_variants = [first_result["variant"]]
        previous_solutions = [first_result["solution"]]
        best_base_score = first_result["base_score"]

        min_difference_candidates = self._build_min_difference_candidates(
            task_count=len(request.tasks),
        )

        for variant_index, strategy in enumerate(strategies[1:], start=1):
            if remaining_budget_seconds() <= 0:
                break
            solved_variant = None

            for min_difference in min_difference_candidates:
                if remaining_budget_seconds() <= 0:
                    break
                solved_variant, _ = self._solve_variant(
                    request=request,
                    tasks_for_solver=tasks_for_solver,
                    pre_unscheduled=pre_unscheduled,
                    user_preferences=user_preferences,
                    base_start_scores=base_start_scores,
                    strategy=strategy,
                    previous_solutions=previous_solutions,
                    best_base_score=best_base_score,
                    variant_index=variant_index,
                    min_difference=min_difference,
                    warm_start_hints=None,
                    enforce_mandatory=not mandatory_constraints_relaxed,
                    time_limit_seconds=remaining_budget_seconds(),
                )
                if solved_variant is not None:
                    break

            if solved_variant is None:
                continue

            if mandatory_constraints_relaxed:
                solved_variant["variant"].metadata = {
                    **solved_variant["variant"].metadata,
                    "mandatory_constraints_relaxed": True,
                }

            candidate_variants.append(solved_variant["variant"])
            previous_solutions.append(solved_variant["solution"])

            if len(candidate_variants) >= len(strategies):
                break

        variants = self._filter_distinct_variants(
            request=request,
            candidates=candidate_variants,
            max_variants=requested_variant_count,
        )

        for index, variant in enumerate(variants, start=1):
            variant.variant_id = index

        best_variant = max(
            variants,
            key=lambda item: (
                item.score or float("-inf"),
                item.metadata.get("selection_score", float("-inf")),
            ),
        )

        return PlanningResult(
            status=self._get_result_status(best_variant),
            scheduled_tasks=best_variant.scheduled_tasks,
            unscheduled_tasks=best_variant.unscheduled_tasks,
            schedule_variants=variants,
            violations=violations,
            metadata={
                **best_variant.metadata,
                "variant_count": len(variants),
            },
        )

    def _build_schedule(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        assignment_vars: dict[tuple[str, int], cp_model.IntVar],
        solver: cp_model.CpSolver,
        pre_unscheduled: list[UnscheduledTask],
    ) -> tuple[list[ScheduledTask], list[UnscheduledTask]]:
        scheduled_tasks: list[ScheduledTask] = []
        scheduled_task_ids: set[str] = set()

        for task in tasks_for_solver:
            for start_slot in task.allowed_starts:
                if solver.Value(assignment_vars[(task.id, start_slot)]) != 1:
                    continue

                start = slot_to_datetime(
                    start_slot,
                    request.planning_start,
                    request.slot_minutes,
                )
                end = slot_to_datetime(
                    start_slot + task.duration_slots,
                    request.planning_start,
                    request.slot_minutes,
                )

                scheduled_tasks.append(
                    ScheduledTask(
                        task_id=task.task_id,
                        title=task.title,
                        task=task.source_task,
                        start=start,
                        end=end,
                        duration_minutes=task.duration_minutes,
                        priority=task.priority,
                        is_mandatory=task.is_mandatory,
                        split_part_index=task.split_part_index,
                        split_part_count=task.split_part_count,
                    )
                )
                scheduled_task_ids.add(task.task_id)

        scheduled_tasks.sort(key=lambda item: item.start)

        unscheduled_tasks = list(pre_unscheduled)
        task_by_id = {
            task.task_id: task
            for task in tasks_for_solver
        }
        for task_id, task in task_by_id.items():
            if task_id in scheduled_task_ids:
                continue

            unscheduled_tasks.append(
                UnscheduledTask(
                    task_id=task_id,
                    title=task.title,
                    task=task.source_task,
                    reason="NO_AVAILABLE_SLOT",
                )
            )

        return scheduled_tasks, unscheduled_tasks

    def _solve_variant(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        pre_unscheduled: list[UnscheduledTask],
        user_preferences: SolverUserPreferences | None,
        base_start_scores: dict[tuple[str, int], int],
        strategy: VariantStrategy,
        previous_solutions: list[dict[tuple[str, int], int]],
        best_base_score: int | None,
        variant_index: int,
        min_difference: int,
        warm_start_hints: dict[tuple[str, int], int] | None,
        enforce_mandatory: bool,
        time_limit_seconds: float,
    ) -> tuple[dict | None, str]:
        if time_limit_seconds <= 0:
            return None, "TIME_BUDGET_EXHAUSTED"

        model, assignment_vars = self._build_base_model(
            request=request,
            tasks_for_solver=tasks_for_solver,
            user_preferences=user_preferences,
            enforce_mandatory=enforce_mandatory,
        )

        base_terms = [
            base_start_scores[(task.id, start_slot)]
            * assignment_vars[(task.id, start_slot)]
            for task in tasks_for_solver
            for start_slot in task.allowed_starts
        ]
        base_objective = sum(base_terms)

        if best_base_score is not None:
            model.Add(
                base_objective
                >= best_base_score
                - self._get_quality_slack(best_base_score, strategy, variant_index)
            )

        diversity_bonus = 0
        if previous_solutions:
            for solution in previous_solutions:
                diff_terms = [
                    self._get_difference_term(
                        assignment_vars[key],
                        solution.get(key, 0),
                    )
                    for key in assignment_vars
                ]
                model.Add(sum(diff_terms) >= max(1, min_difference))
                diversity_bonus += sum(diff_terms)

        strategy_bonus = self._build_variant_style_bonus(
            request=request,
            tasks_for_solver=tasks_for_solver,
            assignment_vars=assignment_vars,
            strategy=strategy,
        )

        total_objective = base_objective + strategy_bonus
        if previous_solutions:
            total_objective += diversity_bonus * DIVERSITY_BONUS_MULTIPLIER

        model.Maximize(total_objective)

        if warm_start_hints:
            self._apply_warm_start_hints(model, assignment_vars, warm_start_hints)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.1, time_limit_seconds)
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = variant_index + 1

        status = solver.Solve(model)
        status_name = solver.StatusName(status)
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            return None, status_name

        scheduled_tasks, unscheduled_tasks = self._build_schedule(
            request=request,
            tasks_for_solver=tasks_for_solver,
            assignment_vars=assignment_vars,
            solver=solver,
            pre_unscheduled=pre_unscheduled,
        )
        solution = {
            key: solver.Value(variable)
            for key, variable in assignment_vars.items()
        }

        variant = ScheduleVariant(
            variant_id=variant_index + 1,
            scheduled_tasks=scheduled_tasks,
            unscheduled_tasks=unscheduled_tasks,
            score=int(solver.Value(base_objective)),
            metadata={
                "solver_status": status_name,
                "strategy": strategy.name,
                "min_difference": min_difference,
                "selection_score": int(solver.ObjectiveValue()),
                "total_scheduled_minutes": sum(
                    task.duration_minutes
                    for task in scheduled_tasks
                ),
                "total_unscheduled_minutes": self._get_total_unscheduled_minutes(
                    request,
                    unscheduled_tasks,
                ),
            },
        )
        return (
            {
                "variant": variant,
                "solution": solution,
                "base_score": int(solver.Value(base_objective)),
            },
            status_name,
        )

    def _resolve_requested_variant_count(self, request: PlanningRequest) -> int:
        if request.settings.mode == "quick":
            return 1

        return request.settings.max_schedule_variants

    def _resolve_time_limit_seconds(self, request: PlanningRequest) -> int:
        if request.settings.mode == "quick":
            return 3

        return 5

    def _resolve_total_solve_budget_seconds(self, request: PlanningRequest) -> int:
        if request.settings.mode == "quick":
            return 2

        return 4

    def _resolve_internal_variant_target(
        self,
        *,
        request: PlanningRequest,
        requested_variant_count: int,
    ) -> int:
        if request.settings.mode == "quick":
            return 1

        return min(
            MAX_INTERNAL_VARIANTS,
            max(
                1,
                min(
                    requested_variant_count,
                    requested_variant_count * INTERNAL_VARIANT_MULTIPLIER,
                ),
            ),
        )

    def _build_base_model(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        user_preferences: SolverUserPreferences | None,
        enforce_mandatory: bool,
    ) -> tuple[cp_model.CpModel, dict[tuple[str, int], cp_model.IntVar]]:
        model = cp_model.CpModel()
        assignment_vars: dict[tuple[str, int], cp_model.IntVar] = {}

        for task in tasks_for_solver:
            for start_slot in task.allowed_starts:
                assignment_vars[(task.id, start_slot)] = model.NewBoolVar(
                    f"x_{task.id}_{start_slot}"
                )

        for task in tasks_for_solver:
            task_vars = [
                assignment_vars[(task.id, start_slot)]
                for start_slot in task.allowed_starts
            ]

            if enforce_mandatory and task.is_mandatory:
                model.Add(sum(task_vars) == 1)
            else:
                model.Add(sum(task_vars) <= 1)

        self._add_split_order_constraints(
            model=model,
            request=request,
            tasks_for_solver=tasks_for_solver,
            assignment_vars=assignment_vars,
            user_preferences=user_preferences,
        )

        optional_split_task_ids = {
            task.task_id
            for task in tasks_for_solver
            if task.split_part_count is not None
            and (not task.is_mandatory or not enforce_mandatory)
        }
        for task_id in optional_split_task_ids:
            split_tasks = [
                task
                for task in tasks_for_solver
                if task.task_id == task_id
            ]
            group_var = model.NewBoolVar(f"schedule_{task_id}")

            for task in split_tasks:
                model.Add(
                    sum(
                        assignment_vars[(task.id, start_slot)]
                        for start_slot in task.allowed_starts
                    )
                    == group_var
                )

        slot_bounds = self._get_relevant_slot_bounds(tasks_for_solver)
        for slot in range(slot_bounds[0], slot_bounds[1]):
            occupying_vars = []

            for task in tasks_for_solver:
                for start_slot in task.allowed_starts:
                    end_slot = start_slot + task.duration_slots
                    if start_slot <= slot < end_slot:
                        occupying_vars.append(assignment_vars[(task.id, start_slot)])

            if occupying_vars:
                model.Add(sum(occupying_vars) <= 1)

        return model, assignment_vars

    def _get_relevant_slot_bounds(
        self,
        tasks_for_solver: list[PreparedTask],
    ) -> tuple[int, int]:
        if not tasks_for_solver:
            return 0, 0

        min_slot = min(
            min(task.allowed_starts)
            for task in tasks_for_solver
            if task.allowed_starts
        )
        max_slot = max(
            start_slot + task.duration_slots
            for task in tasks_for_solver
            for start_slot in task.allowed_starts
        )
        return min_slot, max_slot

    def _build_greedy_fallback_result(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        pre_unscheduled: list[UnscheduledTask],
        base_start_scores: dict[tuple[str, int], int],
        user_preferences: SolverUserPreferences | None,
        violations: list[Violation],
        solver_status: str,
    ) -> PlanningResult:
        scheduled_tasks, unscheduled_tasks = self._build_greedy_schedule(
            request=request,
            tasks_for_solver=tasks_for_solver,
            pre_unscheduled=pre_unscheduled,
            base_start_scores=base_start_scores,
            user_preferences=user_preferences,
        )
        fallback_violations = [
            *violations,
            Violation(
                code="SOLVER_FALLBACK_USED",
                message=(
                    "Greedy fallback was used because the solver did not produce "
                    f"a feasible solution (status: {solver_status})."
                ),
            ),
        ]
        return self._build_single_variant_result(
            request=request,
            scheduled_tasks=scheduled_tasks,
            unscheduled_tasks=unscheduled_tasks,
            violations=fallback_violations,
            solver_status=solver_status,
            strategy="greedy_fallback",
        )

    def _build_greedy_schedule(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        pre_unscheduled: list[UnscheduledTask],
        base_start_scores: dict[tuple[str, int], int],
        user_preferences: SolverUserPreferences | None,
    ) -> tuple[list[ScheduledTask], list[UnscheduledTask]]:
        pre_unscheduled_task_ids = {
            task.task_id
            for task in pre_unscheduled
        }
        tasks_by_id: dict[str, list[PreparedTask]] = {}
        for task in tasks_for_solver:
            if task.task_id in pre_unscheduled_task_ids:
                continue
            tasks_by_id.setdefault(task.task_id, []).append(task)

        ordered_task_groups = sorted(
            (
                sorted(
                    parts,
                    key=lambda item: item.split_part_index or 0,
                )
                for parts in tasks_by_id.values()
            ),
            key=lambda parts: self._build_greedy_task_order_key(request, parts),
        )

        occupied_slots: set[int] = set()
        scheduled_tasks: list[ScheduledTask] = []
        scheduled_task_ids: set[str] = set()

        for task_parts in ordered_task_groups:
            selected_starts = self._select_greedy_starts_for_task(
                request=request,
                task_parts=task_parts,
                occupied_slots=occupied_slots,
                base_start_scores=base_start_scores,
                user_preferences=user_preferences,
            )
            if selected_starts is None:
                continue

            for part, start_slot in zip(task_parts, selected_starts):
                occupied_slots.update(
                    range(start_slot, start_slot + part.duration_slots)
                )
                scheduled_tasks.append(
                    self._build_scheduled_task_from_prepared_task(
                        request=request,
                        task=part,
                        start_slot=start_slot,
                    )
                )
            scheduled_task_ids.add(task_parts[0].task_id)

        scheduled_tasks.sort(key=lambda item: item.start)

        unscheduled_tasks = list(pre_unscheduled)
        for task_id, task_parts in tasks_by_id.items():
            if task_id in scheduled_task_ids:
                continue

            task = task_parts[0].source_task
            unscheduled_tasks.append(
                UnscheduledTask(
                    task_id=task.id,
                    title=task.title,
                    task=task,
                    reason="FALLBACK_NOT_SELECTED",
                )
            )

        return scheduled_tasks, unscheduled_tasks

    def _build_greedy_task_order_key(
        self,
        request: PlanningRequest,
        task_parts: list[PreparedTask],
    ) -> tuple:
        source_task = task_parts[0].source_task
        hard_latest_end = (
            source_task.latest_end
            or source_task.deadline
            or request.planning_end
        )
        total_duration = sum(part.duration_minutes for part in task_parts)
        return (
            0 if source_task.is_fixed else 1,
            0 if source_task.is_mandatory else 1,
            hard_latest_end,
            -source_task.priority,
            total_duration,
            source_task.title,
        )

    def _select_greedy_starts_for_task(
        self,
        request: PlanningRequest,
        task_parts: list[PreparedTask],
        occupied_slots: set[int],
        base_start_scores: dict[tuple[str, int], int],
        user_preferences: SolverUserPreferences | None,
    ) -> list[int] | None:
        tentative_occupied: set[int] = set()

        def backtrack(
            part_index: int,
            minimum_start_slot: int,
            selected_starts: list[int],
        ) -> list[int] | None:
            if part_index >= len(task_parts):
                return list(selected_starts)

            part = task_parts[part_index]
            candidate_starts = [
                start_slot
                for start_slot in part.allowed_starts
                if start_slot >= minimum_start_slot
                and self._slots_are_free(
                    start_slot,
                    part.duration_slots,
                    occupied_slots,
                    tentative_occupied,
                )
            ]
            ranked_starts = self._rank_greedy_candidate_starts(
                part=part,
                candidate_starts=candidate_starts,
                base_start_scores=base_start_scores,
            )

            for start_slot in ranked_starts:
                occupied_range = range(start_slot, start_slot + part.duration_slots)
                tentative_occupied.update(occupied_range)
                selected_starts.append(start_slot)

                next_minimum_start_slot = 0
                if part_index + 1 < len(task_parts):
                    next_minimum_start_slot = (
                        start_slot
                        + part.duration_slots
                        + self._get_required_gap_slots(
                            request=request,
                            task=part,
                            user_preferences=user_preferences,
                        )
                    )

                result = backtrack(
                    part_index + 1,
                    next_minimum_start_slot,
                    selected_starts,
                )
                if result is not None:
                    return result

                selected_starts.pop()
                tentative_occupied.difference_update(occupied_range)

            return None

        return backtrack(0, 0, [])

    def _rank_greedy_candidate_starts(
        self,
        part: PreparedTask,
        candidate_starts: list[int],
        base_start_scores: dict[tuple[str, int], int],
    ) -> list[int]:
        ranked_starts = sorted(
            candidate_starts,
            key=lambda start_slot: (
                -base_start_scores.get((part.id, start_slot), 0),
                start_slot,
            ),
        )
        if len(ranked_starts) <= 120:
            return ranked_starts

        earliest_starts = sorted(candidate_starts)[:40]
        reduced_starts: list[int] = []
        for start_slot in [*ranked_starts[:80], *earliest_starts]:
            if start_slot not in reduced_starts:
                reduced_starts.append(start_slot)
        return reduced_starts

    @staticmethod
    def _slots_are_free(
        start_slot: int,
        duration_slots: int,
        occupied_slots: set[int],
        tentative_occupied: set[int],
    ) -> bool:
        return all(
            slot not in occupied_slots and slot not in tentative_occupied
            for slot in range(start_slot, start_slot + duration_slots)
        )

    def _build_scheduled_task_from_prepared_task(
        self,
        request: PlanningRequest,
        task: PreparedTask,
        start_slot: int,
    ) -> ScheduledTask:
        start = slot_to_datetime(
            start_slot,
            request.planning_start,
            request.slot_minutes,
        )
        end = slot_to_datetime(
            start_slot + task.duration_slots,
            request.planning_start,
            request.slot_minutes,
        )
        return ScheduledTask(
            task_id=task.task_id,
            title=task.title,
            task=task.source_task,
            start=start,
            end=end,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            is_mandatory=task.is_mandatory,
            split_part_index=task.split_part_index,
            split_part_count=task.split_part_count,
        )

    def _build_base_start_scores(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        user_preferences: SolverUserPreferences | None,
    ) -> dict[tuple[str, int], int]:
        return {
            (task.id, start_slot): self._calculate_start_score(
                request=request,
                task=task,
                start_slot=start_slot,
                user_preferences=user_preferences,
            )
            for task in tasks_for_solver
            for start_slot in task.allowed_starts
        }

    def _build_variant_strategies(self, max_variants: int) -> list[VariantStrategy]:
        base_strategies = [
            VariantStrategy(name="balanced", quality_slack_multiplier=0),
            VariantStrategy(name="early", quality_slack_multiplier=1, start_bias=-3),
            VariantStrategy(name="late", quality_slack_multiplier=1, start_bias=2),
            VariantStrategy(name="compact", quality_slack_multiplier=1, start_bias=-5),
            VariantStrategy(name="spread", quality_slack_multiplier=2, start_bias=1),
            VariantStrategy(
                name="morning_peak",
                quality_slack_multiplier=1,
                preferred_block="morning",
            ),
            VariantStrategy(
                name="afternoon_peak",
                quality_slack_multiplier=1,
                preferred_block="afternoon",
            ),
            VariantStrategy(
                name="evening_peak",
                quality_slack_multiplier=2,
                preferred_block="evening",
            ),
            VariantStrategy(
                name="light_load",
                quality_slack_multiplier=2,
                duration_penalty_multiplier=3,
            ),
            VariantStrategy(
                name="front_loaded",
                quality_slack_multiplier=2,
                start_bias=-4,
                preferred_block="morning",
            ),
        ]

        if max_variants <= len(base_strategies):
            return base_strategies[:max_variants]

        strategies: list[VariantStrategy] = []
        cycle_count = ceil(max_variants / len(base_strategies))

        for cycle_index in range(cycle_count):
            for base_strategy in base_strategies:
                if len(strategies) >= max_variants:
                    break

                strategies.append(
                    VariantStrategy(
                        name=(
                            base_strategy.name
                            if cycle_index == 0
                            else f"{base_strategy.name}_{cycle_index + 1}"
                        ),
                        quality_slack_multiplier=(
                            base_strategy.quality_slack_multiplier + cycle_index
                        ),
                        preferred_block=base_strategy.preferred_block,
                        start_bias=base_strategy.start_bias,
                        duration_penalty_multiplier=(
                            base_strategy.duration_penalty_multiplier
                        ),
                    )
                )

        return strategies

    def _build_min_difference_candidates(self, task_count: int) -> list[int]:
        target_difference = max(
            3,
            min(8, ceil(task_count * 0.5)),
        )
        fallback_difference = max(
            MIN_VARIANT_DIFFERENCE_FLOOR,
            ceil(task_count * 0.3),
        )
        candidates = [
            target_difference,
            max(fallback_difference, target_difference - 1),
            fallback_difference,
            MIN_VARIANT_DIFFERENCE_FLOOR,
        ]
        unique_candidates: list[int] = []
        for value in candidates:
            if value not in unique_candidates:
                unique_candidates.append(value)
        return unique_candidates

    def _filter_distinct_variants(
        self,
        request: PlanningRequest,
        candidates: list[ScheduleVariant],
        max_variants: int,
    ) -> list[ScheduleVariant]:
        ranked_candidates = sorted(
            candidates,
            key=lambda variant: (
                variant.score or float("-inf"),
                variant.metadata.get("selection_score", float("-inf")),
                variant.metadata.get("total_scheduled_minutes", 0),
            ),
            reverse=True,
        )

        distinct_variants: list[ScheduleVariant] = []

        for candidate in ranked_candidates:
            closest_difference = None
            closest_ratio = None
            is_duplicate = False
            is_too_similar = False

            for accepted in distinct_variants:
                difference_count, total_entries = self._compare_variants(
                    request=request,
                    left=candidate,
                    right=accepted,
                )
                min_difference = self._get_similarity_difference_threshold(total_entries)
                difference_ratio = (
                    difference_count / total_entries if total_entries > 0 else 0.0
                )

                if closest_difference is None or difference_count < closest_difference:
                    closest_difference = difference_count
                    closest_ratio = difference_ratio

                if difference_count == 0:
                    is_duplicate = True
                    break

                if difference_count < min_difference:
                    is_too_similar = True
                    break

            candidate.metadata = {
                **candidate.metadata,
                "similarity": {
                    "closest_difference_count": closest_difference,
                    "closest_difference_ratio": (
                        round(closest_ratio, 4)
                        if closest_ratio is not None
                        else None
                    ),
                    "dropped_as_duplicate": is_duplicate,
                    "dropped_as_too_similar": is_too_similar,
                },
            }

            if is_duplicate or is_too_similar:
                continue

            distinct_variants.append(candidate)
            if len(distinct_variants) >= max_variants:
                break

        return distinct_variants

    def _compare_variants(
        self,
        request: PlanningRequest,
        left: ScheduleVariant,
        right: ScheduleVariant,
    ) -> tuple[int, int]:
        left_fingerprint = self._build_variant_fingerprint(request, left)
        right_fingerprint = self._build_variant_fingerprint(request, right)
        keys = sorted(set(left_fingerprint) | set(right_fingerprint))

        difference_count = sum(
            1
            for key in keys
            if left_fingerprint.get(key) != right_fingerprint.get(key)
        )
        return difference_count, len(keys)

    def _build_variant_fingerprint(
        self,
        request: PlanningRequest,
        variant: ScheduleVariant,
    ) -> dict[str, tuple[str, str] | str]:
        fingerprint: dict[str, tuple[str, str] | str] = {}

        for task in request.tasks:
            fingerprint[task.id] = "unscheduled"

        for scheduled_task in variant.scheduled_tasks:
            key = self._get_variant_task_key(scheduled_task)
            if scheduled_task.split_part_index is not None:
                fingerprint.pop(scheduled_task.task_id, None)

            fingerprint[key] = (
                scheduled_task.start.isoformat(),
                scheduled_task.end.isoformat(),
            )

        for unscheduled_task in variant.unscheduled_tasks:
            key = self._get_variant_task_key(unscheduled_task)
            fingerprint[key] = "unscheduled"

        return fingerprint

    def _get_variant_task_key(
        self,
        task: ScheduledTask | UnscheduledTask,
    ) -> str:
        split_part_index = getattr(task, "split_part_index", None)
        split_part_count = getattr(task, "split_part_count", None)

        if split_part_index is None:
            return task.task_id

        return f"{task.task_id}#part{split_part_index}of{split_part_count}"

    def _get_similarity_difference_threshold(self, total_entries: int) -> int:
        return max(
            MIN_VARIANT_DIFFERENCE_FLOOR,
            ceil(total_entries * MIN_VARIANT_DIFFERENCE_RATIO),
        )

    def _get_quality_slack(
        self,
        best_base_score: int,
        strategy: VariantStrategy,
        variant_index: int,
    ) -> int:
        base_slack = max(300, min(1400, best_base_score // 30))
        return base_slack + strategy.quality_slack_multiplier * 250 + variant_index * 75

    def _build_variant_style_bonus(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        assignment_vars: dict[tuple[str, int], cp_model.IntVar],
        strategy: VariantStrategy,
    ):
        if (
            strategy.start_bias == 0
            and strategy.preferred_block is None
            and strategy.duration_penalty_multiplier == 0
        ):
            return 0

        bonus_terms = []

        for task in tasks_for_solver:
            for start_slot in task.allowed_starts:
                bonus = strategy.start_bias * start_slot

                if strategy.preferred_block is not None:
                    start_dt = slot_to_datetime(
                        start_slot,
                        request.planning_start,
                        request.slot_minutes,
                    )
                    if self._get_time_block(start_dt) == strategy.preferred_block:
                        bonus += 120

                if strategy.duration_penalty_multiplier > 0:
                    bonus -= (
                        task.effective_load_minutes - task.duration_minutes
                    ) * strategy.duration_penalty_multiplier

                if bonus != 0:
                    bonus_terms.append(
                        bonus * assignment_vars[(task.id, start_slot)]
                    )

        if not bonus_terms:
            return 0

        return sum(bonus_terms)

    def _get_difference_term(
        self,
        variable: cp_model.IntVar,
        current_value: int,
    ):
        if current_value == 1:
            return 1 - variable

        return variable

    def _add_split_order_constraints(
        self,
        model: cp_model.CpModel,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
        assignment_vars: dict[tuple[str, int], cp_model.IntVar],
        user_preferences: SolverUserPreferences | None,
    ) -> None:
        split_task_ids = {
            task.task_id
            for task in tasks_for_solver
            if task.split_part_count is not None
        }

        for task_id in split_task_ids:
            split_tasks = sorted(
                [
                    task
                    for task in tasks_for_solver
                    if task.task_id == task_id
                ],
                key=lambda task: task.split_part_index or 0,
            )

            for previous_task, next_task in zip(split_tasks, split_tasks[1:]):
                required_gap_slots = self._get_required_gap_slots(
                    request=request,
                    task=previous_task,
                    user_preferences=user_preferences,
                )

                for previous_start in previous_task.allowed_starts:
                    previous_end = (
                        previous_start
                        + previous_task.duration_slots
                        + required_gap_slots
                    )

                    for next_start in next_task.allowed_starts:
                        if previous_end <= next_start:
                            continue

                        model.Add(
                            assignment_vars[(previous_task.id, previous_start)]
                            + assignment_vars[(next_task.id, next_start)]
                            <= 1
                        )

    def _get_required_gap_slots(
        self,
        request: PlanningRequest,
        task: PreparedTask,
        user_preferences: SolverUserPreferences | None,
    ) -> int:
        return 0

    def _get_result_status(self, variant: ScheduleVariant) -> str:
        if not variant.scheduled_tasks and variant.unscheduled_tasks:
            return "partial"

        if variant.unscheduled_tasks:
            return "partial"

        return "success"

    def _get_total_unscheduled_minutes(
        self,
        request: PlanningRequest,
        unscheduled_tasks: list[UnscheduledTask],
    ) -> int:
        original_duration_by_id = {
            task.id: task.duration_minutes
            for task in request.tasks
        }
        return sum(
            original_duration_by_id.get(task.task_id, 0)
            for task in unscheduled_tasks
        )

    def _get_total_slots(self, request: PlanningRequest) -> int:
        total_minutes = int(
            (request.planning_end - request.planning_start).total_seconds() // 60
        )
        return total_minutes // request.slot_minutes

    def _get_time_block(self, value: datetime) -> str:
        hour = value.hour

        if 6 <= hour < 12:
            return "morning"

        if 12 <= hour < 18:
            return "afternoon"

        if 18 <= hour < 23:
            return "evening"

        return "night"

    def _build_slot_coverage_prefix(
        self,
        request: PlanningRequest,
        total_slots: int,
        windows: list[TimeWindow] | list[BusyInterval],
    ) -> list[int] | None:
        if not windows:
            return None

        diff = [0] * (total_slots + 1)
        for window in windows:
            start_slot = max(
                0,
                datetime_to_slot(
                    window.start,
                    request.planning_start,
                    request.slot_minutes,
                ),
            )
            end_slot = min(
                total_slots,
                datetime_to_slot_floor(
                    window.end,
                    request.planning_start,
                    request.slot_minutes,
                ),
            )
            if end_slot <= start_slot:
                continue

            diff[start_slot] += 1
            diff[end_slot] -= 1

        prefix = [0] * (total_slots + 1)
        covered_slots = 0
        running = 0
        for slot in range(total_slots):
            running += diff[slot]
            if running > 0:
                covered_slots += 1
            prefix[slot + 1] = covered_slots

        return prefix

    def _build_warm_start_hints(
        self,
        request: PlanningRequest,
        tasks_for_solver: list[PreparedTask],
    ) -> dict[tuple[str, int], int]:
        if not request.settings.use_warm_start and not request.settings.replan_from_current_schedule:
            return {}

        prepared_by_key = {
            (task.task_id, task.split_part_index): task
            for task in tasks_for_solver
        }
        hinted_prepared_ids: set[str] = set()
        hints: dict[tuple[str, int], int] = {}

        for hint in request.placement_hints:
            self._register_warm_start_hint(
                request=request,
                hint=hint,
                prepared_by_key=prepared_by_key,
                hints=hints,
                hinted_prepared_ids=hinted_prepared_ids,
            )

        for task in tasks_for_solver:
            if task.id not in hinted_prepared_ids:
                continue

            for start_slot in task.allowed_starts:
                hints.setdefault((task.id, start_slot), 0)

        return hints

    def _register_warm_start_hint(
        self,
        *,
        request: PlanningRequest,
        hint: TaskPlacementHint,
        prepared_by_key: dict[tuple[str, int | None], PreparedTask],
        hints: dict[tuple[str, int], int],
        hinted_prepared_ids: set[str],
    ) -> None:
        prepared_task = prepared_by_key.get((hint.task_id, hint.split_part_index))
        if prepared_task is None:
            return

        start_slot = datetime_to_slot(
            hint.start,
            request.planning_start,
            request.slot_minutes,
        )
        if start_slot not in prepared_task.allowed_starts:
            return

        hints[(prepared_task.id, start_slot)] = 1
        hinted_prepared_ids.add(prepared_task.id)

    def _apply_warm_start_hints(
        self,
        model: cp_model.CpModel,
        assignment_vars: dict[tuple[str, int], cp_model.IntVar],
        warm_start_hints: dict[tuple[str, int], int],
    ) -> None:
        for key, value in warm_start_hints.items():
            variable = assignment_vars.get(key)
            if variable is None:
                continue
            model.AddHint(variable, value)

    def _prepare_tasks(
        self,
        request: PlanningRequest,
        total_slots: int,
        available_prefix: list[int] | None,
        busy_prefix: list[int] | None,
        user_preferences: SolverUserPreferences | None,
    ) -> tuple[list[PreparedTask], list[UnscheduledTask], list[Violation]]:
        prepared_tasks: list[PreparedTask] = []
        unscheduled: list[UnscheduledTask] = []
        violations: list[Violation] = []

        for task in request.tasks:
            fixed_start_slot = None
            if task.is_fixed:
                fixed_start_slot = datetime_to_slot(
                    task.fixed_start,
                    request.planning_start,
                    request.slot_minutes,
                )

            hard_latest_end = task.latest_end or task.deadline
            candidate_task_parts = self._build_task_parts(
                request=request,
                task=task,
                user_preferences=user_preferences,
            )
            if len(candidate_task_parts) > 1:
                full_task_allowed_starts, full_task_preferred_starts = (
                    self._collect_allowed_starts(
                        request=request,
                        task=task,
                        duration_minutes=task.duration_minutes,
                        total_slots=total_slots,
                        fixed_start_slot=fixed_start_slot,
                        hard_latest_end=hard_latest_end,
                        available_prefix=available_prefix,
                        busy_prefix=busy_prefix,
                    )
                )
                # Only fall back to split variants when the full task cannot fit anywhere.
                if full_task_allowed_starts:
                    task_part_options = [
                        (
                            task.duration_minutes,
                            full_task_allowed_starts,
                            full_task_preferred_starts,
                        )
                    ]
                else:
                    task_part_options = [
                        (
                            part_duration,
                            *self._collect_allowed_starts(
                                request=request,
                                task=task,
                                duration_minutes=part_duration,
                                total_slots=total_slots,
                                fixed_start_slot=fixed_start_slot,
                                hard_latest_end=hard_latest_end,
                                available_prefix=available_prefix,
                                busy_prefix=busy_prefix,
                            ),
                        )
                        for part_duration in candidate_task_parts
                    ]
            else:
                task_part_options = [
                    (
                        task.duration_minutes,
                        *self._collect_allowed_starts(
                            request=request,
                            task=task,
                            duration_minutes=task.duration_minutes,
                            total_slots=total_slots,
                            fixed_start_slot=fixed_start_slot,
                            hard_latest_end=hard_latest_end,
                            available_prefix=available_prefix,
                            busy_prefix=busy_prefix,
                        ),
                    )
                ]
            task_has_unavailable_part = False
            split_part_count = len(task_part_options) if len(task_part_options) > 1 else None

            for part_index, (
                part_duration,
                allowed_starts,
                preferred_starts,
            ) in enumerate(task_part_options, start=1):
                duration_slots = part_duration // request.slot_minutes
                split_part_index = part_index if split_part_count is not None else None
                prepared_task = PreparedTask(
                    id=self._build_prepared_task_id(task.id, split_part_index),
                    task_id=task.id,
                    title=task.title,
                    source_task=task,
                    duration_slots=duration_slots,
                    duration_minutes=part_duration,
                    effective_load_minutes=self._get_effective_load_minutes(
                        part_duration,
                        task,
                        request.slot_minutes,
                        user_preferences,
                    ),
                    priority=task.priority,
                    is_mandatory=task.is_mandatory,
                    category=task.category,
                    energy_required=task.energy_required,
                    split_part_index=split_part_index,
                    split_part_count=split_part_count,
                    allowed_starts=allowed_starts,
                    preferred_starts=preferred_starts,
                )
                prepared_tasks.append(prepared_task)

                if not allowed_starts:
                    task_has_unavailable_part = True

            if not task_has_unavailable_part:
                continue

            if not task.is_mandatory:
                for prepared_task in prepared_tasks:
                    if prepared_task.task_id == task.id:
                        prepared_task.allowed_starts = []
                        prepared_task.preferred_starts = set()

            reason = self._detect_no_slot_reason(request, task.id)
            unscheduled.append(
                UnscheduledTask(
                    task_id=task.id,
                    title=task.title,
                    task=task,
                    reason=reason,
                )
            )

            if task.is_mandatory:
                violations.append(
                    Violation(
                        code=reason,
                        message=f"Mandatory task '{task.title}' cannot be scheduled.",
                    )
                )

        return prepared_tasks, unscheduled, violations

    def _collect_allowed_starts(
        self,
        *,
        request: PlanningRequest,
        task: TaskInput,
        duration_minutes: int,
        total_slots: int,
        fixed_start_slot: int | None,
        hard_latest_end: datetime | None,
        available_prefix: list[int] | None,
        busy_prefix: list[int] | None,
    ) -> tuple[list[int], set[int]]:
        duration_slots = duration_minutes // request.slot_minutes
        allowed_starts: list[int] = []
        preferred_starts: set[int] = set()

        latest_start_slot = total_slots - duration_slots
        if fixed_start_slot is not None:
            earliest_start_slot = fixed_start_slot
            latest_start_slot = fixed_start_slot
        else:
            earliest_start_slot = 0
            if task.earliest_start is not None:
                earliest_start_slot = max(
                    0,
                    datetime_to_slot(
                        task.earliest_start,
                        request.planning_start,
                        request.slot_minutes,
                    ),
                )
            if hard_latest_end is not None:
                latest_start_slot = min(
                    latest_start_slot,
                    datetime_to_slot_floor(
                        hard_latest_end,
                        request.planning_start,
                        request.slot_minutes,
                    ) - duration_slots,
                )

        if latest_start_slot < earliest_start_slot:
            latest_start_slot = earliest_start_slot - 1

        for start_slot in range(earliest_start_slot, latest_start_slot + 1):
            if (
                not task.is_fixed
                and available_prefix is not None
                and not self._interval_fully_covered(
                    available_prefix,
                    start_slot,
                    duration_slots,
                )
            ):
                continue

            if busy_prefix is not None and self._interval_has_overlap(
                busy_prefix,
                start_slot,
                duration_slots,
            ):
                continue

            start_dt = slot_to_datetime(
                start_slot,
                request.planning_start,
                request.slot_minutes,
            )
            if task.earliest_start and start_dt < task.earliest_start:
                continue

            end_dt = slot_to_datetime(
                start_slot + duration_slots,
                request.planning_start,
                request.slot_minutes,
            )
            if hard_latest_end and end_dt > hard_latest_end:
                continue

            if task.allowed_windows and not interval_inside_any_window(
                start_dt,
                end_dt,
                task.allowed_windows,
            ):
                continue

            allowed_starts.append(start_slot)

            if task.preferred_windows and interval_overlaps_any_window(
                start_dt,
                end_dt,
                task.preferred_windows,
            ):
                preferred_starts.add(start_slot)

        return allowed_starts, preferred_starts

    @staticmethod
    def _interval_fully_covered(
        prefix: list[int],
        start_slot: int,
        duration_slots: int,
    ) -> bool:
        end_slot = start_slot + duration_slots
        return prefix[end_slot] - prefix[start_slot] == duration_slots

    @staticmethod
    def _interval_has_overlap(
        prefix: list[int],
        start_slot: int,
        duration_slots: int,
    ) -> bool:
        end_slot = start_slot + duration_slots
        return prefix[end_slot] - prefix[start_slot] > 0

    def _build_task_parts(
        self,
        request: PlanningRequest,
        task: TaskInput,
        user_preferences: SolverUserPreferences | None,
    ) -> list[int]:
        if not task.allow_splitting or task.is_fixed:
            return [task.duration_minutes]

        min_part_minutes = task.min_split_part_minutes or task.duration_minutes
        if task.duration_minutes < min_part_minutes * 2:
            return [task.duration_minutes]

        if user_preferences is None:
            return self._build_default_task_parts(task.duration_minutes, min_part_minutes)

        preferred_focus = self._align_minutes_down(
            user_preferences.preferred_focus_block_minutes,
            request.slot_minutes,
        )
        max_focus = self._align_minutes_down(
            user_preferences.max_focus_block_minutes,
            request.slot_minutes,
        )
        target_part_minutes = max(min_part_minutes, preferred_focus)
        if max_focus > 0:
            target_part_minutes = min(target_part_minutes, max_focus)

        if (
            target_part_minutes <= 0
            or task.duration_minutes < target_part_minutes + min_part_minutes
        ):
            return [task.duration_minutes]

        parts: list[int] = []
        remaining_minutes = task.duration_minutes

        while (
            remaining_minutes > target_part_minutes
            and remaining_minutes - target_part_minutes >= min_part_minutes
        ):
            parts.append(target_part_minutes)
            remaining_minutes -= target_part_minutes

        parts.append(remaining_minutes)
        return parts

    def _build_default_task_parts(
        self,
        duration_minutes: int,
        min_part_minutes: int,
    ) -> list[int]:
        parts: list[int] = []
        remaining_minutes = duration_minutes

        while remaining_minutes >= min_part_minutes * 2:
            parts.append(min_part_minutes)
            remaining_minutes -= min_part_minutes

        parts.append(remaining_minutes)
        return parts

    def _build_prepared_task_id(
        self,
        task_id: str,
        split_part_index: int | None,
    ) -> str:
        if split_part_index is None:
            return task_id

        return f"{task_id}__part_{split_part_index}"

    def _calculate_start_score(
        self,
        request: PlanningRequest,
        task: PreparedTask,
        start_slot: int,
        user_preferences: SolverUserPreferences | None,
    ) -> int:
        priority_weight = task.priority * 1000
        if task.is_mandatory:
            priority_weight += 500

        score = priority_weight

        if start_slot in task.preferred_starts:
            score += 150

        if user_preferences is not None:
            start_dt = slot_to_datetime(
                start_slot,
                request.planning_start,
                request.slot_minutes,
            )
            time_block = self._get_time_block(start_dt)
            block_weight = self._get_time_block_weight(
                task=task,
                time_block=time_block,
                user_preferences=user_preferences,
            )
            score += block_weight * self._get_energy_weight(task.energy_required)

            score += int(task.priority * 80 * user_preferences.completion_rate)
            score -= int(task.duration_minutes * user_preferences.reschedule_rate)
            score -= (task.effective_load_minutes - task.duration_minutes) * 2

            if task.duration_minutes > user_preferences.preferred_focus_block_minutes:
                extra_minutes = (
                    task.duration_minutes
                    - user_preferences.preferred_focus_block_minutes
                )
                score -= extra_minutes // 4

            if task.duration_minutes > user_preferences.max_focus_block_minutes:
                extra_minutes = (
                    task.duration_minutes
                    - user_preferences.max_focus_block_minutes
                )
                score -= extra_minutes

            if user_preferences.likes_compact_schedule:
                score -= start_slot // 3
            else:
                score -= start_slot // 10
        else:
            score -= start_slot

        return score

    def _get_time_block_weight(
        self,
        task: PreparedTask,
        time_block: str,
        user_preferences: SolverUserPreferences,
    ) -> int:
        category_weights = user_preferences.time_block_weights.get(
            task.category or "",
            {},
        )
        if time_block in category_weights:
            return category_weights[time_block]

        return user_preferences.global_time_block_weights.get(time_block, 0)

    def _get_energy_weight(self, energy_required: str | None) -> int:
        if energy_required == "high":
            return 3

        if energy_required == "medium":
            return 2

        return 1

    def _get_duration_multiplier(
        self,
        task: TaskInput,
        user_preferences: SolverUserPreferences | None,
    ) -> float:
        if user_preferences is None:
            return 1.0

        if task.category and task.category in user_preferences.duration_multipliers:
            return user_preferences.duration_multipliers[task.category]

        return user_preferences.duration_multipliers.get("global", 1.0)

    def _get_effective_load_minutes(
        self,
        duration_minutes: int,
        task: TaskInput,
        slot_minutes: int,
        user_preferences: SolverUserPreferences | None,
    ) -> int:
        multiplier = self._get_duration_multiplier(task, user_preferences)
        effective_minutes = ceil(duration_minutes * multiplier)
        return self._align_minutes_up(effective_minutes, slot_minutes)

    def _align_minutes_down(self, minutes: int, slot_minutes: int) -> int:
        return (minutes // slot_minutes) * slot_minutes

    def _align_minutes_up(self, minutes: int, slot_minutes: int) -> int:
        return ceil(minutes / slot_minutes) * slot_minutes

    def _detect_no_slot_reason(self, request: PlanningRequest, task_id: str) -> str:
        task = next(task for task in request.tasks if task.id == task_id)
        hard_latest_end = task.latest_end or task.deadline

        if hard_latest_end and hard_latest_end <= request.planning_start:
            return "DEADLINE_BEFORE_PLANNING_START"

        if task.duration_minutes > int(
            (request.planning_end - request.planning_start).total_seconds() // 60
        ):
            return "TASK_DURATION_TOO_LARGE"

        if task.is_fixed:
            return "FIXED_TASK_OVERLAP"

        return "NO_AVAILABLE_SLOT"

    def _all_tasks_unscheduled(
        self,
        request: PlanningRequest,
        reason: str,
    ) -> list[UnscheduledTask]:
        return [
            UnscheduledTask(
                task_id=task.id,
                title=task.title,
                task=task,
                reason=reason,
            )
            for task in request.tasks
        ]

    def _build_single_variant_result(
        self,
        request: PlanningRequest,
        scheduled_tasks: list[ScheduledTask],
        unscheduled_tasks: list[UnscheduledTask],
        violations: list[Violation],
        solver_status: str,
        strategy: str,
    ) -> PlanningResult:
        variant = ScheduleVariant(
            variant_id=1,
            scheduled_tasks=scheduled_tasks,
            unscheduled_tasks=unscheduled_tasks,
            metadata={
                "solver_status": solver_status,
                "strategy": strategy,
                "total_scheduled_minutes": sum(
                    task.duration_minutes
                    for task in scheduled_tasks
                ),
                "total_unscheduled_minutes": self._get_total_unscheduled_minutes(
                    request,
                    unscheduled_tasks,
                ),
            },
        )
        return PlanningResult(
            status=self._get_result_status(variant),
            scheduled_tasks=scheduled_tasks,
            unscheduled_tasks=unscheduled_tasks,
            schedule_variants=[variant],
            violations=violations,
            metadata={
                **variant.metadata,
                "variant_count": 1,
            },
        )
