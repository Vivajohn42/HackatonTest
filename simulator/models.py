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
    NEEDS_TEARDOWN = auto()


@dataclass
class Cassette:
    id: str
    cassette_type: CassetteType
    state: CassetteState = CassetteState.AVAILABLE
    setup_remaining_min: float = 0.0
    assigned_machine: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class SetupMachine:
    id: str = "SETUP-1"
    setup_duration_min: float = 12.0
    current_cassette: Optional[Cassette] = None
    busy_until: float = 0.0
    queue: list[Cassette] = field(default_factory=list)

    def is_busy(self, current_time: float) -> bool:
        return current_time < self.busy_until

    def start_setup(self, cassette: Cassette, current_time: float) -> float:
        cassette.state = CassetteState.IN_SETUP
        cassette.setup_remaining_min = self.setup_duration_min
        self.current_cassette = cassette
        self.busy_until = current_time + self.setup_duration_min
        return self.busy_until

    def complete_setup(self) -> Optional[Cassette]:
        if self.current_cassette is None:
            return None
        cassette = self.current_cassette
        cassette.state = CassetteState.READY
        cassette.setup_remaining_min = 0.0
        self.current_cassette = None
        return cassette


class MachineState(Enum):
    IDLE = auto()
    PRODUCING = auto()
    CHANGEOVER = auto()


@dataclass
class A650Machine:
    id: str
    state: MachineState = MachineState.IDLE
    cassette_left: Optional[Cassette] = None
    cassette_right: Optional[Cassette] = None
    current_order: Optional[ProductionOrder] = None
    busy_until: float = 0.0
    changeover_duration_min: float = 1.0

    total_produced: int = 0
    total_changeovers: int = 0
    total_idle_min: float = 0.0
    total_production_min: float = 0.0
    total_changeover_min: float = 0.0

    def needs_changeover(self, order: ProductionOrder) -> tuple[bool, bool]:
        need_left = (
            self.cassette_left is None
            or self.cassette_left.cassette_type != order.cassette_type_left
        )
        need_right = (
            self.cassette_right is None
            or self.cassette_right.cassette_type != order.cassette_type_right
        )
        return need_left, need_right

    def changeover_time(self, order: ProductionOrder) -> float:
        need_left, need_right = self.needs_changeover(order)
        changes = int(need_left) + int(need_right)
        return changes * self.changeover_duration_min


class OrderPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ProductionOrder:
    id: str
    wire_type: str
    wire_cross_section_mm2: float
    wire_length_mm: float
    quantity: int
    cassette_type_left: CassetteType
    cassette_type_right: CassetteType
    priority: OrderPriority = OrderPriority.NORMAL
    due_time: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    assigned_machine: Optional[str] = None

    @property
    def processing_time_min(self) -> float:
        base_time = 0.5
        time_per_wire = 0.05 + (self.wire_length_mm / 1000) * 0.02
        return base_time + self.quantity * time_per_wire

    @property
    def is_completed(self) -> bool:
        return self.end_time is not None


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
