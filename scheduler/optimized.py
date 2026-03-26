from __future__ import annotations

from collections import defaultdict

from simulator.models import (
    A650Machine,
    CassetteState,
    CassetteType,
    MachineState,
    Plant,
    ProductionOrder,
)
from scheduler.base import BaseScheduler


class OptimizedScheduler(BaseScheduler):
    @property
    def name(self) -> str:
        return "Kassetten-Clustering (Optimiert)"

    def schedule(
        self,
        pending_orders: list[ProductionOrder],
        plant: Plant,
        current_time: float,
    ) -> list[dict]:
        if not pending_orders:
            return []

        assignments: list[dict] = []
        idle_machines = [
            m for m in plant.machines
            if m.state == MachineState.IDLE and m.current_order is None
        ]

        self._prefetch_setups(pending_orders, plant, current_time)

        for machine in idle_machines:
            if not pending_orders:
                break
            best_order = self._find_best_order(machine, pending_orders, plant, current_time)
            if best_order:
                assignments.append({"order": best_order, "machine": machine})

        return assignments

    def _find_best_order(
        self,
        machine: A650Machine,
        pending_orders: list[ProductionOrder],
        plant: Plant,
        current_time: float,
    ) -> ProductionOrder | None:
        best_score = float("-inf")
        best_order = None
        for order in pending_orders:
            score = self._score_order(machine, order, plant, current_time)
            if score > best_score:
                best_score = score
                best_order = order
        return best_order

    def _score_order(
        self,
        machine: A650Machine,
        order: ProductionOrder,
        plant: Plant,
        current_time: float,
    ) -> float:
        score = 0.0

        need_left, need_right = machine.needs_changeover(order)
        changeovers = int(need_left) + int(need_right)
        score -= changeovers * 10.0

        if need_left:
            ready_left = plant.get_ready_cassettes(order.cassette_type_left)
            if ready_left:
                score += 5.0
            else:
                available_left = plant.get_available_cassettes(order.cassette_type_left)
                if not available_left:
                    score -= 50.0

        if need_right:
            ready_right = plant.get_ready_cassettes(order.cassette_type_right)
            if ready_right:
                score += 5.0
            else:
                available_right = plant.get_available_cassettes(order.cassette_type_right)
                if not available_right:
                    score -= 50.0

        score += order.priority.value * 3.0

        if order.due_time is not None:
            remaining = order.due_time - current_time
            if remaining < order.processing_time_min * 2:
                score += 15.0
            elif remaining < order.processing_time_min * 5:
                score += 5.0

        return score

    def _prefetch_setups(
        self,
        pending_orders: list[ProductionOrder],
        plant: Plant,
        current_time: float,
    ) -> None:
        sm = plant.setup_machine
        if sm.is_busy(current_time) and len(sm.queue) >= 2:
            return

        needed_types: dict[CassetteType, int] = defaultdict(int)
        for order in pending_orders[:20]:
            needed_types[order.cassette_type_left] += 1
            needed_types[order.cassette_type_right] += 1

        sorted_types = sorted(needed_types.items(), key=lambda x: -x[1])

        for ctype, _count in sorted_types:
            ready = [
                c for c in plant.cassette_pool
                if c.cassette_type == ctype
                and c.state in (CassetteState.READY, CassetteState.IN_SETUP)
            ]
            if ready:
                continue

            available = plant.get_available_cassettes(ctype)
            if available:
                cassette = available[0]
                if not sm.is_busy(current_time):
                    sm.start_setup(cassette, current_time)
                elif cassette not in sm.queue:
                    sm.queue.append(cassette)
