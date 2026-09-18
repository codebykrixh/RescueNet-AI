"""Enumerations of the canonical model (docs/08 Parts 1–2).

Exactly the 11 Level-1 event types. No duplicate-search type (DM-07), no
sync/ack types (DM-08), no audit types (DM-09), no REJECTED — that is an outbox
delivery state, never an event type (DM-39).
"""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    """The 11 Level-1 event types (docs/08 §2.1–§2.2). Wire codes are permanent
    and never reused, even if a type is retired (DM-33)."""

    # Server-authored control events (docs/08 §2.1)
    INCIDENT_DECLARED = "INCIDENT_DECLARED"
    GRID_GENERATED = "GRID_GENERATED"
    TEAM_REGISTERED = "TEAM_REGISTERED"
    DEVICE_ENROLLED = "DEVICE_ENROLLED"
    ASSIGNMENT_ISSUED = "ASSIGNMENT_ISSUED"
    ASSIGNMENT_REVOKED = "ASSIGNMENT_REVOKED"
    # Device-authored field events (docs/08 §2.2)
    CELL_STATUS_REPORTED = "CELL_STATUS_REPORTED"
    SURVIVOR_REPORTED = "SURVIVOR_REPORTED"
    RESOURCE_DELTA_REPORTED = "RESOURCE_DELTA_REPORTED"
    POSITION_REPORTED = "POSITION_REPORTED"
    TEAM_STATUS_REPORTED = "TEAM_STATUS_REPORTED"


class EntityType(str, Enum):
    """docs/08 Part 1.1. ``entity_type`` is implied by ``type`` (docs/09 §10.4)."""

    CELL = "CELL"
    TEAM = "TEAM"
    SURVIVOR = "SURVIVOR"
    RESOURCE = "RESOURCE"
    INCIDENT = "INCIDENT"
    GRID = "GRID"
    DEVICE = "DEVICE"
    ASSIGNMENT = "ASSIGNMENT"


class Priority(str, Enum):
    """Two tiers only (D-04). Derived from event type, never stored (DM-02)."""

    CRITICAL = "CRITICAL"
    ROUTINE = "ROUTINE"


class ReceivedVia(str, Enum):
    """Server-set provenance (docs/08 Part 1.1)."""

    INTERNET = "INTERNET"
    SMS = "SMS"


class CellStatus(str, Enum):
    """docs/08 §2.2 event 7."""

    IN_PROGRESS = "IN_PROGRESS"
    SEARCHED = "SEARCHED"
    NEEDS_RESEARCH = "NEEDS_RESEARCH"


class SurvivorStatus(str, Enum):
    """docs/08 §2.2 event 8."""

    TRAPPED = "TRAPPED"
    ACCESSIBLE = "ACCESSIBLE"
    EXTRICATED = "EXTRICATED"
    DECEASED = "DECEASED"


class Triage(str, Enum):
    """Optional triage category (docs/08 §2.2 event 8).

    Not clinically validated — docs/05 AL-08 requires this to be stated
    wherever triage appears.
    """

    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLACK = "BLACK"


class TeamStatus(str, Enum):
    """docs/08 §2.2 event 11."""

    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class DisasterType(str, Enum):
    """docs/08 §2.1 event 1; the incident types named in PS-B1."""

    LANDSLIDE = "LANDSLIDE"
    BUILDING_COLLAPSE = "BUILDING_COLLAPSE"
    OTHER = "OTHER"


#: docs/08 §2.2 — exactly one Level-1 type is CRITICAL. SOS joins at Level 2.
_CRITICAL_TYPES = frozenset({EventType.SURVIVOR_REPORTED})

#: docs/09 §10.4 / docs/08 §16.8 — entity_type is implied by type.
_ENTITY_TYPE_BY_EVENT_TYPE: dict[EventType, EntityType] = {
    EventType.INCIDENT_DECLARED: EntityType.INCIDENT,
    EventType.GRID_GENERATED: EntityType.GRID,
    EventType.TEAM_REGISTERED: EntityType.TEAM,
    EventType.DEVICE_ENROLLED: EntityType.DEVICE,
    EventType.ASSIGNMENT_ISSUED: EntityType.ASSIGNMENT,
    EventType.ASSIGNMENT_REVOKED: EntityType.ASSIGNMENT,
    EventType.CELL_STATUS_REPORTED: EntityType.CELL,
    EventType.SURVIVOR_REPORTED: EntityType.SURVIVOR,
    EventType.RESOURCE_DELTA_REPORTED: EntityType.RESOURCE,
    EventType.POSITION_REPORTED: EntityType.TEAM,
    EventType.TEAM_STATUS_REPORTED: EntityType.TEAM,
}


def priority_for(event_type: EventType) -> Priority:
    """Priority is a pure function of type — the single source of truth (DM-02).

    Storing priority on the event would create a second source able to disagree
    with the type, which is why the canonical schema has no priority field.
    """
    return Priority.CRITICAL if event_type in _CRITICAL_TYPES else Priority.ROUTINE


def entity_type_for(event_type: EventType) -> EntityType:
    """The entity type implied by an event type (docs/09 §10.4)."""
    return _ENTITY_TYPE_BY_EVENT_TYPE[event_type]
