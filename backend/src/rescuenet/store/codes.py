"""Stable numeric wire codes for enum columns (docs/08 §11.1, DM-33).

docs/08 §11.1 stores ``type``, ``entity_type`` and ``received_via`` as
``smallint`` wire codes. DM-33 makes those codes **permanent — never reused,
even if a type is retired**, because reuse would make old rows unreadable.

PROVENANCE — read this before changing anything here.

**None of these three mappings is specified by the documentation.** A contract
review on 2026-08-23 established that:

* docs/08 §11.1 fixes the *storage type* (``smallint``) for all three, and
  DM-33 makes **type** codes permanent — but no document assigns a number to any
  value.
* The ``#`` column in docs/08 §2.1/§2.2 is a **table row counter**, not a
  declared wire code. An earlier M3 note described it as "documented, not chosen
  here"; that was an overstatement and is corrected here.
* ``ENTITY_TYPE_CODE`` and ``RECEIVED_VIA_CODE`` follow the order in which
  docs/08 §1.1 lists the values. That ordering is documented; its use as a
  numeric encoding is not.

So all three mappings were **chosen during M3 implementation** from documented
orderings. They are stable, plausible and locked by ``test_wire_codes.py``, but
they are **awaiting ratification in docs/08** and must not be treated as a
settled contract until that happens.

Impact if they were to change: ``type`` is persisted and permanent under DM-33,
so changing it would make stored rows unreadable. ``entity_type`` and
``received_via`` are persisted but never transmitted (``entity_type`` is implied
by ``type``, docs/09 §10.4; ``received_via`` is server-set), so a change would
require only a data migration, not a wire-format change.
"""

from __future__ import annotations

from rescuenet.domain.enums import EntityType, EventType, ReceivedVia

#: docs/08 §2.1 rows 1–6, §2.2 rows 7–11.
EVENT_TYPE_CODE: dict[EventType, int] = {
    EventType.INCIDENT_DECLARED: 1,
    EventType.GRID_GENERATED: 2,
    EventType.TEAM_REGISTERED: 3,
    EventType.DEVICE_ENROLLED: 4,
    EventType.ASSIGNMENT_ISSUED: 5,
    EventType.ASSIGNMENT_REVOKED: 6,
    EventType.CELL_STATUS_REPORTED: 7,
    EventType.SURVIVOR_REPORTED: 8,
    EventType.RESOURCE_DELTA_REPORTED: 9,
    EventType.POSITION_REPORTED: 10,
    EventType.TEAM_STATUS_REPORTED: 11,
}

#: Order of docs/08 §1.1's entity_type enum listing.
ENTITY_TYPE_CODE: dict[EntityType, int] = {
    EntityType.CELL: 1,
    EntityType.TEAM: 2,
    EntityType.SURVIVOR: 3,
    EntityType.RESOURCE: 4,
    EntityType.INCIDENT: 5,
    EntityType.GRID: 6,
    EntityType.DEVICE: 7,
    EntityType.ASSIGNMENT: 8,
}

#: Order of docs/08 §1.1's received_via enum listing.
RECEIVED_VIA_CODE: dict[ReceivedVia, int] = {
    ReceivedVia.INTERNET: 1,
    ReceivedVia.SMS: 2,
}

EVENT_TYPE_BY_CODE = {code: member for member, code in EVENT_TYPE_CODE.items()}
ENTITY_TYPE_BY_CODE = {code: member for member, code in ENTITY_TYPE_CODE.items()}
RECEIVED_VIA_BY_CODE = {code: member for member, code in RECEIVED_VIA_CODE.items()}
