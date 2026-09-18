"""Batch event ingestion (endpoint 7) — docs/09 Part 2.

Partial acceptance is mandatory (AP-04): a batch returns ``200`` even when some
events are rejected, because rejecting the whole batch for one bad event would
block the outbox permanently — the bad event can never succeed, so everything
queued behind it would never send.
"""

from __future__ import annotations

from sqlalchemy import Connection, func, select

from rescuenet.domain import EventValidationError, Priority, RejectionCode, parse_event
from rescuenet.domain.limits import MAX_CELL_INDEX
from rescuenet.domain.validation import may_permanently_reject
from rescuenet.store import append, max_server_seq


def _reject(device_id, seq, code: RejectionCode, message: str) -> dict:
    from rescuenet.domain.validation import is_retryable

    return {
        "device_id": device_id, "seq": seq, "code": code.value,
        "retryable": is_retryable(code), "message": message,
    }


def _highest_accepted_seq(conn: Connection, device_id: int) -> int:
    """The device's highest already-accepted ``seq`` (TR-22)."""
    from rescuenet.store.tables import event as event_table

    return conn.execute(
        select(func.coalesce(func.max(event_table.c.seq), -1)).where(
            event_table.c.device_id == device_id)
    ).scalar_one()


def ingest_batch(conn: Connection, batch: dict, caller=None) -> dict:
    """Ingest a batch, returning the documented accepted/rejected structure.

    Security rules applied here (M5):

    * **FIELD** — every event's ``device_id`` must equal the authenticated
      device (docs/09 Part 7.2).
    * **GATEWAY** — may relay other devices' events. Author authenticity is
      **not** verified until M8 supplies the MAC path (DM-51).
    * ``WRONG_INCIDENT`` — the event's incident must match the caller's scope.
    * ``SEQ_NOT_MONOTONIC`` — ``seq`` must exceed the device's highest accepted
      value (TR-22, docs/09 §2.6). Gaps are legal (DM-13); going backwards is not.
    """
    accepted: list[dict] = []
    rejected: list[dict] = []
    highest: dict[int, int] = {}

    for raw in batch.get("events", []):
        device_id, seq = raw.get("device_id"), raw.get("seq")

        try:
            canonical = parse_event(raw)
        except EventValidationError as exc:
            rejected.append(_reject(device_id, seq, exc.code, exc.message))
            continue

        # AP-20 — reference errors must never permanently reject a CRITICAL
        # event. A mistyped cell_index must not discard a survivor's location.
        cell_index = canonical.payload.get("cell_index")
        if cell_index is not None and cell_index > MAX_CELL_INDEX:
            if may_permanently_reject(RejectionCode.UNKNOWN_CELL, canonical.priority):
                rejected.append(_reject(
                    device_id, seq, RejectionCode.UNKNOWN_CELL,
                    f"cell_index {cell_index} not in grid",
                ))
                continue
            # CRITICAL: accepted, and flagged for commander attention.

        # ── M5 authorization on the authenticated caller ──
        if caller is not None:
            if caller.role == "FIELD" and canonical.device_id != caller.device_id:
                rejected.append(_reject(
                    device_id, seq, RejectionCode.ATTRIBUTION_MISMATCH,
                    "FIELD credentials may only submit their own device's events"))
                continue
            if (caller.incident_id is not None
                    and canonical.incident_id != caller.incident_id):
                rejected.append(_reject(
                    device_id, seq, RejectionCode.WRONG_INCIDENT,
                    "event incident_id does not match the credential's incident"))
                continue

        # ── TR-22 · seq must be strictly monotonic per device ──
        if canonical.device_id not in highest:
            highest[canonical.device_id] = _highest_accepted_seq(conn, canonical.device_id)
        previous = highest[canonical.device_id]
        if canonical.seq < previous:
            rejected.append(_reject(
                device_id, seq, RejectionCode.SEQ_NOT_MONOTONIC,
                f"seq {canonical.seq} is below the device's highest accepted {previous}"))
            continue

        result = append(conn, canonical)
        highest[canonical.device_id] = max(previous, canonical.seq)
        accepted.append({
            "device_id": result.device_id, "seq": result.seq,
            "server_seq": result.server_seq, "was_duplicate": result.was_duplicate,
        })

    return {
        "accepted": accepted,
        "rejected": rejected,
        "server_seq_high": max_server_seq(conn),
    }
