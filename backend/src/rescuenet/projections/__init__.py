"""RescueNet backend — projections. Derived read models (docs/08 §7 and §11.2, M3).

Every read model here is derived and rebuildable; none is a source of truth.
"""

from rescuenet.projections.folds import (
    ASSIGNED,
    UNSEARCHED,
    AssignmentState,
    CellState,
    CoverageMetrics,
    DuplicateSearch,
    Projections,
    SurvivorRecord,
    TeamPosition,
    TeamState,
    fold_all,
    fold_assignment_state,
    fold_cell_state,
    fold_coverage_metrics,
    fold_duplicate_search,
    fold_resource_stock,
    fold_survivor_reports,
    fold_team_position,
    fold_team_state,
)
from rescuenet.projections.rebuild import clear_read_models, rebuild, watermark

__all__ = [
    "fold_all", "fold_cell_state", "fold_duplicate_search", "fold_assignment_state",
    "fold_team_state", "fold_team_position", "fold_resource_stock",
    "fold_survivor_reports", "fold_coverage_metrics",
    "Projections", "CellState", "DuplicateSearch", "AssignmentState", "TeamState",
    "TeamPosition", "SurvivorRecord", "CoverageMetrics",
    "ASSIGNED", "UNSEARCHED",
    "rebuild", "clear_read_models", "watermark",
]
