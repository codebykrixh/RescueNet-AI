"""Parametric grid (docs/08 DM-10, docs/09 §10.5, FR-203/FR-204).

The grid is defined by six numbers, and every cell's position and geometry is
computed from ``cell_index``. A 5,000-cell grid therefore costs one event, not
5,000, and no cell geometry is ever stored or transmitted (DM-10, DM-12).

Geometry is expressed in **local metres east/north of the incident origin**,
optionally rotated by the grid bearing. That is exact, deterministic and needs
no geodesy library — projecting to lat/lon is a presentation concern and does
not belong in the domain (docs/06 §3 rule 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rescuenet.domain.limits import MAX_CELL_INDEX, MAX_CELLS, RESERVED_CELL_INDEX


class GridError(ValueError):
    """Grid parameters or a cell reference are invalid."""


@dataclass(frozen=True)
class Grid:
    """A published grid. Immutable once generated (FR-205)."""

    origin_lat: float
    origin_lon: float
    cell_size_m: float
    rows: int
    cols: int
    bearing_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise GridError("rows and cols must both be >= 1")
        if self.cell_size_m <= 0:
            raise GridError("cell_size_m must be > 0")
        if self.cell_count > MAX_CELLS:
            raise GridError(
                f"grid of {self.rows}x{self.cols}={self.cell_count} cells exceeds "
                f"MAX_CELLS={MAX_CELLS} (docs/09 §10.5)"
            )

    @property
    def cell_count(self) -> int:
        return self.rows * self.cols

    # -- index <-> row/col -------------------------------------------------
    def row_col(self, cell_index: int) -> tuple[int, int]:
        """Row-major decomposition of a cell index."""
        self.validate_cell_index(cell_index)
        return divmod(cell_index, self.cols)

    def cell_index(self, row: int, col: int) -> int:
        """Inverse of :meth:`row_col`."""
        if not (0 <= row < self.rows):
            raise GridError(f"row {row} outside 0..{self.rows - 1}")
        if not (0 <= col < self.cols):
            raise GridError(f"col {col} outside 0..{self.cols - 1}")
        return row * self.cols + col

    def contains(self, cell_index: int) -> bool:
        """Whether the index falls inside *this* grid.

        Distinct from :func:`is_representable_cell_index`, which asks only
        whether the wire schema can carry the value at all.
        """
        return 0 <= cell_index < self.cell_count

    def validate_cell_index(self, cell_index: int) -> None:
        if not is_representable_cell_index(cell_index):
            raise GridError(
                f"cell_index {cell_index} is not representable: valid range is "
                f"0..{MAX_CELL_INDEX} ({RESERVED_CELL_INDEX} is reserved)"
            )
        if not self.contains(cell_index):
            raise GridError(
                f"cell_index {cell_index} outside this grid of {self.cell_count} cells"
            )

    # -- geometry ----------------------------------------------------------
    def cell_bounds_local(self, cell_index: int) -> tuple[float, float, float, float]:
        """Axis-aligned bounds in metres east/north of origin, before bearing.

        Returns ``(min_east, min_north, max_east, max_north)``.
        """
        row, col = self.row_col(cell_index)
        min_e = col * self.cell_size_m
        min_n = row * self.cell_size_m
        return (min_e, min_n, min_e + self.cell_size_m, min_n + self.cell_size_m)

    def cell_corners_local(
        self, cell_index: int
    ) -> tuple[tuple[float, float], ...]:
        """The four corners in metres from origin, rotated by ``bearing_deg``.

        Corner order is south-west, south-east, north-east, north-west before
        rotation. Rotation is clockwise, matching a compass bearing.
        """
        min_e, min_n, max_e, max_n = self.cell_bounds_local(cell_index)
        corners = ((min_e, min_n), (max_e, min_n), (max_e, max_n), (min_e, max_n))
        if self.bearing_deg == 0.0:
            return corners
        theta = math.radians(self.bearing_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        return tuple(
            (e * cos_t + n * sin_t, -e * sin_t + n * cos_t) for e, n in corners
        )

    def cell_centre_local(self, cell_index: int) -> tuple[float, float]:
        """Cell centre in metres from origin, rotated by ``bearing_deg``."""
        min_e, min_n, max_e, max_n = self.cell_bounds_local(cell_index)
        e, n = (min_e + max_e) / 2.0, (min_n + max_n) / 2.0
        if self.bearing_deg == 0.0:
            return (e, n)
        theta = math.radians(self.bearing_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        return (e * cos_t + n * sin_t, -e * sin_t + n * cos_t)

    # -- label -------------------------------------------------------------
    def cell_label(self, cell_index: int) -> str:
        """Human-speakable cell label (FR-204), per docs/05 §10 / docs/08 §3.1.

        ``<COLUMN LETTERS>-<ROW NUMBER>`` — columns alphabetic, rows numeric,
        both 1-based for display, hyphen separator, Excel-style column encoding.

        Purely derived presentation. Labels are never transmitted (DM-10) and
        never persisted as canonical event data.
        """
        row, col = self.row_col(cell_index)          # validates the index
        return f"{column_letters(col)}-{row + 1}"

    def cell_index_from_label(self, label: str) -> int:
        """Inverse of :meth:`cell_label`, for radio-spoken input.

        Raises :class:`GridError` if the label is malformed or outside the grid.
        """
        text = label.strip().upper()
        if "-" not in text:
            raise GridError(f"label {label!r} must be <LETTERS>-<NUMBER>")
        letters, _, number = text.partition("-")
        if not letters.isalpha() or not number.isdigit():
            raise GridError(f"label {label!r} must be <LETTERS>-<NUMBER>")
        col = column_index(letters)
        row = int(number) - 1
        if row < 0:
            raise GridError(f"label {label!r} has a row below 1")
        return self.cell_index(row, col)


def is_representable_cell_index(cell_index: int) -> bool:
    """Whether the 13-bit wire field can carry this index (docs/09 §10.5).

    ``RESERVED_CELL_INDEX`` (8191) is addressable by the field but never
    allocated, so it is *not* representable as a cell.
    """
    return isinstance(cell_index, int) and 0 <= cell_index <= MAX_CELL_INDEX


def column_letters(col: int) -> str:
    """0-based column index to Excel-style letters: 0->A, 25->Z, 26->AA, 701->ZZ.

    Bijective base-26 — there is no "zero digit", which is why ``Z`` is followed
    by ``AA`` rather than ``BA`` (docs/03 §3.1 anticipated this at 26 columns).
    """
    if col < 0:
        raise GridError(f"column index {col} is negative")
    letters, n = "", col + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def column_index(letters: str) -> int:
    """Inverse of :func:`column_letters`. ``A`` -> 0, ``AA`` -> 26."""
    text = letters.strip().upper()
    if not text or not text.isalpha():
        raise GridError(f"column {letters!r} must be one or more letters")
    value = 0
    for character in text:
        value = value * 26 + (ord(character) - ord("A") + 1)
    return value - 1
