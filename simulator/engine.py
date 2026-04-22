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
    total_time_sec: float = 0.0
    orders_completed: int = 0
    orders_total: int = 0
    total_changeovers: int = 0
    total_setups: int = 0
    total_idle_sec: float = 0.0
    total_production_sec: float = 0.0
    total_changeover_sec: float = 0.0
    total_setup_sec: float = 0.0
    orders_on_time: int = 0
    orders_late: int = 0
    total_leadsets_produced: int = 0
    total_wait_ticks: int = 0
    machine_utilization: dict[str, float] = field(default_factory=dict)
    cassettes_depleted: int = 0

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "SIMULATIONSERGEBNIS",
            "=" * 60,
            f"Gesamtzeit:          {self.total_time_sec:.0f} sec ({self.total_time_sec / 3600:.1f} h)",
            f"Auftraege:           {self.orders_completed}/{self.orders_total} abgeschlossen",
            f"Leadsets produziert: {self.total_leadsets_produced}",
            f"Puenktlich:          {self.orders_on_time} | Verspaetet: {self.orders_late}",
            f"Kassettenwechsel:    {self.total_changeovers} (total {self.total_changeover_sec:.0f} sec)",
            f"Kassetten-Setups:    {self.total_setups} (total {self.total_setup_sec:.0f} sec)",
            f"Rollen aufgebraucht: {self.cassettes_depleted}",
            f"Warteticks:          {self.total_wait_ticks}",
            f"Produktionszeit:     {self.total_production_sec:.0f} sec",
            f"Leerlaufzeit:        {self.total_idle_sec:.0f} sec",
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
        self.total_setup_sec: float = 0.0
        self.cassettes_depleted: int = 0

    def run(self, max_time_sec: float = 36000.0) -> SimulationResult:
        self._schedule_tick()

        while self.events and self.current_time <= max_time_sec:
            event = heapq.heappop(self.events)
            self.current_time = event.time

            if self.current_time > max_time_sec:
                break

            if event.event_type == EventType.SETUP_COMPLETE:
                self._handle_setup_complete(event)
            elif event.event_type == EventType.CHANGEOVER_COMPLETE:
                self._handle_changeover_complete(event)
            elif event.event_type == EventType.PRODUCTION_COMPLETE:
                self._handle_production_complete(event)
            elif event.event_type == EventType.SCHEDULE_TICK:
                self._schedule_tick()

        return self._build_result(max_time_sec)

    def _add_event(self, event: Event) -> None:
        heapq.heappush(self.events, event)

    def _schedule_tick(self) -> None:
        assignments = self.scheduler.schedule(
            pending_orders=self.pending_orders,
            plant=self.plant,
            current_time=self.current_time,
        )

        for assignment in assignments:
            self._start_order_on_machine(assignment["order"], assignment["machine"])

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
                self.total_setup_sec += sm.setup_duration_min * 60

    def _start_order_on_machine(self, order, machine):
        if order in self.pending_orders:
            self.pending_orders.remove(order)

        order.assigned_machine = machine.id
        need_s1, need_s2 = machine.needs_changeover(order)

        sides_to_check = []
        if need_s1:
            sides_to_check.append((1, order.cassette_type_s1))
        if need_s2:
            sides_to_check.append((2, order.cassette_type_s2))

        all_ready = True
        for side, ctype in sides_to_check:
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
                    self._request_setup(available[0])
                    all_ready = False
                else:
                    self.pending_orders.append(order)
                    order.assigned_machine = None
                    machine.wait_ticks += 1
                    return

        if not all_ready:
            self.pending_orders.append(order)
            order.assigned_machine = None
            return

        changeover_time_sec = 0.0
        for side, ctype in sides_to_check:
            ready = self.plant.get_ready_cassettes(ctype)
            if ready:
                new_cassette = ready[0]
                slot = machine.get_empty_slot(side)
                if slot is None:
                    slot = machine.get_depleted_slot(side)
                if slot is None:
                    slots = machine.side1_slots if side == 1 else machine.side2_slots
                    slot = slots[0]

                if slot.cassette is not None:
                    old = slot.cassette
                    if old.is_depleted:
                        old.state = CassetteState.AVAILABLE
                        self.cassettes_depleted += 1
                    else:
                        old.state = CassetteState.READY
                    old.assigned_machine = None
                    old.assigned_slot = None

                new_cassette.state = CassetteState.IN_USE
                new_cassette.assigned_machine = machine.id
                new_cassette.assigned_slot = slot.slot_id
                slot.cassette = new_cassette
                changeover_time_sec += machine.changeover_duration_min * 60
                machine.total_changeovers += 1

        machine.current_order = order
        machine.state = MachineState.CHANGEOVER if changeover_time_sec > 0 else MachineState.PRODUCING
        machine.total_changeover_min += changeover_time_sec / 60
        order.start_time = self.current_time

        if changeover_time_sec > 0:
            self._add_event(Event(
                time=self.current_time + changeover_time_sec,
                event_type=EventType.CHANGEOVER_COMPLETE,
                machine_id=machine.id,
                order_id=order.id,
            ))
        else:
            self._start_production(machine, order)

    def _start_production(self, machine, order):
        production_end = self.current_time + order.processing_time_sec
        machine.state = MachineState.PRODUCING
        machine.busy_until = production_end

        c_s1 = machine.get_cassette_for_type(1, order.cassette_type_s1)
        c_s2 = machine.get_cassette_for_type(2, order.cassette_type_s2)
        if c_s1:
            c_s1.consume_terminals(order.leadsets)
        if c_s2:
            c_s2.consume_terminals(order.leadsets)

        self._add_event(Event(
            time=production_end,
            event_type=EventType.PRODUCTION_COMPLETE,
            machine_id=machine.id,
            order_id=order.id,
        ))

    def _request_setup(self, cassette):
        sm = self.plant.setup_machine
        if sm.is_busy(self.current_time):
            if cassette not in sm.queue:
                sm.queue.append(cassette)
        else:
            finish_time = sm.start_setup(cassette, self.current_time)
            self.total_setups += 1
            self.total_setup_sec += sm.setup_duration_min * 60
            self._add_event(Event(
                time=finish_time,
                event_type=EventType.SETUP_COMPLETE,
                cassette_id=cassette.id,
            ))

    def _handle_setup_complete(self, event):
        sm = self.plant.setup_machine
        sm.complete_setup()

        if sm.queue:
            next_cassette = sm.queue.pop(0)
            finish_time = sm.start_setup(next_cassette, self.current_time)
            self.total_setups += 1
            self.total_setup_sec += sm.setup_duration_min * 60
            self._add_event(Event(
                time=finish_time,
                event_type=EventType.SETUP_COMPLETE,
                cassette_id=next_cassette.id,
            ))

        self._add_event(Event(
            time=self.current_time,
            event_type=EventType.SCHEDULE_TICK,
        ))

    def _handle_changeover_complete(self, event):
        machine = self._get_machine(event.machine_id)
        if machine and machine.current_order:
            self._start_production(machine, machine.current_order)

    def _handle_production_complete(self, event):
        machine = self._get_machine(event.machine_id)
        if machine and machine.current_order:
            order = machine.current_order
            order.produced = order.leadsets
            order.end_time = self.current_time
            machine.total_produced += order.leadsets
            machine.total_production_min += order.processing_time_sec / 60
            machine.state = MachineState.IDLE
            machine.current_order = None
            if order not in self.completed_orders:
                self.completed_orders.append(order)

            for slot in machine.all_slots():
                if slot.is_depleted and slot.cassette is not None:
                    cassette = slot.cassette
                    cassette.state = CassetteState.AVAILABLE
                    cassette.assigned_machine = None
                    cassette.assigned_slot = None
                    slot.cassette = None
                    self.cassettes_depleted += 1
                    self._request_setup(cassette)

        self._add_event(Event(
            time=self.current_time,
            event_type=EventType.SCHEDULE_TICK,
        ))

    def _get_machine(self, machine_id):
        if machine_id is None:
            return None
        for m in self.plant.machines:
            if m.id == machine_id:
                return m
        return None

    def _build_result(self, max_time_sec):
        result = SimulationResult()
        result.total_time_sec = min(self.current_time, max_time_sec)
        result.orders_completed = len(self.completed_orders)
        result.orders_total = len(self.plant.orders)
        result.total_setups = self.total_setups
        result.total_setup_sec = self.total_setup_sec
        result.cassettes_depleted = self.cassettes_depleted

        for order in self.completed_orders:
            result.total_leadsets_produced += order.leadsets
            if order.due_time and order.end_time:
                if order.end_time <= order.due_time:
                    result.orders_on_time += 1
                else:
                    result.orders_late += 1

        for machine in self.plant.machines:
            result.total_changeovers += machine.total_changeovers
            result.total_changeover_sec += machine.total_changeover_min * 60
            result.total_production_sec += machine.total_production_min * 60
            result.total_wait_ticks += machine.wait_ticks

            if result.total_time_sec > 0:
                utilization = (machine.total_production_min * 60) / result.total_time_sec
                result.machine_utilization[machine.id] = utilization
                result.total_idle_sec += (
                    result.total_time_sec
                    - machine.total_production_min * 60
                    - machine.total_changeover_min * 60
                )

        return result
