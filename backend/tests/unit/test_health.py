"""M1: `/health` returns service status (docs/12 M1 tests, docs/09 endpoint 14)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_health_returns_200(client):
    assert client.get("/health").status_code == 200


def test_health_body_matches_contract(client):
    """docs/09: `/health` returns `{status, db, broker}` — exactly those keys."""
    body = client.get("/health").json()
    assert set(body) == {"status", "db", "broker"}


def test_health_reports_application_ok(client):
    assert client.get("/health").json()["status"] == "ok"


def test_backing_services_are_unchecked_not_ok(client):
    """M1 has no store or publisher, so neither may be reported healthy.

    Claiming `ok` for a component nothing has checked would be a fabricated
    result (docs/05 §7). They become real at M3 and M10.
    """
    body = client.get("/health").json()
    assert body["db"] == "unchecked"
    assert body["broker"] == "unchecked"


def test_health_requires_no_authentication(client):
    """docs/09: unauthenticated by contract."""
    assert client.get("/health", headers={}).status_code == 200


def test_health_exposes_no_operational_data(client):
    """docs/09: 'exposes no operational data'."""
    body = client.get("/health").json()
    forbidden = {
        "server_seq", "events", "event_count", "incident", "incident_id",
        "device_id", "teams", "cells", "version", "database_url", "settings",
    }
    assert not (forbidden & set(body))


#: Routes FastAPI mounts for its own documentation UI. These are not application
#: routes and never appear in the OpenAPI schema, which is precisely why the
#: schema is the right thing to assert against.
FASTAPI_DOC_ROUTES = frozenset(
    {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
)


def _application_paths(app) -> set[str]:
    """The authoritative set of application HTTP paths.

    Reads the OpenAPI schema rather than ``app.routes``. ``app.routes`` is not a
    reliable source: a router added with ``include_router`` is held as a single
    router object whose ``.path`` attribute is absent, so every path it carries —
    including ``/health`` — is invisible to a naive scan of that collection. A
    guard built on ``app.routes`` therefore passes whether or not endpoints have
    been added, which makes it worthless as a guard.
    """
    return set(app.openapi()["paths"])


def test_health_is_registered_as_an_application_route(client):
    assert "/health" in _application_paths(client.app)


#: The exact surface after M5: 11 M4 operational endpoints + 3 M5 auth endpoints.
#: Asserted as method+path pairs, not just paths.
M4_ENDPOINTS = frozenset({
    ("get", "/health"),                                  # 14
    ("post", "/v1/incidents"),                           # 3
    ("post", "/v1/incidents/{incident_id}/grid"),        # 4
    ("post", "/v1/teams"),                               # 5
    ("post", "/v1/events"),                              # 7
    ("get", "/v1/events"),                               # 8
    ("get", "/v1/incidents/{incident_id}/snapshot"),     # 9
    ("post", "/v1/assignments"),                         # 10
    ("delete", "/v1/assignments/{assignment_id}"),       # 11
    ("get", "/v1/incidents/{incident_id}/export"),       # 12
    ("get", "/v1/diag/sync"),                            # 13
})

#: M5-owned (docs/12 §3.2), delivered at M5.
M5_ENDPOINTS = frozenset({
    ("post", "/v1/enrol"),                               # 1
    ("post", "/v1/auth/session"),                        # 2
    ("post", "/v1/teams/{team_id}/join-code"),           # 6
})

ALL_ENDPOINTS = M4_ENDPOINTS | M5_ENDPOINTS

def _operations(app) -> set[tuple[str, str]]:
    """Every (method, path) pair the application exposes."""
    return {
        (method, path)
        for path, ops in app.openapi()["paths"].items()
        for method in ops
        if method in ("get", "post", "put", "patch", "delete")
    }


def test_exactly_the_fourteen_endpoints_are_registered(client):
    """11 M4 operational + 3 M5 auth endpoints, and nothing else."""
    actual = _operations(client.app)
    assert actual == ALL_ENDPOINTS, (
        f"missing: {sorted(ALL_ENDPOINTS - actual)}  "
        f"unexpected: {sorted(actual - ALL_ENDPOINTS)}")
    assert len(actual) == 14


def test_all_eleven_m4_endpoints_survive_m5(client):
    assert M4_ENDPOINTS <= _operations(client.app)


def test_exactly_three_m5_endpoints_added(client):
    assert M5_ENDPOINTS <= _operations(client.app)
    assert len(M5_ENDPOINTS) == 3


def test_no_m6_plus_endpoints(client):
    """No Android, dashboard, SMS or MQTT endpoint may appear."""
    paths = set(client.app.openapi()["paths"])
    forbidden = [p for p in paths
                 if any(k in p for k in ("sms", "mqtt", "peer", "sync/push", "codec"))]
    assert not forbidden, forbidden


def test_health_still_registered(client):
    assert ("get", "/health") in _operations(client.app)


def test_fastapi_doc_routes_are_not_application_routes(client):
    """/docs, /redoc and /openapi.json must not be counted as application routes."""
    paths = _application_paths(client.app)
    assert not (paths & FASTAPI_DOC_ROUTES)
    # ...and they are still served, they simply are not part of the API surface.
    assert client.get("/openapi.json").status_code == 200
