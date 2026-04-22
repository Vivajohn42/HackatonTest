"""Datenmodell fuer das Kassetten-Planungs-System."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


@dataclass
class CassetteType:
    id: str
    terminal_type: str
    seal_type: Optional[str] = None
    roll_capacity: int = 8000
    description: str = ""

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CassetteType):
            return NotImplemented
        return self.id == other.id


class CassetteState(Enum):
    AVAILABLE = auto()
    IN_SETUP = auto()
    READY = auto()
    IN_USE = auto()
    DEPLETED = auto()


@dataclass
class Cassette:
    id: str
    cassette_type: CassetteType
    state: CassetteState = CassetteState.AVAILABLE
    roll_remaining: int = 0
    assigned_machine: Optional[str] = None
    assigned_slot: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.id)

    def __post_init__(self):
        if self.roll_remaining == 0 and self.state != CassetteState.AVAILABLE:
            self.roll_remaining = self.cassette_type.roll_capacity

    def consume_terminals(self, count: int) -> int:
        actual = min(count, self.roll_remaining)
        self.roll_remaining -= actual
        if self.roll_remaining <= 0:
            self.state = CassetteState.DEPLETED
        return actual

    @property
    def is_depleted(self) -> bool:
        return self.roll_remaining <= 0

    @property
    def fill_percentage(self) -> float:
        if self.cassette_type.roll_capacity == 0:
            return 0.0
        return self.roll_remaining / self.cassette_type.roll_capacity


@dataclass
class SetupMachine:
    id: str = "ASSEMBLY-1"
    setup_duration_min: float = 12.0
    current_cassette: Optional[Cassette] = None
    busy_until: float = 0.0
    queue: list[Cassette] = field(default_factory=list)

    def is_busy(self, current_time: float) -> bool:
        return current_time < self.busy_until

    def start_setup(self, cassette: Cassette, current_time: float) -> float:
        cassette.state = CassetteState.IN_SETUP
        self.current_cassette = cassette
        self.busy_until = current_time + self.setup_duration_min * 60
        return self.busy_until

    def complete_setup(self) -> Optional[Cassette]:
        if self.current_cassette is None:
            return None
        cassette = self.current_cassette
        cassette.state = CassetteState.READY
        cassette.roll_remaining = cassette.cassette_type.roll_capacity
        cassette.assigned_machine = None
        cassette.assigned_slot = None
        self.current_cassette = None
        return cassette


class MachineState(Enum):
    IDLE = auto()
    PRODUCING = auto()
    CHANGEOVER = auto()
    LOADING = auto()
    VERIFYING = auto()


@dataclass
class MachineSlot:
    side: int
    slot_index: int
    cassette: Optional[Cassette] = None

    @property
    def slot_id(self) -> str:
        return f"S{self.side}-{self.slot_index}"

    @property
    def is_empty(self) -> bool:
        return self.cassette is None

    @property
    def is_depleted(self) -> bool:
        return self.cassette is not None and self.cassette.is_depleted


@dataclass
class A650Machine:
    id: str
    state: MachineState = MachineState.IDLE
    current_order: Optional[ProductionOrder] = None
    busy_until: float = 0.0
    changeover_duration_min: float = 1.0

    side1_slots: list[MachineSlot] = field(default_factory=list)
    side2_slots: list[MachineSlot] = field(default_factory=list)

    total_produced: int = 0
    total_changeovers: int = 0
    total_idle_min: float = 0.0
    total_production_min: float = 0.0
    total_changeover_min: float = 0.0
    wait_ticks: int = 0

    def __post_init__(self):
        if not self.side1_slots:
            self.side1_slots = [MachineSlot(side=1, slot_index=i) for i in range(2)]
        if not self.side2_slots:
            self.side2_slots = [MachineSlot(side=2, slot_index=i) for i in range(2)]

    def get_cassette_for_type(self, side: int, ctype: CassetteType) -> Optional[Cassette]:
        slots = self.side1_slots if side == 1 else self.side2_slots
        for slot in slots:
            if (slot.cassette is not None
                    and slot.cassette.cassette_type == ctype
                    and not slot.cassette.is_depleted):
                return slot.cassette
        return None

    def get_empty_slot(self, side: int) -> Optional[MachineSlot]:
        slots = self.side1_slots if side == 1 else self.side2_slots
        for slot in slots:
            if slot.is_empty:
                return slot
        return None

    def get_depleted_slot(self, side: int) -> Optional[MachineSlot]:
        slots = self.side1_slots if side == 1 else self.side2_slots
        for slot in slots:
            if slot.is_depleted:
                return slot
        return None

    def needs_changeover(self, order: ProductionOrder) -> tuple[bool, bool]:
        need_s1 = self.get_cassette_for_type(1, order.cassette_type_s1) is None
        need_s2 = self.get_cassette_for_type(2, order.cassette_type_s2) is None
        return need_s1, need_s2

    def has_enough_terminals(self, order: ProductionOrder) -> tuple[bool, bool]:
        c_s1 = self.get_cassette_for_type(1, order.cassette_type_s1)
        c_s2 = self.get_cassette_for_type(2, order.cassette_type_s2)
        enough_s1 = c_s1 is not None and c_s1.roll_remaining >= order.leadsets
        enough_s2 = c_s2 is not None and c_s2.roll_remaining >= order.leadsets
        return enough_s1, enough_s2

    def all_slots(self) -> list[MachineSlot]:
        return self.side1_slots + self.side2_slots

    def installed_cassette_types(self, side: int) -> list[CassetteType]:
        slots = self.side1_slots if side == 1 else self.side2_slots
        return [
            slot.cassette.cassette_type
            for slot in slots
            if slot.cassette is not None and not slot.cassette.is_depleted
        ]


class OrderPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ProductionOrder:
    id: str
    article: str
    leadsets: int
    cassette_type_s1: CassetteType
    cassette_type_s2: CassetteType
    wire_type: str = ""
    wire_cross_section_mm2: float = 0.5
    wire_length_mm: float = 500.0
    priority: OrderPriority = OrderPriority.NORMAL
    due_time: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    assigned_machine: Optional[str] = None
    produced: int = 0

    @property
    def processing_time_sec(self) -> float:
        # ~3-5 sec pro Leadset (CC-Maschine Durchschnitt)
        return self.leadsets * 4.0

    @property
    def is_completed(self) -> bool:
        return self.produced >= self.leadsets

    @property
    def progress(self) -> float:
        if self.leadsets == 0:
            return 1.0
        return self.produced / self.leadsets


@dataclass
class Plant:
    name: str = "Beispielwerk"
    machines: list[A650Machine] = field(default_factory=list)
    setup_machine: SetupMachine = field(default_factory=SetupMachine)
    cassette_pool: list[Cassette] = field(default_factory=list)
    cassette_types: list[CassetteType] = field(default_factory=list)
    orders: list[ProductionOrder] = field(default_factory=list)

    def get_available_cassettes(self, cassette_type: CassetteType) -> list[Cassette]:
        return [
            c for c in self.cassette_pool
            if c.cassette_type == cassette_type
            and c.state in (CassetteState.AVAILABLE, CassetteState.READY)
        ]

    def get_ready_cassettes(self, cassette_type: CassetteType) -> list[Cassette]:
        return [
            c for c in self.cassette_pool
            if c.cassette_type == cassette_type
            and c.state == CassetteState.READY
        ]

    def get_cassettes_in_use(self, cassette_type: CassetteType) -> list[Cassette]:
        return [
            c for c in self.cassette_pool
            if c.cassette_type == cassette_type
            and c.state == CassetteState.IN_USE
            and not c.is_depleted
        ]
