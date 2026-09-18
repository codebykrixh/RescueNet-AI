"""Value ranges, every one derived from the wire schema.

docs/09 §10.5 sets the precedent: a limit that the SMS wire field cannot
represent is a limit of the domain too, "derived from the field width, not
chosen independently — the two must never drift apart". Audit finding F-01 was
exactly what happens when they do drift, so every range here names the wire
field it comes from (docs/04 §3.1).
"""

from __future__ import annotations

from typing import Final

# --- Grid (docs/09 §10.5, audit F-01) -------------------------------------
#: 13-bit ``cell_index`` addresses 0..8191 — 8192 distinct values.
CELL_INDEX_BITS: Final[int] = 13
#: Maximum number of cells in a Level-1 grid.
MAX_CELLS: Final[int] = 8191
#: Highest index a cell may actually take.
MAX_CELL_INDEX: Final[int] = MAX_CELLS - 1          # 8190
#: Never allocated — a one-value safety margin at the top of the field.
RESERVED_CELL_INDEX: Final[int] = 8191

# --- Identity (docs/08 Part 1.1, D-05) -------------------------------------
DEVICE_ID_BITS: Final[int] = 12
MAX_DEVICE_ID: Final[int] = 2**DEVICE_ID_BITS - 1   # 4095
#: docs/08 DM-36 — reserved for server-authored events.
SERVER_DEVICE_ID: Final[int] = 0
#: docs/11 TR-22 — enrolment allocates from 1.
MIN_ENROLLED_DEVICE_ID: Final[int] = 1

SEQ_BITS: Final[int] = 20
MAX_SEQ: Final[int] = 2**SEQ_BITS - 1               # 1048575

# --- Attribution (docs/04 §3.1) -------------------------------------------
MAX_TEAM_ID: Final[int] = 2**8 - 1                  # 255
MAX_RESPONDER_ID: Final[int] = 2**10 - 1            # 1023
MAX_AGENCY_ID: Final[int] = 2**4 - 1                # 15

# --- Payload values (docs/04 §3.1) ----------------------------------------
MAX_PERSON_COUNT: Final[int] = 2**6 - 1             # 63
MAX_ITEM_ID: Final[int] = 2**8 - 1                  # 255
MIN_QTY_DELTA: Final[int] = -128                    # signed 8-bit
MAX_QTY_DELTA: Final[int] = 127
#: Origin-relative metres, signed 16-bit: ±32 km at 1 m resolution.
MIN_REL_COORD: Final[int] = -(2**15)                # -32768
MAX_REL_COORD: Final[int] = 2**15 - 1               # 32767

#: docs/08 Part 14 — the schema version this build writes.
CURRENT_SCHEMA_VERSION: Final[int] = 1
