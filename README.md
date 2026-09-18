# RescueNet AI

**Multi-Agency Coordination Platform for Search-and-Rescue Operations**

A shared, real-time operational picture for disaster sites where multiple agencies — NDRF,
SDRF, police, fire services and volunteer organisations — search a gridded area under
chaotic, low-bandwidth conditions. Built offline-first, because the network is treated as
an optional accelerator and never a dependency.

> **Status: M0 — repository bootstrap.** No application code exists yet. The specification
> phase (docs 01–12) is complete and approved.

## The specification is the contract

Read these before changing anything. They are authoritative.

| Doc | Contents |
|---|---|
| [01](docs/01-requirements-analysis.md) | Requirements analysis — every requirement, traced to the problem statement |
| [02](docs/02-prototype-scope.md) | Prototype scope — Level 1 / 2 / 3, A–D classification |
| [03](docs/03-feasibility-analysis.md) | Feasibility — per-package analysis, transport comparison |
| [04](docs/04-feasibility-validation.md) | Spike results — **executed evidence, kept separate from assumptions** |
| [05](docs/05-final-decisions.md) | Final decisions, accepted limitations, and the claim gate |
| [06](docs/06-system-architecture.md) | System architecture — 28 decisions, 8 diagrams |
| [07](docs/07-technology-selection.md) | Technology selection — the stack, and what is forbidden |
| [08](docs/08-data-and-event-model.md) | Data and event model — the canonical event schema |
| [09](docs/09-api-and-mqtt-contracts.md) | REST, MQTT and SMS contracts |
| [10](docs/10-final-contract-audit.md) | Cross-document audit and remediation record |
| [11](docs/11-test-strategy.md) | Test register — every Level-1 contract has a planned test |
| [12](docs/12-implementation-plan.md) | Implementation plan — milestones M0…M14 |

`spikes/` holds feasibility **evidence**, not source. It is excluded from every build and
CI path, and nothing there may be copied into `src` — it is rewritten from the requirements.

## Layout

```
backend/     Python + FastAPI, modular monolith          M1–M5, M10
mobile/      Native Kotlin Android field application     M6–M9, M12
dashboard/   React + TypeScript commander dashboard      M11
shared/      Canonical fixtures + generated OpenAPI      M2+
deploy/      Docker Compose: PostgreSQL + Mosquitto      M0
tests/       Cross-component contract tests              M13
```

## Architecture in one paragraph

The **backend event store is authoritative**. Every operational fact is an immutable,
append-only event identified by `(device_id, seq)`, allocated on the device so it works
offline with no coordination. **REST carries every durable write and every authoritative
read.** **MQTT is notification-only** — it publishes post-commit, carries `server_seq` so a
subscriber can detect a gap, and any gap is repaired by a REST delta; the dashboard's broker
credential is subscribe-only, so MQTT cannot become a write path. **SMS is a fallback
transport** confined behind a transport abstraction, with all wire knowledge inside the
codec. State that looks mutable — cell status, inventory, coverage — is a deterministic fold
over the log, never a stored value that gets overwritten. Nothing accepted is ever discarded.

## Getting started

Infrastructure only; no application code exists yet.

```bash
cp deploy/.env.example deploy/.env          # then fill in real values
# generate deploy/mosquitto/passwd — see deploy/mosquitto/passwd.example
cp deploy/mosquitto/acl.example deploy/mosquitto/acl
cd deploy && docker compose up -d           # postgres + mosquitto
```

Running backend tests or tooling **from the host** (not in a container) needs the
database URL with the host-facing address. Credentials live only in `deploy/.env`;
export the host variant from there so the two can never drift apart:

```bash
export RESCUENET_DATABASE_URL="$(grep '^DATABASE_URL_HOST=' deploy/.env | cut -d= -f2-)"
```

The application reads exactly one variable, `RESCUENET_DATABASE_URL`, and never knows
which environment it is in. Compose injects it for the container (host `postgres`);
the command above supplies it on the host (host `127.0.0.1`). No host address is
hard-coded anywhere in application code.

### Bootstrap incident (required once per deployment)

`POST /v1/incidents` requires a commander **Session**, and a session authenticates against
an existing incident's password. The first incident therefore **cannot** be created through
the API — it is provisioned out-of-band, exactly like the broker credentials above. This is
an operational step, **not an API capability**, and no bootstrap or admin endpoint exists.

```bash
cd backend
export RESCUENET_DATABASE_URL="$(grep '^DATABASE_URL_HOST=' ../deploy/.env | cut -d= -f2-)"
PYTHONPATH=src ./.venv/bin/python -m rescuenet.bootstrap
```

The tool prompts for the password with `getpass`, so it never appears in your shell history,
your terminal, or any log. It stores only the **scrypt** hash (`n=2^14, r=8, p=1`, 16-byte
per-incident salt — docs/08 §11.1c), the same mechanism the API uses. Plaintext is never
persisted.

Once that incident exists, a commander logs in with `POST /v1/auth/session` and every
subsequent incident is created through the authenticated API normally.

**Security properties:** the bootstrap password is as strong as you choose it; anyone able
to run this tool already has database credentials, so it grants no privilege they lacked;
and it does not weaken the documented `Session` requirement on any endpoint.

Never commit `deploy/.env`, `deploy/mosquitto/passwd`, `deploy/mosquitto/acl`, keystores or
certificates. `.gitignore` enforces this; do not weaken it.

## Honest status of SMS

The manual wire test established that generated GSM-7 payloads were transmitted **unaltered
between the two tested handset/SIM routes, in both directions**, and that payloads up to
**459 characters arrived intact**. **Segment counts were not observed. Carrier identities
were not recorded. Programmatic Android SMS is not validated (SP-01b-A is open), and the
application does not send SMS.**

Open spikes: SP-01b-A (programmatic SMS) · SP-02 (peer sync) · SP-03 (dashboard render load)
· SP-04 (offline persistence) · SP-06 (MQTT gap recovery).

## Contributing rules

1. The specification is authoritative. Architecture and technology decisions are closed.
2. Only technologies listed in docs/07 §A. No Kubernetes, microservices, Redis,
   Elasticsearch, GraphQL, PostGIS, CRDT frameworks or component libraries.
3. Never claim a capability that has no recorded evidence — docs/05 §7 is the gate.
4. Never commit a secret.
