from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from simulator.models import (
    A650Machine,
    Cassette,
    CassetteState,
    CassetteType,
    MachineState,
    Plant,
    ProductionOrder,
)


class EventType(Enum):
    SETUP_COMPLETE = auto()
    CHANGEOVER_COMPLETE = auto()
    PRODUCTION_COMPLETE = auto()
    SCHEDULE_TICK = auto()


@dataclass(order=True)
class Event:
    time: float
    event_type: EventType = field(compare=False)
    machine_id: Optional[str] = field(default=None, compare=False)
    cassette_id: Optional[str] = field(default=None, compare=False)
    order_id: Optional[str] = field(default=None, compare=False)


@dataclass
class SimulationResult:
    total_time_min: float = 0.0
    orders_completed: int = 0
    orders_total: int = 0
    total_changeovers: int = 0
    total_setups: int = 0
    total_idle_min: float = 0.0
    total_production_min: float = 0.0
    total_changeover_min: float = 0.0
    total_setup_min: float = 0.0
    orders_on_time: int = 0
    orders_late: int = 0
    machine_utilization: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "SIMULATIONSERGEBNIS",
            "=" * 60,
            f"Gesamtzeit:          {self.total_time_min:.1f} min ({self.total_time_min / 60:.1f} h)",
            f"Auftraege:           {self.orders_completed}/{self.orders_total} abgeschlossen",
            f"Puenktlich:          {self.orders_on_time} | Verspaetet: {self.orders_late}",
            f"Kassettenwechsel:    {self.total_changeovers} (total {self.total_changeover_min:.1f} min)",
            f"Kassetten-Setups:    {self.total_setups} (total {self.total_setup_min:.1f} min)",
            f"Produktionszeit:     {self.total_production_min:.1f} min",
            f"Leerlaufzeit:        {self.total_idle_min:.1f} min",
            "-" * 60,
            "Maschinenauslastung:",
        ]
        for machine_id, util in sorted(self.machine_utilization.items()):
            lines.append(f"  {machine_id}: {util:.1%}")
        lines.append("=" * 60)
        return "\n".join(lines)


class SimulationEngine:
    def __init__(self, plant: Plant, scheduler):
        self.plant = plant
        self.scheduler = scheduler
        self.current_time: float = 0.0
        self.events: list[Event] = []
        self.completed_orders: list[ProductionOrder] = []
        self.pending_orders: list[ProductionOrder] = list(plant.orders)
        self.total_setups: int = 0
        self.total_setup_min: float = 0.0

    def run(self, max_time_min: float = 480.0) -> SimulationResult:
        self._schedule_tick()

        while self.events and self.current_time <= max_time_min:
            event = heapq.heappop(self.events)
            self.current_time = event.time

            if self.current_time > max_time_min:
                break

            if event.event_type == EventType.SETUP_COMPLETE:
                self._handle_setup_complete(event)
            elif event.event_type == EventType.CHANGEOVER_COMPLETE:
                self._handle_changeover_complete(event)
            elif event.event_type == EventType.PRODUCTION_COMPLETE:
                self._handle_production_complete(event)
            elif event.event_type == EventType.SCHEDULE_TICK:
                self._schedule_tick()

        return self._build_result(max_time_min)

    def _add_event(self, event: Event) -> None:
        heapq.heappush(self.events, event)

    def _schedule_tick(self) -> None:
        assignments = self.scheduler.schedule(
            pending_orders=self.pending_orders,
            plant=self.plant,
            current_time=self.current_time,
        )

        for assignment in assignments:
            order = assignment["order"]
            machine = assignment["machine"]
            self._start_order_on_machine(order, machine)

        sm = self.plant.setup_machine
        if sm.is_busy(self.current_time):
            has_event = any(
                e.event_type == EventType.SETUP_COMPLETE and e.time == sm.busy_until
                for e in self.events
            )
            if not has_event and sm.current_cassette:
                self._add_event(Event(
                    time=sm.busy_until,
                    event_type=EventType.SETUP_COMPLETE,
                    cassette_id=sm.current_cassette.id,
                ))
                self.total_setups += 1
                self.total_setup_min += sm.setup_duration_min

    def _start_order_on_machine(self, order: ProductionOrder, machine: A650Machine) -> None:
        if order in self.pending_orders:
            self.pending_orders.remove(order)

        order.assigned_machine = machine.id
        need_left, need_right = machine.needs_changeover(order)

        cassettes_needed: list[tuple[CassetteType, str]] = []
        if need_left:
            cassettes_needed.append((order.cassette_type_left, "left"))
        if need_right:
            cassettes_needed.append((order.cassette_type_right, "right"))

        all_ready = True
        for ctype, side in cassettes_needed:
            ready = self.plant.get_ready_cassettes(ctype)
            if not ready:
                in_setup = [
                    c for c in self.plant.cassette_pool
                    if c.cassette_type == ctype and c.state == CassetteState.IN_SETUP
                ]
                if in_setup:
                    all_ready = False
                    continue

                available = self.plant.get_available_cassettes(ctype)
                if available:
                    cassette = available[0]
                    self._request_setup(cassette)
                    all_ready = False
                else:
                    self.pending_orders.append(order)
                    order.assigned_machine = None
                    return

        if not all_ready:
            self.pending_orders.append(order)
            order.assigned_machine = None
            return

        changeover_time = 0.0
        if need_left:
            ready = self.plant.get_ready_cassettes(order.cassette_type_left)
            if ready:
                if machine.cassette_left:
                    machine.cassette_left.state = CassetteState.AVAILABLE
                    machine.cassette_left.assigned_machine = None
                cassette = ready[0]
                cassette.state = CassetteState.IN_USE
                cassette.assigned_machine = machine.id
                machine.cassette_left = cassette
                changeover_time += machine.changeover_duration_min
                machine.total_changeovers += 1

        if need_right:
            ready = self.plant.get_ready_cassettes(order.cassette_type_right)
            if ready:
                if machine.cassette_right:
                    machine.cassette_right.state = CassetteState.AVAILABLE
                    machine.cassette_right.assigned_machine = None
                cassette = ready[0]
                cassette.state = CassetteState.IN_USE
                cassette.assigned_machine = machine.id
                machine.cassette_right = cassette
                changeover_time += machine.changeover_duration_min
                machine.total_changeovers += 1

        machine.current_order = order
        machine.state = MachineState.CHANGEOVER if changeover_time > 0 else MachineState.PRODUCING
        machine.total_changeover_min += changeover_time

        order.start_time = self.current_time + changeover_time

        if changeover_time > 0:
            self._add_event(Event(
                time=self.current_time + changeover_time,
                event_type=EventType.CHANGEOVER_COMPLETE,
                machine_id=machine.id,
                order_id=order.id,
            ))
        else:
            production_end = self.current_time + order.processing_time_min
            machine.state = MachineState.PRODUCING
            machine.busy_until = production_end
            self._add_event(Event(
                time=production_end,
                event_type=EventType.PRODUCTION_COMPLETE,
                machine_id=machine.id,
                order_id=order.id,
            ))

    def _request_setup(self, cassette: Cassette) -> None:
        sm = self.plant.setup_machine
        if sm.is_busy(self.current_time):
            if cassette not in sm.queue:
                sm.queue.append(cassette)
        else:
            finish_time = sm.start_setup(cassette, self.current_time)
            self.total_setups += 1
            self.total_setup_min += sm.setup_duration_min
            self._add_event(Event(
                time=finish_time,
                event_type=EventType.SETUP_COMPLETE,
                cassette_id=cassette.id,
            ))

    def _handle_setup_complete(self, event: Event) -> None:
        sm = self.plant.setup_machine
        completed = sm.complete_setup()

        if sm.queue:
            next_cassette = sm.queue.pop(0)
            finish_time = sm.start_setup(next_cassette, self.current_time)
            self.total_setups += 1
            self.total_setup_min += sm.setup_duration_min
            self._add_event(Event(
                time=finish_time,
                event_type=EventType.SETUP_COMPLETE,
                cassette_id=next_cassette.id,
            ))

        self._add_event(Event(
            time=self.current_time,
            event_type=EventType.SCHEDULE_TICK,
        ))

    def _handle_changeover_complete(self, event: Event) -> None:
        machine = self._get_machine(event.machine_id)
        if machine and machine.current_order:
            order = machine.current_order
            production_end = self.current_time + order.processing_time_min
            machine.state = MachineState.PRODUCING
            machine.busy_until = production_end
            self._add_event(Event(
                time=production_end,
                event_type=EventType.PRODUCTION_COMPLETE,
                machine_id=machine.id,
                order_id=order.id,
            ))

    def _handle_production_complete(self, event: Event) -> None:
        machine = self._get_machine(event.machine_id)
        if machine and machine.current_order:
            order = machine.current_order
            order.end_time = self.current_time
            machine.total_produced += order.quantity
            machine.total_production_min += order.processing_time_min
            machine.state = MachineState.IDLE
            machine.current_order = None
            self.completed_orders.append(order)

        self._add_event(Event(
            time=self.current_time,
            event_type=EventType.SCHEDULE_TICK,
        ))

    def _get_machine(self, machine_id: Optional[str]) -> Optional[A650Machine]:
        if machine_id is None:
            return None
        for m in self.plant.machines:
            if m.id == machine_id:
                return m
        return None

    def _build_result(self, max_time_min: float) -> SimulationResult:
        result = SimulationResult()
        result.total_time_min = min(self.current_time, max_time_min)
        result.orders_completed = len(self.completed_orders)
        result.orders_total = len(self.plant.orders)
        result.total_setups = self.total_setups
        result.total_setup_min = self.total_setup_min

        for order in self.completed_orders:
            if order.due_time and order.end_time:
                if order.end_time <= order.due_time:
                    result.orders_on_time += 1
                else:
                    result.orders_late += 1

        for machine in self.plant.machines:
            result.total_changeovers += machine.total_changeovers
            result.total_changeover_min += machine.total_changeover_min
            result.total_production_min += machine.total_production_min

            if result.total_time_min > 0:
                utilization = machine.total_production_min / result.total_time_min
                result.machine_utilization[machine.id] = utilization
                result.total_idle_min += result.total_time_min - machine.total_production_min - machine.total_changeover_min

        return result
