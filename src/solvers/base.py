"""Common interface and result type for fingering solvers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SolverResult:
    cost: float
    path: list                                # [(notes, fingers), ...]
    node_visits: int = 0
    extras: dict = field(default_factory=dict)  # solver-specific stats


class FingeringSolver(ABC):
    def __init__(self, layers, hand="R"):
        self.layers = layers
        self.hand = hand

    @abstractmethod
    def solve(self) -> SolverResult:
        ...
