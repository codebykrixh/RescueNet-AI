"""Packing of the ratified SMS wire format — ``docs/09`` §6.6 / **DM-57**.

Encode-only. The backend never *decodes* SMS: the gateway forwards decoded
canonical JSON (``09`` §6.5 — "The FastAPI backend contains no SMS logic"). What
the backend does need is to **re-pack** a relayed batch bit-for-bit so it can
recompute the MAC, because the MAC covers packed wire bytes (DM-49).

Widths mirror ``mobile/.../codec/WireLimits.kt``. Both sides are locked by
TR-11/TR-12, so a drift fails loudly on one side or the other.
"""

from __future__ import annotations

from typing import Any, Final

from rescuenet.codec.bitio import BitWriter
from rescuenet.domain.enums import CellStatus, EventType, SurvivorStatus, TeamStatus, Triage
from rescuenet.store.codes import EVENT_TYPE_CODE

# --- header, docs/09 §6.6.1 -------------------------------------------------
PROTO_VERSION_BITS: Final = 4
DEVICE_ID_BITS: Final = 12
TEAM_ID_BITS: Final = 8
AGENCY_ID_BITS: Final = 4
INCIDENT_ID_BITS: Final = 12
SCHEMA_VERSION_BITS: Final = 4
BASE_SEQ_BITS: Final = 20
BASE_T_BITS: Final = 20
EVENT_COUNT_BITS: Final = 5
HEADER_BITS: Final = 89

# --- event common prefix, docs/09 §6.6.2 ------------------------------------
EVT_TYPE_BITS: Final = 4          # DM-01: widened 3 -> 4
SEQ_DELTA_BITS: Final = 6
T_DELTA_BITS: Final = 12

# --- payload fields ---------------------------------------------------------
CELL_INDEX_BITS: Final = 13
STATUS_BITS: Final = 3
RESPONDER_ID_BITS: Final = 10
PERSON_COUNT_BITS: Final = 6
SURVIVOR_STATUS_BITS: Final = 3
TRIAGE_BITS: Final = 3
TEAM_STATUS_BITS: Final = 3
ITEM_ID_BITS: Final = 8
QTY_DELTA_BITS: Final = 8
REL_COORD_BITS: Final = 16
PRESENCE_MASK_BITS: Final = 3

# --- framing and budget, docs/09 §6.6.4 / §6.6.7 ----------------------------
FRAMING_BITS: Final = 68
MAC_BYTES: Final = 4
MAX_BATCH_BYTES: Final = 120
FIXED_OVERHEAD_BITS: Final = FRAMING_BITS + HEADER_BITS      # 157
EVENT_CAPACITY_BITS: Final = MAX_BATCH_BYTES * 8 - FIXED_OVERHEAD_BITS  # 803
PROTO_VERSION: Final = 1

#: SCOPE A — the four SMS-eligible uplink types (M8-6). The other seven have no
#: SMS layout; ``POSITION_REPORTED`` is never sent over SMS (M8-7).
SMS_ELIGIBLE: Final[frozenset[EventType]] = frozenset(
    {
        EventType.CELL_STATUS_REPORTED,
        EventType.SURVIVOR_REPORTED,
        EventType.RESOURCE_DELTA_REPORTED,
        EventType.TEAM_STATUS_REPORTED,
    }
)

#: Positional wire codes, matching the Kotlin enums and ``08`` §2.2 order.
CELL_STATUS_CODE: Final = {CellStatus.IN_PROGRESS: 0, CellStatus.SEARCHED: 1, CellStatus.NEEDS_RESEARCH: 2}
SURVIVOR_STATUS_CODE: Final = {
    SurvivorStatus.TRAPPED: 0, SurvivorStatus.ACCESSIBLE: 1,
    SurvivorStatus.EXTRICATED: 2, SurvivorStatus.DECEASED: 3,
}
TRIAGE_CODE: Final = {Triage.RED: 0, Triage.YELLOW: 1, Triage.GREEN: 2, Triage.BLACK: 3}
TEAM_STATUS_CODE: Final = {TeamStatus.ACTIVE: 0, TeamStatus.STANDBY: 1, TeamStatus.OUT_OF_SERVICE: 2}


class WireEncodingError(ValueError):
    """A value cannot be represented. **Never** truncate — ``08`` §10.1 rule 2."""


def pack_header(w: BitWriter, header: dict[str, Any]) -> None:
    """Pack the nine header fields in the ratified order."""
    w.write(header.get("proto_version", PROTO_VERSION), PROTO_VERSION_BITS)
    w.write(header["device_id"], DEVICE_ID_BITS)
    w.write(header["team_id"], TEAM_ID_BITS)
    w.write(header["agency_id"], AGENCY_ID_BITS)
    w.write(header["incident_id"], INCIDENT_ID_BITS)
    w.write(header["schema_version"], SCHEMA_VERSION_BITS)
    w.write(header["base_seq"], BASE_SEQ_BITS)
    w.write(header["base_t"], BASE_T_BITS)
    w.write(header["event_count"], EVENT_COUNT_BITS)


def _enum(raw: Any, enum_cls: Any, table: dict[Any, int], field: str) -> int:
    try:
        return table[enum_cls(raw)]
    except (KeyError, ValueError) as exc:
        raise WireEncodingError(f"unknown {field} value {raw!r}") from exc


def pack_event(w: BitWriter, event_type: EventType, seq_delta: int, t_delta: int,
               responder_id: int, payload: dict[str, Any]) -> None:
    """Pack one SMS-eligible event after the common prefix."""
    if event_type not in SMS_ELIGIBLE:
        raise WireEncodingError(
            f"{event_type.value} has no SMS layout — SCOPE A carries only "
            f"{sorted(t.value for t in SMS_ELIGIBLE)}"
        )
    w.write(EVENT_TYPE_CODE[event_type], EVT_TYPE_BITS)
    w.write(seq_delta, SEQ_DELTA_BITS)
    w.write(t_delta, T_DELTA_BITS)

    if event_type is EventType.CELL_STATUS_REPORTED:
        w.write(payload["cell_index"], CELL_INDEX_BITS)
        w.write(_enum(payload["status"], CellStatus, CELL_STATUS_CODE, "status"), STATUS_BITS)
        w.write(responder_id, RESPONDER_ID_BITS)
    elif event_type is EventType.RESOURCE_DELTA_REPORTED:
        w.write(payload["item_id"], ITEM_ID_BITS)
        w.write_signed(payload["qty_delta"], QTY_DELTA_BITS)
        w.write(responder_id, RESPONDER_ID_BITS)
    elif event_type is EventType.TEAM_STATUS_REPORTED:
        w.write(_enum(payload["team_status"], TeamStatus, TEAM_STATUS_CODE, "team_status"), TEAM_STATUS_BITS)
        w.write(responder_id, RESPONDER_ID_BITS)
    else:  # SURVIVOR_REPORTED
        triage = payload.get("triage")
        rel_lat = payload.get("rel_lat")
        rel_lon = payload.get("rel_lon")
        mask = (0b100 if triage is not None else 0) | \
               (0b010 if rel_lat is not None else 0) | \
               (0b001 if rel_lon is not None else 0)
        w.write(mask, PRESENCE_MASK_BITS)
        w.write(payload["cell_index"], CELL_INDEX_BITS)
        w.write(payload["person_count"], PERSON_COUNT_BITS)
        w.write(_enum(payload["survivor_status"], SurvivorStatus, SURVIVOR_STATUS_CODE, "survivor_status"),
                SURVIVOR_STATUS_BITS)
        if triage is not None:
            w.write(_enum(triage, Triage, TRIAGE_CODE, "triage"), TRIAGE_BITS)
        if rel_lat is not None:
            w.write_signed(rel_lat, REL_COORD_BITS)
        if rel_lon is not None:
            w.write_signed(rel_lon, REL_COORD_BITS)
        w.write(responder_id, RESPONDER_ID_BITS)


def event_bits(event_type: EventType, payload: dict[str, Any]) -> int:
    """Exact packed size of one event, without encoding it."""
    base = EVT_TYPE_BITS + SEQ_DELTA_BITS + T_DELTA_BITS
    if event_type is EventType.CELL_STATUS_REPORTED:
        return base + CELL_INDEX_BITS + STATUS_BITS + RESPONDER_ID_BITS
    if event_type is EventType.RESOURCE_DELTA_REPORTED:
        return base + ITEM_ID_BITS + QTY_DELTA_BITS + RESPONDER_ID_BITS
    if event_type is EventType.TEAM_STATUS_REPORTED:
        return base + TEAM_STATUS_BITS + RESPONDER_ID_BITS
    if event_type is EventType.SURVIVOR_REPORTED:
        return (base + PRESENCE_MASK_BITS + CELL_INDEX_BITS + PERSON_COUNT_BITS
                + SURVIVOR_STATUS_BITS
                + (TRIAGE_BITS if payload.get("triage") is not None else 0)
                + (REL_COORD_BITS if payload.get("rel_lat") is not None else 0)
                + (REL_COORD_BITS if payload.get("rel_lon") is not None else 0)
                + RESPONDER_ID_BITS)
    raise WireEncodingError(f"{event_type.value} has no SMS layout")


def encode_payload(header: dict[str, Any], events: list[dict[str, Any]]) -> bytes:
    """Pack ``header || events`` — exactly the byte sequence the MAC covers.

    Framing is **not** included (``09`` §6.6.5). Events must already be in
    ascending ``seq`` order; this function never reorders them.
    """
    if len(events) != header["event_count"]:
        raise WireEncodingError(
            f"event_count {header['event_count']} disagrees with {len(events)} events"
        )
    w = BitWriter()
    pack_header(w, header)
    last = -1
    for e in events:
        sd = e["seq_delta"]
        if sd <= last:
            raise WireEncodingError(f"events must ascend by seq; {sd} follows {last}")
        last = sd
        pack_event(w, e["type"], sd, e["t_delta"], e["responder_id"], e["payload"])
    return w.to_bytes()
