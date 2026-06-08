"""Solver registry — pick a solver by name."""

from .base import FingeringSolver, SolverResult
from .dynamic import DynamicSolver
from .greedy import GreedySolver
from .graph import GraphSolver
from .viterbi import ViterbiSolver


SOLVERS = {
    "dynamic": DynamicSolver,
    "greedy":  GreedySolver,
    "graph":   GraphSolver,
    "viterbi": ViterbiSolver,
}


def get_solver(name):
    if name not in SOLVERS:
        raise ValueError(f"Unknown solver {name!r}. Available: {list(SOLVERS)}")
    return SOLVERS[name]
