"""The six fold rules (docs/08 §7.2).

Pure functions over canonical events. No SQL, no transport, no I/O — the same
semantics SP-05 validated 13/13 (docs/04 §3.2), expressed against the real
domain model instead of a simulation.

Three properties hold throughout and are what make the design work without
CRDTs (AD-14):

* the log is a **set union** keyed by ``(device_id, seq)`` — merging is union,
  which is already commutative, associative and idempotent;
* everything that *looks* mutable is a **fold computed at read time**, never a
  stored value that gets overwritten (DM-20);
* ordering uses ``server_seq`` — acceptance order, never causal order (DM-21).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from rescuenet.domain.enums import CellStatus, EventType

UNSEARCHED = "UNSEARCHED"
ASSIGNED = "ASSIGNED"


def _ordered(events: Iterable) -> list:
    """Ascending by ``server_seq``; uncommitted events sort last, then by identity.

    ``server_seq`` is a strictly monotonic single-writer sequence, so ties are
    impossible among committed events (docs/08 §7.3) — the secondary key exists
    only to keep the function total for not-yet-committed events.
    """
    return sorted(
        events,
        key=lambda e: (e.server_seq is None, e.server_seq or 0, e.device_id, e.seq),
    )


# ── rule 6 · cell status ────────────────────────────────────────────────────
@dataclass(frozen=True)
class CellState:
    incident_id: int
    cell_index: int
    status: str
    team_id: int | None
    last_server_seq: int | None


def fold_cell_state(events: Iterable) -> dict[tuple[int, int], CellState]:
    """Rule 6 — latest ``CELL_STATUS_REPORTED`` by ``server_seq``; else ``ASSIGNED``
    if a live assignment exists; else ``UNSEARCHED``."""
    holders = fold_assignment_state(events)
    latest: dict[tuple[int, int], object] = {}
    for e in _ordered(events):
        if e.type is EventType.CELL_STATUS_REPORTED:
            latest[(e.incident_id, e.payload["cell_index"])] = e

    out: dict[tuple[int, int], CellState] = {}
    for key, e in latest.items():
        out[key] = CellState(key[0], key[1], e.payload["status"], e.team_id, e.server_seq)
    for key, holder in holders.items():
        if key not in out and holder.team_id is not None:
            out[key] = CellState(key[0], key[1], ASSIGNED, holder.team_id,
                                 holder.last_server_seq)
    return out


# ── rule 1 · duplicate search ───────────────────────────────────────────────
@dataclass(frozen=True)
class DuplicateSearch:
    incident_id: int
    cell_index: int
    team_ids: tuple[int, ...]

    @property
    def team_count(self) -> int:
        return len(self.team_ids)


def fold_duplicate_search(events: Iterable) -> dict[tuple[int, int], DuplicateSearch]:
    """Rule 1 — a cell searched by two or more distinct teams (D-01b).

    A **set-cardinality predicate with no ordering term**, which is why the
    flagship demo is immune to the AL-05 acceptance-order inversion (DM-22).
    """
    teams: dict[tuple[int, int], set[int]] = defaultdict(set)
    for e in events:
        if (
            e.type is EventType.CELL_STATUS_REPORTED
            and e.payload.get("status") == CellStatus.SEARCHED.value
        ):
            teams[(e.incident_id, e.payload["cell_index"])].add(e.team_id)
    return {
        key: DuplicateSearch(key[0], key[1], tuple(sorted(ids)))
        for key, ids in teams.items()
        if len(ids) >= 2
    }


# ── rule 4 · assignments ────────────────────────────────────────────────────
@dataclass(frozen=True)
class AssignmentState:
    incident_id: int
    cell_index: int
    team_id: int | None
    assignment_id: int | None
    last_server_seq: int


def fold_assignment_state(events: Iterable) -> dict[tuple[int, int], AssignmentState]:
    """Rule 4 — per cell, the latest ISSUED/REVOKED by ``server_seq``.

    D-01 makes all assignments originate from the one online dashboard through
    one server, so ``server_seq`` is a genuine total order over them and no
    concurrent assignment is structurally possible.
    """
    cells_of_assignment: dict[int, list[tuple[int, int]]] = {}
    out: dict[tuple[int, int], AssignmentState] = {}

    for e in _ordered(events):
        if e.type is EventType.ASSIGNMENT_ISSUED:
            aid = e.payload["assignment_id"]
            keys = [(e.incident_id, c) for c in e.payload["cell_ids"]]
            cells_of_assignment[aid] = keys
            for key in keys:
                out[key] = AssignmentState(key[0], key[1], e.payload["team_id"], aid,
                                           e.server_seq or 0)
        elif e.type is EventType.ASSIGNMENT_REVOKED:
            aid = e.payload["assignment_id"]
            for key in cells_of_assignment.get(aid, []):
                out[key] = AssignmentState(key[0], key[1], None, aid, e.server_seq or 0)
    return out


# ── rule 3 · team status ────────────────────────────────────────────────────
@dataclass(frozen=True)
class TeamState:
    team_id: int
    callsign: str | None = None
    agency_id: int | None = None
    status: str | None = None
    last_server_seq: int | None = None


def fold_team_state(events: Iterable) -> dict[int, TeamState]:
    """Rule 3 — registration plus the latest ``TEAM_STATUS_REPORTED``."""
    out: dict[int, TeamState] = {}
    for e in _ordered(events):
        if e.type is EventType.TEAM_REGISTERED:
            p = e.payload
            prev = out.get(p["team_id"])
            out[p["team_id"]] = TeamState(
                p["team_id"], p["callsign"], p["agency_id"],
                prev.status if prev else None, e.server_seq,
            )
        elif e.type is EventType.TEAM_STATUS_REPORTED:
            prev = out.get(e.team_id, TeamState(e.team_id))
            out[e.team_id] = TeamState(
                e.team_id, prev.callsign, prev.agency_id,
                e.payload["team_status"], e.server_seq,
            )
    return out


# ── position (latest per team) ──────────────────────────────────────────────
@dataclass(frozen=True)
class TeamPosition:
    team_id: int
    rel_lat: int
    rel_lon: int
    t_srv: object | None
    last_server_seq: int


def fold_team_position(events: Iterable) -> dict[int, TeamPosition]:
    out: dict[int, TeamPosition] = {}
    for e in _ordered(events):
        if e.type is EventType.POSITION_REPORTED:
            out[e.team_id] = TeamPosition(
                e.team_id, e.payload["rel_lat"], e.payload["rel_lon"],
                e.t_srv, e.server_seq or 0,
            )
    return out


# ── rule 2 · inventory ──────────────────────────────────────────────────────
def fold_resource_stock(events: Iterable) -> dict[tuple[int, int], int]:
    """Rule 2 — additive sum of signed deltas.

    Commutative, so **no conflict is representable**. Negative totals are
    returned as-is, not clamped: a negative reading is information.
    """
    totals: dict[tuple[int, int], int] = defaultdict(int)
    for e in events:
        if e.type is EventType.RESOURCE_DELTA_REPORTED:
            totals[(e.team_id, e.payload["item_id"])] += e.payload["qty_delta"]
    return dict(totals)


# ── rule 5 · survivor reports ───────────────────────────────────────────────
@dataclass(frozen=True)
class SurvivorRecord:
    device_id: int
    seq: int
    incident_id: int
    cell_index: int
    person_count: int
    survivor_status: str
    triage: str | None
    team_id: int
    agency_id: int
    server_seq: int | None


def fold_survivor_reports(events: Iterable) -> list[SurvivorRecord]:
    """Rule 5 — the **full set**, never deduplicated, never suppressed (AL-11)."""
    out = []
    for e in _ordered(events):
        if e.type is EventType.SURVIVOR_REPORTED:
            p = e.payload
            out.append(SurvivorRecord(
                e.device_id, e.seq, e.incident_id, p["cell_index"],
                p["person_count"], p["survivor_status"], p.get("triage"),
                e.team_id, e.agency_id, e.server_seq,
            ))
    return out


# ── coverage metrics (AP-24) ────────────────────────────────────────────────
@dataclass(frozen=True)
class CoverageMetrics:
    incident_id: int
    total: int
    searched: int
    in_progress: int
    needs_research: int
    assigned: int
    unsearched: int


def fold_coverage_metrics(events: Iterable) -> dict[int, CoverageMetrics]:
    """AP-24 — a second-order projection of ``cell_state`` plus the grid size.

    Server-owned and computed exactly once here. The dashboard never recomputes
    it, so the fold cannot exist in two places and diverge (docs/09 §5.3).
    """
    grid_total: dict[int, int] = {}
    for e in _ordered(events):
        if e.type is EventType.GRID_GENERATED:
            grid_total[e.incident_id] = e.payload["rows"] * e.payload["cols"]

    states = fold_cell_state(events)
    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (incident_id, _), state in states.items():
        counts[incident_id][state.status] += 1

    out: dict[int, CoverageMetrics] = {}
    for incident_id in set(grid_total) | set(counts):
        c = counts[incident_id]
        total = grid_total.get(incident_id, 0)
        searched = c.get(CellStatus.SEARCHED.value, 0)
        in_progress = c.get(CellStatus.IN_PROGRESS.value, 0)
        needs = c.get(CellStatus.NEEDS_RESEARCH.value, 0)
        assigned = c.get(ASSIGNED, 0)
        out[incident_id] = CoverageMetrics(
            incident_id, total, searched, in_progress, needs, assigned,
            max(total - (searched + in_progress + needs + assigned), 0),
        )
    return out


@dataclass(frozen=True)
class Projections:
    """Everything derivable from a set of events, in one deterministic pass."""

    cell_state: dict = field(default_factory=dict)
    duplicate_search: dict = field(default_factory=dict)
    assignment_state: dict = field(default_factory=dict)
    team_state: dict = field(default_factory=dict)
    team_position: dict = field(default_factory=dict)
    resource_stock: dict = field(default_factory=dict)
    survivor_reports: list = field(default_factory=list)
    coverage_metrics: dict = field(default_factory=dict)


def fold_all(events: Iterable) -> Projections:
    events = list(events)
    return Projections(
        cell_state=fold_cell_state(events),
        duplicate_search=fold_duplicate_search(events),
        assignment_state=fold_assignment_state(events),
        team_state=fold_team_state(events),
        team_position=fold_team_position(events),
        resource_stock=fold_resource_stock(events),
        survivor_reports=fold_survivor_reports(events),
        coverage_metrics=fold_coverage_metrics(events),
    )
