"""Operator tool: provision the bootstrap incident (DM-52).

`09` endpoint 3 requires a commander Session, and a Session authenticates against
an existing incident — so the first incident cannot be created through the API.
This tool closes that circularity **operationally**, without adding API surface,
weakening any documented `Session` requirement, or creating an auth bypass.

    PYTHONPATH=src python -m rescuenet.bootstrap

The password is read with ``getpass``: never echoed, never logged, never placed in
shell history. Only the scrypt hash is stored (docs/08 §11.1c) — the same
mechanism the API uses, not a second code path.
"""

from __future__ import annotations

import getpass
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import insert, select

from rescuenet.services.credentials import hash_password
from rescuenet.store import make_engine
from rescuenet.store.tables import incident as incident_table


def main() -> int:
    url = os.environ.get("RESCUENET_DATABASE_URL")
    if not url:
        print("RESCUENET_DATABASE_URL is not set. See README.", file=sys.stderr)
        return 2

    name = input("Incident name: ").strip()
    if not name:
        print("A name is required.", file=sys.stderr)
        return 2
    password = getpass.getpass("Commander password: ")
    if password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if len(password) < 12:
        print("Use at least 12 characters.", file=sys.stderr)
        return 2

    engine = make_engine(url)
    with engine.begin() as conn:
        existing = conn.execute(select(incident_table.c.incident_id)).first()
        if existing is not None:
            print(
                "An incident already exists. Bootstrap is for an empty deployment; "
                "create further incidents through the authenticated API.",
                file=sys.stderr,
            )
            return 1
        incident_id = conn.execute(
            insert(incident_table)
            .values(
                name=name, disaster_type="OTHER",
                origin_lat=0.0, origin_lon=0.0,
                started_at=datetime.now(timezone.utc),
                password_hash=hash_password(password),
            )
            .returning(incident_table.c.incident_id)
        ).scalar_one()

    # The password is never echoed back, and never logged.
    print(f"Provisioned incident {incident_id}. Log in with POST /v1/auth/session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
