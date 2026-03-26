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

    def _find_best_order(self, machine, pending_orders, plant, current_time):
        best_score = float("-inf")
        best_order = None
        for order in pending_orders:
            score = self._score_order(machine, order, plant, current_time)
            if score > best_score:
                best_score = score
                best_order = order
        return best_order

    def _score_order(self, machine, order, plant, current_time):
        score = 0.0
        need_s1, need_s2 = machine.needs_changeover(order)
        changeovers = int(need_s1) + int(need_s2)
        score -= changeovers * 20.0

        if not need_s1 and not need_s2:
            score += 30.0

        enough_s1, enough_s2 = machine.has_enough_terminals(order)
        if not need_s1 and enough_s1:
            score += 10.0
        if not need_s2 and enough_s2:
            score += 10.0

        if need_s1:
            ready = plant.get_ready_cassettes(order.cassette_type_s1)
            if ready:
                score += 8.0
            else:
                available = plant.get_available_cassettes(order.cassette_type_s1)
                if not available:
                    score -= 50.0

        if need_s2:
            ready = plant.get_ready_cassettes(order.cassette_type_s2)
            if ready:
                score += 8.0
            else:
                available = plant.get_available_cassettes(order.cassette_type_s2)
                if not available:
                    score -= 50.0

        score += order.priority.value * 3.0

        if order.due_time is not None:
            remaining = order.due_time - current_time
            if remaining < order.processing_time_sec * 1.5:
                score += 20.0
            elif remaining < order.processing_time_sec * 3:
                score += 8.0

        return score

    def _prefetch_setups(self, pending_orders, plant, current_time):
        sm = plant.setup_machine
        if sm.is_busy(current_time) and len(sm.queue) >= 2:
            return

        needed_types: dict[CassetteType, int] = defaultdict(int)
        for order in pending_orders[:20]:
            needed_types[order.cassette_type_s1] += 1
            needed_types[order.cassette_type_s2] += 1

        sorted_types = sorted(needed_types.items(), key=lambda x: -x[1])

        for ctype, _count in sorted_types:
            ready_or_setup = [
                c for c in plant.cassette_pool
                if c.cassette_type == ctype
                and c.state in (CassetteState.READY, CassetteState.IN_SETUP, CassetteState.IN_USE)
                and not c.is_depleted
            ]
            if ready_or_setup:
                continue

            available = plant.get_available_cassettes(ctype)
            if available:
                cassette = available[0]
                if not sm.is_busy(current_time):
                    sm.start_setup(cassette, current_time)
                elif cassette not in sm.queue:
                    sm.queue.append(cassette)
