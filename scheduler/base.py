from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.models import A650Machine, Plant, ProductionOrder


class BaseScheduler(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def schedule(
        self,
        pending_orders: list[ProductionOrder],
        plant: Plant,
        current_time: float,
    ) -> list[dict]:
        ...
