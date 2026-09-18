"""TR-11 (index range half) and TR-12 (parametric grid) — docs/09 §10.5, DM-10."""
from __future__ import annotations

import math

import pytest

from rescuenet.domain import (
    Grid,
    GridError,
    column_letters,
    is_representable_cell_index,
)
from rescuenet.domain.limits import MAX_CELL_INDEX, MAX_CELLS, RESERVED_CELL_INDEX

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------- TR-11
def test_full_index_range_round_trips_without_collision():
    """Every valid index maps to a unique (row, col) and back — the check that
    would have caught audit finding F-01."""
    grid = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=8191, cols=1)
    seen: set[tuple[int, int]] = set()
    for index in range(grid.cell_count):
        row, col = grid.row_col(index)
        assert (row, col) not in seen, f"collision at {index}"
        seen.add((row, col))
        assert grid.cell_index(row, col) == index
    assert len(seen) == MAX_CELLS


def test_boundary_indices_both_sides():
    grid = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=8191, cols=1)
    assert grid.row_col(0) == (0, 0)                       # lowest valid
    assert grid.row_col(MAX_CELL_INDEX) == (8190, 0)       # highest valid
    with pytest.raises(GridError):
        grid.row_col(RESERVED_CELL_INDEX)                  # reserved
    with pytest.raises(GridError):
        grid.row_col(-1)


def test_reserved_index_is_never_representable():
    """docs/09 §10.5 — 8191 is addressable by the field but never allocated."""
    assert is_representable_cell_index(MAX_CELL_INDEX)
    assert not is_representable_cell_index(RESERVED_CELL_INDEX)
    assert not is_representable_cell_index(MAX_CELLS)       # same value, by name


def test_max_cells_is_derived_from_the_wire_field():
    """8191 cells, indices 0..8190, all inside 13 bits."""
    assert MAX_CELLS == 8191
    assert MAX_CELL_INDEX == MAX_CELLS - 1
    assert MAX_CELL_INDEX < 2**13
    assert MAX_CELLS > 5000, "must still exceed the NFR-09 evaluation target"


def test_grid_larger_than_max_cells_is_refused():
    with pytest.raises(GridError, match="MAX_CELLS"):
        Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=100, cols=100)


def test_grid_exactly_at_max_cells_is_accepted():
    grid = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=8191, cols=1)
    assert grid.cell_count == MAX_CELLS


def test_nfr09_target_grid_of_5000_cells_is_valid():
    grid = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=50, cols=100)
    assert grid.cell_count == 5000
    assert grid.contains(4999) and not grid.contains(5000)


# ---------------------------------------------------------------- TR-12
@pytest.fixture
def grid():
    return Grid(origin_lat=19.1638, origin_lon=73.6822, cell_size_m=100.0,
                rows=25, cols=200)


def test_index_decomposes_row_major(grid):
    assert grid.row_col(0) == (0, 0)
    assert grid.row_col(199) == (0, 199)
    assert grid.row_col(200) == (1, 0)
    assert grid.row_col(214) == (1, 14)


def test_row_col_round_trip_over_the_whole_grid(grid):
    for index in range(grid.cell_count):
        assert grid.cell_index(*grid.row_col(index)) == index


def test_bounds_are_derived_not_stored(grid):
    """DM-10 — geometry is computed from six numbers, never persisted."""
    assert grid.cell_bounds_local(0) == (0.0, 0.0, 100.0, 100.0)
    assert grid.cell_bounds_local(214) == (1400.0, 100.0, 1500.0, 200.0)


def test_centre_is_the_middle_of_the_bounds(grid):
    assert grid.cell_centre_local(0) == (50.0, 50.0)
    assert grid.cell_centre_local(214) == (1450.0, 150.0)


def test_bounds_are_deterministic(grid):
    assert grid.cell_bounds_local(214) == grid.cell_bounds_local(214)


def test_adjacent_cells_share_an_edge(grid):
    _, _, right_of_a, _ = grid.cell_bounds_local(0)
    left_of_b, *_ = grid.cell_bounds_local(1)
    assert right_of_a == left_of_b


def test_corners_are_four_points(grid):
    assert len(grid.cell_corners_local(0)) == 4


def test_bearing_rotates_geometry_and_preserves_size():
    plain = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=100.0, rows=2, cols=2)
    turned = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=100.0, rows=2, cols=2,
                  bearing_deg=90.0)
    assert plain.cell_corners_local(0) != turned.cell_corners_local(0)

    def edge(corners):
        (x0, y0), (x1, y1) = corners[0], corners[1]
        return math.hypot(x1 - x0, y1 - y0)

    assert edge(turned.cell_corners_local(0)) == pytest.approx(100.0)


def test_no_geometry_records_are_materialised(grid):
    """DM-12 — an untouched cell occupies nothing."""
    assert not hasattr(grid, "cells")
    assert set(vars(grid)) == {
        "origin_lat", "origin_lon", "cell_size_m", "rows", "cols", "bearing_deg"
    }


@pytest.mark.parametrize(
    "override",
    [{"rows": 0}, {"cols": 0}, {"rows": -1}, {"cell_size_m": 0.0},
     {"cell_size_m": -1.0}],
)
def test_invalid_grid_parameters_are_refused(override):
    params = {"origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 10.0,
              "rows": 5, "cols": 5} | override
    with pytest.raises(GridError):
        Grid(**params)


def test_index_outside_this_grid_is_refused(grid):
    with pytest.raises(GridError, match="outside this grid"):
        grid.validate_cell_index(grid.cell_count)


# ---------------------------------------------------------------- cell labels
# Rule: <COLUMN LETTERS>-<ROW NUMBER>, 1-based display, Excel column encoding.
# docs/05 §10, docs/08 §3.1. Labels are derived presentation only.

def test_first_cell_is_a_one(grid):
    assert grid.cell_label(0) == "A-1"


def test_first_row_walks_the_columns(grid):
    assert [grid.cell_label(i) for i in range(4)] == ["A-1", "B-1", "C-1", "D-1"]


def test_first_column_walks_the_rows(grid):
    assert [grid.cell_label(r * grid.cols) for r in range(4)] == [
        "A-1", "A-2", "A-3", "A-4"
    ]


@pytest.mark.parametrize(
    "index,expected",
    [(0, "A-1"), (1, "B-1"), (13, "N-1"), (199, "GR-1"),
     (200, "A-2"), (213, "N-2"), (214, "O-2")],
)
def test_documented_examples(grid, index, expected):
    """The worked examples recorded in docs/05 §10."""
    assert grid.cell_label(index) == expected


@pytest.mark.parametrize(
    "col,letters",
    [(0, "A"), (1, "B"), (24, "Y"), (25, "Z"), (26, "AA"), (27, "AB"),
     (51, "AZ"), (52, "BA"), (199, "GR"), (701, "ZZ"), (702, "AAA")],
)
def test_excel_style_column_encoding(col, letters):
    assert column_letters(col) == letters


def test_z_to_aa_transition_in_a_real_grid():
    """docs/03 §3.1 anticipated ambiguity at 26 columns; bijective base-26 solves it."""
    wide = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=2, cols=30)
    assert wide.cell_label(25) == "Z-1"
    assert wide.cell_label(26) == "AA-1"
    assert wide.cell_label(27) == "AB-1"


def test_multi_letter_columns():
    wide = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=1, cols=800)
    assert wide.cell_label(701) == "ZZ-1"
    assert wide.cell_label(702) == "AAA-1"


def test_multi_digit_rows():
    tall = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0, rows=150, cols=2)
    assert tall.cell_label(2 * 9) == "A-10"
    assert tall.cell_label(2 * 99) == "A-100"


def test_last_valid_cell_of_the_largest_grid():
    largest = Grid(origin_lat=0.0, origin_lon=0.0, cell_size_m=10.0,
                   rows=MAX_CELLS, cols=1)
    assert largest.cell_label(MAX_CELL_INDEX) == "A-8191"


def test_label_rejects_invalid_indexes_exactly_like_the_rest_of_the_grid(grid):
    for bad in (-1, grid.cell_count, RESERVED_CELL_INDEX):
        with pytest.raises(GridError):
            grid.cell_label(bad)


def test_labels_are_unique_across_a_whole_grid(grid):
    labels = [grid.cell_label(i) for i in range(grid.cell_count)]
    assert len(set(labels)) == grid.cell_count


def test_label_is_deterministic(grid):
    assert grid.cell_label(214) == grid.cell_label(214) == "O-2"


def test_label_round_trips_back_to_the_index(grid):
    for index in range(0, grid.cell_count, 37):
        assert grid.cell_index_from_label(grid.cell_label(index)) == index


def test_label_parsing_accepts_spoken_case_and_spacing(grid):
    assert grid.cell_index_from_label("  o-2 ") == 214


@pytest.mark.parametrize("bad", ["", "O2", "-2", "O-", "O-0", "9-9", "O-2-3"])
def test_malformed_labels_are_rejected(grid, bad):
    with pytest.raises(GridError):
        grid.cell_index_from_label(bad)


def test_label_outside_the_grid_is_rejected(grid):
    with pytest.raises(GridError):
        grid.cell_index_from_label("A-999")


def test_b14_is_a_real_cell_just_not_index_214(grid):
    """The corrected example: B-14 exists, but it is index 2601 at cols=200.

    docs/08 §16.6 previously paired 'B-14' with cell_index 214, which is
    arithmetically impossible for any integer grid width (13*cols+1 == 214 has
    no integer solution). Corrected in docs/08; recorded in docs/05 §10.
    """
    assert grid.cell_label(2601) == "B-14"
    assert grid.cell_index_from_label("B-14") == 2601
    assert grid.cell_label(214) == "O-2"


def test_labels_are_presentation_only_and_never_canonical_data():
    """Changing the label rule cannot touch the canonical event schema."""
    from rescuenet.domain import CanonicalEvent
    from rescuenet.domain.payloads import CellStatusReportedPayload

    assert "label" not in CanonicalEvent.model_fields
    assert "label" not in CellStatusReportedPayload.model_fields
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "src" / "rescuenet" / "domain" / "event.py"
    ).read_text()
    assert "cell_label" not in source and "column_letters" not in source
