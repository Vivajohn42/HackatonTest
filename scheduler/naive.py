from __future__ import annotations

from simulator.models import MachineState, Plant, ProductionOrder
from scheduler.base import BaseScheduler


class NaiveScheduler(BaseScheduler):
    @property
    def name(self) -> str:
        return "FIFO (Naive)"

    def schedule(
        self,
        pending_orders: list[ProductionOrder],
        plant: Plant,
        current_time: float,
    ) -> list[dict]:
        assignments: list[dict] = []
        idle_machines = [
            m for m in plant.machines
            if m.state == MachineState.IDLE and m.current_order is None
        ]
        for machine in idle_machines:
            if not pending_orders:
                break
            order = pending_orders[0]
            assignments.append({"order": order, "machine": machine})
        return assignments
