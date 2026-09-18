"""TR-22 — event identity is (device_id, seq) (D-05, DM-06, DM-36)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from rescuenet.domain import EventIdentity, SERVER_DEVICE_ID
from rescuenet.domain.limits import MAX_DEVICE_ID, MAX_SEQ, MIN_ENROLLED_DEVICE_ID

pytestmark = pytest.mark.unit


def test_identity_is_the_pair(canonical_event):
    e = canonical_event()
    assert e.identity == EventIdentity(device_id=e.device_id, seq=e.seq)


def test_identity_is_not_a_uuid_timestamp_hash_or_server_seq(canonical_event):
    """D-05: identity must not be replaced by any of these."""
    e = canonical_event(server_seq=999)
    assert set(EventIdentity.model_fields) == {"device_id", "seq"}
    assert e.identity.device_id == e.device_id and e.identity.seq == e.seq
    # server_seq is acceptance order, never identity
    other = canonical_event(server_seq=12345)
    assert other.identity == e.identity


def test_two_devices_same_seq_are_different_events(canonical_event):
    """The duplicate-search case: same action, two devices, two facts (DM-15)."""
    a = canonical_event(device_id=17, seq=4021)
    b = canonical_event(device_id=22, seq=4021)
    assert a.identity != b.identity


def test_identity_is_hashable_and_usable_as_a_dedup_key(canonical_event):
    a = canonical_event(device_id=17, seq=1)
    b = canonical_event(device_id=17, seq=1, server_seq=77)
    assert len({a.identity, b.identity}) == 1


@pytest.mark.parametrize("device_id", [-1, MAX_DEVICE_ID + 1])
def test_device_id_outside_the_wire_range_is_rejected(device_id):
    with pytest.raises(ValidationError):
        EventIdentity(device_id=device_id, seq=0)


@pytest.mark.parametrize("device_id", [0, MIN_ENROLLED_DEVICE_ID, MAX_DEVICE_ID])
def test_device_id_boundaries_accepted(device_id):
    assert EventIdentity(device_id=device_id, seq=0).device_id == device_id


@pytest.mark.parametrize("seq", [-1, MAX_SEQ + 1])
def test_seq_outside_the_wire_range_is_rejected(seq):
    with pytest.raises(ValidationError):
        EventIdentity(device_id=1, seq=seq)


@pytest.mark.parametrize("seq", [0, MAX_SEQ])
def test_seq_boundaries_accepted(seq):
    assert EventIdentity(device_id=1, seq=seq).seq == seq


def test_device_zero_is_reserved_for_the_server(canonical_event):
    """DM-36 — server-authored events use device_id 0."""
    assert EventIdentity(device_id=SERVER_DEVICE_ID, seq=1).is_server_authored
    assert not EventIdentity(device_id=1, seq=1).is_server_authored


def test_enrolment_range_starts_at_one(canonical_event):
    """TR-22 — enrolment allocates 1..4095; 0 is reserved."""
    assert MIN_ENROLLED_DEVICE_ID == 1
    assert SERVER_DEVICE_ID == 0
    assert MIN_ENROLLED_DEVICE_ID > SERVER_DEVICE_ID
