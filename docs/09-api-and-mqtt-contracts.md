# RescueNet AI — API and MQTT Contracts (v1.0)

**Date:** 2026-08-22 · **Stage:** External contracts · **Target:** Minimum Demonstrable Spine (D-03)
**Baseline:** [`06`](06-system-architecture.md) architecture · [`07`](07-technology-selection.md) stack · [`08`](08-data-and-event-model.md) data model — **none of them modified here**

> **No implementation.** No code, no folders, no UI.

**Parties to these contracts:** Android field app · Android gateway (same APK) · FastAPI backend · PostgreSQL authoritative state · Mosquitto broker · commander dashboard.

---

## 0. The `REJECTED` delivery state — APPROVED 2026-08-22

Writing the ingestion contract surfaced a case `08` did not cover. **DM-17 stated there is no terminal outbox state**, reasoning that a terminal state implies discard. That reasoning was about **transmission** failure and still holds. **Server rejection is a different case**: an event failing *semantic* validation fails identically on every retry, consuming the scarcest resource in the system.

**AP-14 is approved.** `REJECTED` is now a terminal **delivery** state, bound by the following constraints. `08` Part 6 has been amended accordingly (DM-39, DM-40); **the canonical event schema in `08` Part 1 is unchanged.**

| # | Constraint | Where satisfied |
|---|---|---|
| 1 | Applies only to outbox/delivery state | `08` 6.2 table; all new fields are outbox columns |
| 2 | The domain event remains permanently stored and auditable | `08` 6.2; §2.7 below |
| 3 | The event is never deleted because it was rejected | `08` 6.2; DM-39 |
| 4 | Permanent failures must not block later valid events | §2.7.3 — a `REJECTED` row is not `PENDING`, so it is never selected |
| 5 | Retryable failures remain `PENDING` | §2.7.1; the server's `retryable` flag is authoritative |
| 6 | A rejected event carries enough diagnostic information | Four outbox columns (`08` 6.1) + §2.7.4 |
| 7 | The server distinguishes retryable from permanent | §2.6 classification; `retryable` on every rejection |
| 8 | Partial batch acceptance preserved | AP-04, unchanged; §2.3 |
| 9 | No canonical event schema change | Confirmed — delivery metadata only (DM-39) |

---

# PART 1 — REST API contract

## 1.0 Conventions

| Aspect | Rule |
|---|---|
| Base path | `/v1` — version in the path, matching NFR-16's reduced form (`02` L2-09) |
| Content type | `application/json; charset=utf-8` |
| Auth header | `Authorization: Bearer <token>` |
| Time format | RFC 3339 UTC |
| Compression | **None** at Level 1 (AD-20). Not requested, not required |
| Cursor | Always `server_seq`, a plain integer (Part 3) |
| Error format | One shape, everywhere (Part 9) |
| OpenAPI | Served at `/v1/openapi.json` — this **is** the FR-901/FR-902 evidence |

## 1.1 Endpoint inventory — 14 endpoints, all required

| # | Method | Path | Purpose | Auth | Level-1 justification |
|---|---|---|---|---|---|
| 1 | `POST` | `/v1/enrol` | Device joins an incident with a join code | Join code | FR-104, Spine el. 3 |
| 2 | `POST` | `/v1/auth/session` | Commander dashboard login | Incident password | FR-103, D-01 |
| 3 | `POST` | `/v1/incidents` | Declare an incident | Session | Spine el. 1 |
| 4 | `POST` | `/v1/incidents/{id}/grid` | Generate the grid | Session | FR-203, Spine el. 2 |
| 5 | `POST` | `/v1/teams` | Register a team | Session | FR-101/102, Spine el. 3 |
| 6 | `POST` | `/v1/teams/{id}/join-code` | Mint a join code for a team | Session | FR-104 |
| 7 | `POST` | `/v1/events` | **Batch event upload — the only device write path** | Device or Gateway | FR-801, Spine el. 1/7 |
| 8 | `GET` | `/v1/events` | Delta sync **and** audit history (filtered) | Device or Session | FR-802, FR-1001, Part 3 |
| 9 | `GET` | `/v1/incidents/{id}/snapshot` | Initial load — read models + `current_server_seq` | Device or Session | `06` §11, Part 3 |
| 10 | `POST` | `/v1/assignments` | Commander issues an assignment | Session | FR-301, FR-706 |
| 11 | `DELETE` | `/v1/assignments/{id}` | Commander revokes an assignment | Session | FR-307 |
| 12 | `GET` | `/v1/incidents/{id}/export` | GeoJSON / CSV export | Session | FR-905, EC-04 |
| 13 | `GET` | `/v1/diag/sync` | Sync diagnostics — watermarks, outbox depth | Session | T-19, EC-01 evidence |
| 14 | `GET` | `/health` | Liveness | None | T-19 |

**Milestone ownership** (added 2026-08-23; `12` §3.2). **No request or response semantics
below are changed by this note** — it records only which milestone builds each endpoint.

- **M4 — operational API:** 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14
- **M5 — authentication:** 1 (`/v1/enrol`), 2 (`/v1/auth/session`), 6 (`/v1/teams/{id}/join-code`)

The `Auth` column above remains binding. M4 ships its endpoints **without** authentication
enforcement as a transitional state; **M5 must enforce every `Auth`/`AuthZ` requirement in
this document across all of them** (`12` §3.2.1).

**Endpoints deliberately not created**, and why:

| Not created | Reason |
|---|---|
| `GET /v1/cells`, `/v1/teams/{id}/position`, `/v1/survivors`, `/v1/resources` | All are in the snapshot and maintained by delta. Per-entity read endpoints would invite the dashboard to poll, defeating the MQTT+delta design. **AP-01** |
| `GET /v1/audit/...` | Audit **is** `GET /v1/events` with entity filters. A separate endpoint would be a second view of the same source of truth (DM-32) |
| `PATCH`/`PUT` anything | Nothing is mutable (DM-05). There is no update verb in this API |
| `POST /v1/auth/refresh` | Device tokens are long-lived and revocable; no refresh at Level 1 (Part 8) |
| Per-event upload `POST /v1/events/{one}` | Batching is mandatory for bandwidth (Part 10) |

## 1.2 Endpoint specifications

### 1 · `POST /v1/enrol`

| | |
|---|---|
| **Purpose** | Bind a handset to a team and issue its credentials (FR-104, FR-105) |
| **Auth** | The join code itself. No bearer token |
| **AuthZ** | Code must be unused or within its use limit, and not expired |
| **Request** | `{ "join_code": "K7QM4P", "device_label": "Nokia-A", "mode": "FIELD" \| "GATEWAY" }` |
| **Response 201** | `{ "device_id": 17, "token": "<opaque>", "hmac_secret": "<base64>", "incident_id": 9, "team_id": 3, "agency_id": 1, "responder_id": 71, "server_seq": 1203, "role": "FIELD" }` |
| **Statuses** | `201` · `400` malformed · `404` unknown code · `409` code exhausted/expired · `503` |
| **Idempotency** | **Not idempotent by design.** Two enrolments with one code produce **two distinct `device_id`s** — which is correct, because two physical handsets must never share an identity (D-05 would break). **AP-02** |
| **Pagination** | n/a |
| **Bandwidth** | ~300 B response, once per device lifetime |
| **Traceability** | FR-104, FR-105, `06` §14, DM-11 |

`hmac_secret` is delivered **once, over TLS, and never again**. It is not retrievable. It exists in `device_credential` (DM-11) and in the handset's encrypted storage only.

### 2 · `POST /v1/auth/session`

| | |
|---|---|
| **Purpose** | Commander dashboard login (D-01: online only) |
| **Request** | `{ "incident_id": 9, "password": "…" }` |
| **Response 200** | `{ "token": "<opaque>", "expires_at": "…", "role": "COMMANDER", "incident_id": 9, "mqtt": { "url": "…", "username": "rescuenet-dashboard", "password": "…", "topic": "rescuenet/v1/incident/9/notify" } }` — the `mqtt` block delivers the **configured** subscribe-only credential (§4.4, AP-23) |
| **Statuses** | `200` · `401` bad password · `404` unknown incident · `503` |
| **Idempotency** | Repeated login issues a new token; old tokens remain valid until expiry |
| **Bandwidth** | ~200 B |
| **Traceability** | FR-103, D-01, `06` §14 |

### 3 · `POST /v1/incidents` · 4 · `POST /v1/incidents/{id}/grid` · 5 · `POST /v1/teams`

These three share a shape: **the commander states an intent, and the server authors the corresponding event** with `device_id = 0` (DM-36). The dashboard never allocates `(device_id, seq)`.

| | `POST /v1/incidents` | `POST /v1/incidents/{id}/grid` | `POST /v1/teams` |
|---|---|---|---|
| **Emits** | `INCIDENT_DECLARED` | `GRID_GENERATED` | `TEAM_REGISTERED` |
| **Request** | `{name, disaster_type, origin_lat, origin_lon, started_at}` | `{origin_lat, origin_lon, cell_size_m, rows, cols, bearing_deg}` | `{callsign, agency_id, agency_type}` |
| **Response 201** | `{incident_id, server_seq}` | `{incident_id, cell_count, server_seq}` | `{team_id, server_seq}` |
| **Statuses** | `201·400·401·422·503` | `201·400·401·409·422·503` | `201·400·401·422·503` |
| **`409` case** | — | **Grid already generated.** Immutable once published (FR-205) | — |
| **`422` case** | invalid coordinates | `rows × cols` exceeds **`MAX_CELLS` = 8,191** (see Part 10.5) | unknown `agency_id` |
| **Bandwidth** | ~250 B | ~200 B request → **one event**, not 5,000 (DM-10) | ~150 B |

### 6 · `POST /v1/teams/{id}/join-code`

Returns `{ "join_code": "K7QM4P", "expires_at": "…", "max_uses": 5 }`. Statuses `201·401·404·503`. Traces to FR-104, AL-04 (trust-on-first-use is accepted and disclosed).

### 7 · `POST /v1/events` — the ingestion endpoint

Fully specified in Part 2.

### 8 · `GET /v1/events` — delta sync and audit history

Fully specified in Part 3 (sync) and Part 1.3 (audit filters).

### 9 · `GET /v1/incidents/{id}/snapshot`

| | |
|---|---|
| **Purpose** | Initial load. Returns folded read models plus the cursor to continue from |
| **Auth** | Device token or session token |
| **AuthZ** | Caller must belong to the incident. `scope` is constrained by role |
| **Query** | `scope=field\|command` |
| **`scope=field`** | incident, grid params, teams, **my** assignment, `cell_state`, resource catalogue + **my** stock |
| **`scope=command`** | everything above for all teams, plus `duplicate_search`, `team_position`, `survivor_report`, `coverage_metrics` (§5.3) |
| **Response 200** | `{ "current_server_seq": 1203, "incident": {…}, "grid": {…}, "teams": […], "cell_state": [[214,"SEARCHED",3], …], "…": … }` |
| **Statuses** | `200·401·403·404·503` |
| **Idempotency** | Safe, cacheable per `current_server_seq` |
| **Pagination** | **None** — a snapshot is atomic by definition. Size is bounded by the grid cap (Part 10) |
| **Bandwidth** | **The most expensive operation in the API.** `cell_state` uses positional arrays, not objects — ~15 B/cell rather than ~45 B. See Part 10 |
| **Traceability** | `06` §11, DM-12, DM-30 |

**`cell_state` omits untouched cells entirely** (DM-12): an unsearched 5,000-cell grid contributes zero entries, because the grid parameters already describe it.

### 10 · `POST /v1/assignments` · 11 · `DELETE /v1/assignments/{id}`

| | POST | DELETE |
|---|---|---|
| **Emits** | `ASSIGNMENT_ISSUED` (`device_id=0`) | `ASSIGNMENT_REVOKED` (`device_id=0`) |
| **Request** | `{ "team_id": 3, "cell_ids": [214,215,216], "note": "…" }` | — |
| **Response** | `201 { "assignment_id": 45, "server_seq": 412, "already_held": [] }` | `200 { "server_seq": 620 }` |
| **Statuses** | `201·400·401·403·404·422·503` | `200·401·404·503` |
| **Duplicate-assignment handling** | **`201` with `already_held` populated**, not `409`. FR-303 requires the collision to be *surfaced*, not to block the commander. The response names the holding team so the UI can warn. **AP-03** |
| **Idempotency** | Not idempotent — each call is a distinct commander decision and a distinct event |
| **Bandwidth** | ~150 B + 4 B/cell |
| **Traceability** | FR-301, FR-303, FR-307, 7.2 rule 4 in `08` |

**D-01 removes assignment concurrency entirely**: all assignments originate from the one online dashboard through one server, so `server_seq` is a genuine total order over them (`08` 7.2 rule 4).

### 12 · `GET /v1/incidents/{id}/export`

`?format=geojson|csv`. Returns grid cell states and survivor reports. Statuses `200·401·404·422·503`. Bandwidth: proportional to touched cells; a deliberate, occasional, human-triggered operation. Traces to FR-905, EC-04.

### 13 · `GET /v1/diag/sync` · 14 · `GET /health`

Diagnostics returns `{ current_server_seq, events_total, events_by_transport, projection_lag, mqtt_connected, last_publish_server_seq }`. This is how EC-01 evidence gets captured during the demo (T-19). `/health` returns `{status, db, broker}` — **unauthenticated, and it exposes no operational data.**

## 1.3 Audit filters on `GET /v1/events`

| Query param | Meaning |
|---|---|
| `since` | Sync cursor — exclusive lower bound on `server_seq` (Part 3) |
| `entity_type` + `entity_id` | Audit: everything touching one entity |
| `team_id` | Audit: everything a team did |
| `type` | Filter by event type |
| `limit` | Page size |

**"What happened to grid O-2?"** → `GET /v1/events?entity_type=CELL&entity_id=214&limit=200`, returning the ordered narrative in `08` Part 13.2. Audit reads the **source of truth**, never a projection (DM-32).

---

# PART 2 — Event ingestion API

## 2.1 The pipeline

```mermaid
flowchart TD
    A["DEVICE<br/>outbox PENDING, priority-ordered"] --> B["BATCH<br/>header + N events, size-bounded"]
    B --> C["REST POST /v1/events<br/>or gateway forward"]
    C --> D["AUTHENTICATION<br/>bearer token, plus MAC if forwarded"]
    D --> E["PER-EVENT VALIDATION<br/>schema, seq, actor, cell, type"]
    E --> F["DEDUPLICATION<br/>ON CONFLICT device_id, seq"]
    F --> G["APPEND<br/>assign server_seq + t_srv"]
    G --> H["FOLD<br/>update read models"]
    G --> I["MQTT PUBLISH<br/>post-commit only"]
    G --> J["RESPONSE<br/>accepted / rejected sets"]
    J --> K["DEVICE<br/>mark ACKED, or REJECTED"]
```

## 2.2 Request

```
POST /v1/events
Authorization: Bearer <device or gateway token>
```

| Field | Meaning |
|---|---|
| `batch_id` | Client-generated, for diagnostics and gateway dedup. **Not an identity** — batches are not entities (DM-14) |
| `origin_device_id` | The device that authored these events |
| `mac` | Required **only** when forwarded by a gateway (Part 7). Absent on direct TLS uploads |
| `events[]` | Canonical events per `08` Part 1, without server-assigned fields |

## 2.3 Response — partial acceptance is mandatory

**Status `200` even when some events are rejected.** Rejecting a whole batch because one event is bad would block the outbox permanently: the bad event can never succeed, so the good ones behind it would never be sent. **AP-04.**

```json
{
  "accepted":  [ { "device_id": 17, "seq": 4021, "server_seq": 1201, "was_duplicate": false } ],
  "rejected":  [ { "device_id": 17, "seq": 4025, "code": "UNKNOWN_CELL", "retryable": false, "message": "cell_index 99999 not in grid" } ],
  "server_seq_high": 1203
}
```

**Duplicates appear in `accepted` with `was_duplicate: true`**, never in `rejected`. This is AD-28 and `08` Part 5: a repeat is *accepted*, because the client's correct action is identical either way — mark it `ACKED`. The flag exists for diagnostics only. **AP-05.**

## 2.4 The eight required cases

| Case | Behaviour |
|---|---|
| **One event valid, another invalid** | `200`. Valid → `accepted`; invalid → `rejected` with a reason. The batch is never rejected as a unit (AP-04) |
| **Same event uploaded twice** | Both times in `accepted`; second carries `was_duplicate: true` and the **same `server_seq`** as the first. No second row, no second MQTT publish |
| **Older event arrives after a newer one** | Accepted normally and given a **higher `server_seq`** than the newer one. This is AL-05, and it is correct behaviour — `server_seq` is acceptance order, not occurrence order (`08` Part 8). Folds use `server_seq`; the audit view exposes `t_dev` so a human sees the inversion |
| **Partially duplicated batch** | Each event de-duplicated independently. Mixed `was_duplicate` flags in one response are normal |
| **Device `seq` gaps** | **Accepted.** Gaps are legal (DM-13) — a rolled-back local transaction consumes a `seq`. The server does **not** wait for or demand missing `seq` values. It records the gap in diagnostics only |
| **Device retries after timeout** | Every event de-duplicated; response identical to the first. Costs one redundant transmission, loses nothing |
| **Server commits but the response is lost** | The device keeps the events `PENDING` and re-sends. The re-send is de-duplicated and returns the original `server_seq`. **The only cost is one redundant batch.** This is the case that makes idempotency non-negotiable |
| **Two devices create the same logical action** | **Both stored.** Different `(device_id, seq)` = different facts. This is the D-01b duplicate-search scenario, not an error (DM-15) |

## 2.5 Why a client cannot accidentally create duplicate domain events

Three independent guarantees, any one of which suffices:

1. **Identity is allocated at creation, not at send.** A retry transmits the *same* `(device_id, seq)`, never a new one. The client has no code path that mints a fresh identity for an existing event (`08` Part 6).
2. **The primary key rejects the second row.** `ON CONFLICT (device_id, seq) DO NOTHING`.
3. **`seq` comes from a persisted counter inside the write transaction.** A crash cannot replay an allocation (AD-10).

**A "duplicate domain event" is only creatable by a human doing the action twice** — and that is a real-world fact the system must record, not a bug to suppress.

## 2.6 Validation rules (each maps to a rejection code)

| Rule | Code | Retryable |
|---|---|---|
| Known event type and schema version | `UNKNOWN_TYPE` / `UNSUPPORTED_SCHEMA` | No |
| Payload matches the type's required fields | `INVALID_PAYLOAD` | No |
| `cell_index` within the incident's grid | `UNKNOWN_CELL` | No |
| `seq` strictly greater than the device's highest accepted `seq` | `SEQ_NOT_MONOTONIC` | No |
| Actor's `team_id`/`agency_id` match the device's enrolment | `ATTRIBUTION_MISMATCH` | No |
| `incident_id` matches the device's incident | `WRONG_INCIDENT` | No |
| Event type permitted for the caller's role | `TYPE_NOT_PERMITTED` | No |
| Database or dependency unavailable | `UNAVAILABLE` | **Yes** |

### 2.6.1 Retryability is the server's verdict, not the client's inference

**The client acts on the `retryable` boolean and never interprets the `code` string.** Codes are diagnostics. This means a new rejection code can be introduced server-side without any client change, and a client can never mis-classify a code it has not seen. If `retryable` is absent from a malformed response, the client treats it as **`true`** — failing safe toward retention — and raises a diagnostic. **AP-21.**

### 2.6.2 CRITICAL events are never permanently rejected for reference errors

Applying AP-14 naively creates a serious failure mode: a `SURVIVOR_REPORTED` event with a mistyped `cell_index` would be permanently rejected, and a real survivor's location would never reach the commander. That is precisely the harm this system exists to prevent (PS-B9, P-4).

**Rule:** rejection codes are partitioned by severity, and the partition interacts with priority.

| Code class | Codes | Applies to |
|---|---|---|
| **Structural** — the event cannot be parsed or stored meaningfully | `UNKNOWN_TYPE`, `INVALID_PAYLOAD`, `UNSUPPORTED_SCHEMA` | **All types**, including CRITICAL |
| **Security / attribution** — accepting would corrupt the audit record | `ATTRIBUTION_MISMATCH`, `WRONG_INCIDENT`, `TYPE_NOT_PERMITTED`, `SEQ_NOT_MONOTONIC` | **All types**, including CRITICAL |
| **Reference** — the event is well-formed but points at something unknown | `UNKNOWN_CELL` | **ROUTINE types only.** For `SURVIVOR_REPORTED` the event is **accepted** and the unresolvable reference is flagged in the read model for commander attention |

The accepted-with-flag path needs **no event schema change** — the flag lives in the `survivor_report` read model, which is derived and rebuildable (DM-30). **AP-20.**

Only `UNAVAILABLE` is retryable. Every other verdict is permanent → `REJECTED` (§2.7).

---

## 2.7 The `REJECTED` contract

### 2.7.1 Entry
A row enters `REJECTED` **only** when a `200` ingestion response lists it in `rejected` with `retryable: false`. Every other outcome — transport failure, timeout, lost response, `500`, `503`, or `retryable: true` — returns the row to `PENDING` with backoff.

### 2.7.2 What is retained
| Retained | Where | Forever? |
|---|---|---|
| The domain event | Local event log | **Yes — permanently, and auditable** |
| The rejection reason | Outbox row (`rejected_code`, `rejected_message`, `rejected_at`, `rejected_batch_ref`) | **Yes — `REJECTED` rows are never pruned** (DM-40) |
| Server-side record | Structured log + `/v1/diag/sync` counters | For the incident |

**The event is never deleted because it was rejected.** A rejected event appears in the device's local history exactly as any other, distinguished only by its delivery state.

### 2.7.3 Non-blocking, proven at two levels
| Level | Mechanism |
|---|---|
| **Within a batch** | Partial acceptance (AP-04) — valid events in the same batch are accepted and `ACKED` in the same response that rejects the bad one |
| **Across the queue** | Batching selects `PENDING` rows only. A `REJECTED` row is not `PENDING`, so it is skipped forever and consumes no transmission capacity |

### 2.7.4 Diagnostics
The field app surfaces `REJECTED` rows in a diagnostics view: event type, `t_dev`, `rejected_code`, `rejected_message`, and the `batch_id` for correlation with server logs. The count appears in the sync header alongside queue depth, so a responder can see that something was refused rather than silently vanishing.

### 2.7.5 No automatic exit
There is **no automatic transition out of `REJECTED`** at Level 1. Manual re-queue is a Level-2 diagnostic affordance and is deliberately not built. If it were ever added, re-sending is safe by construction — the event's `(device_id, seq)` is unchanged, so the server would de-duplicate or re-reject deterministically.

---

# PART 3 — Sync contract

## 3.1 The question the client asks

> *"What authoritative changes have occurred since `server_seq` = X?"*

```
GET /v1/events?since=1201&limit=200
```

## 3.2 The cursor is `server_seq` — a plain integer

| Property | Consequence |
|---|---|
| Monotonic and server-assigned | Total order, no ambiguity |
| **Never expires** | No server-side cursor state, no expiry handling, no resumption failures |
| Survives restart trivially | It is one integer in the local store |
| Human-readable | Diagnostics and demo evidence are legible |

**Opaque cursor tokens were rejected**: they require server-side state with expiry, and an expired cursor forces a full re-snapshot — the exact failure the design is trying to avoid. **AP-06.**

## 3.3 The four ordering concepts, kept distinct

| Concept | Scope | Used by the sync protocol? |
|---|---|---|
| **device `seq`** | Device-local counter | **No.** It is identity and per-device order. The server never uses it for global ordering, and it is **never a cursor** |
| **`server_seq`** | Global acceptance order | **Yes — it is the cursor** |
| **event timestamp** (`t_dev`, `t_srv`) | Display and audit | **No.** Never used to select or order sync results |
| **cursor** | The client's `last_applied_server_seq` | **It *is* `server_seq`** — not a separate concept, not an opaque token |

## 3.4 Response

```json
{
  "events": [],
  "next_since": 1401,
  "has_more": true,
  "current_server_seq": 1560
}
```

(`events` shown empty here to isolate the envelope — see 11.6 for a populated response. Events are canonical per `08`, ascending by `server_seq`.)

| Field | Meaning |
|---|---|
| `next_since` | Cursor for the next page. **The client advances only after successfully applying the page** |
| `has_more` | More pages exist right now |
| `current_server_seq` | The server's high-water mark, so the client can show sync progress |

## 3.5 Paging and limits

| Limit | Value | Reason |
|---|---|---|
| Default page size | 200 events | ~40 KB, comfortable on any link |
| Maximum page size | 1,000 events | Cap on request cost |
| Maximum response bytes | 256 KB | **Whichever cap is reached first wins** — a page may return fewer than `limit` events |
| Ordering | Strictly ascending `server_seq` | Deterministic and resumable |
| Retry | Idempotent — the same `since` always yields the same page for a given store state |

## 3.6 Initial vs incremental synchronisation

| | Mechanism | Why |
|---|---|---|
| **Initial** | `GET /snapshot` → read models + `current_server_seq` | Replaying tens of thousands of events to a new client is wasteful when the server already holds the fold. **AP-07** |
| **Incremental** | `GET /events?since=…`, repeated until `has_more = false` | Delta only; full state is never re-sent (FR-802) |
| **Long gap** | If `current_server_seq − last_applied > 2000`, re-snapshot instead of paging | Bounded recovery cost |

**A client's cursor is never invalid**, so there is no "cursor expired" path to handle. The only decision is snapshot-vs-delta, and it is a size heuristic, not an error.

---

# PART 4 — MQTT contract

**MQTT is notification-only and is never the source of truth** (AD-15). This section makes that structural, not merely stated.

## 4.1 Broker and topics

| | |
|---|---|
| **Broker** | Eclipse Mosquitto (T-09), TCP listener for the backend, **WebSocket listener** for the dashboard |
| **Topic** | `rescuenet/v1/incident/{incident_id}/notify` |
| **Hierarchy rationale** | One topic at Level 1 — the dashboard wants everything. The path leaves room for `/notify/{type}` subtopics as a **Level-2** refinement, at zero Level-1 cost. **AP-08** |

## 4.2 QoS, retain, and why

| Setting | Value | Reason |
|---|---|---|
| **QoS** | **1** (at-least-once) | Reduces avoidable REST delta pulls. **Correctness never depends on it** — the gap rule is the backstop. QoS 2 was rejected: duplicates are harmless (notifications are idempotent hints) and QoS 2 costs extra round trips |
| **Retain** | **`false`, always and without exception** | A retained message would present itself as current state to a new subscriber, which is precisely the "MQTT as source of truth" failure AD-15 forbids. New subscribers get state from `GET /snapshot`, never from the broker. **AP-09** |
| **Clean session** | `true` | The broker holds no client state; recovery is REST's job |
| **LWT** | Not used at Level 1 | Nothing depends on presence |

## 4.3 Message structure

```json
{
  "v": 1,
  "incident_id": 9,
  "server_seq": 1201,
  "kind": "EVENT_COMMITTED",
  "event": {
    "device_id": 17, "seq": 4021,
    "type": "CELL_STATUS_REPORTED",
    "entity_type": "CELL", "entity_id": 214,
    "team_id": 3, "agency_id": 1,
    "payload": { "cell_index": 214, "status": "SEARCHED" },
    "t_srv": "2026-08-22T11:31:02Z"
  },
  "derived": {
    "duplicate_search": true,
    "coverage": { "total": 5000, "searched": 1287, "in_progress": 40,
                  "needs_research": 3, "unsearched": 3670 }
  }
}
```

~300 bytes — the `coverage` block is present **only** on events that change `cell_state` (§5.3). Every field is either the event identity, what the dashboard renders, or the gap-detection cursor.

## 4.4 Authentication and authorization

Three concerns that are routinely conflated, kept separate here:

| Concern | Level-1 mechanism |
|---|---|
| **Authentication** — *who is this client?* | Mosquitto's native **static password file**, holding exactly two accounts: `rescuenet-publisher` and `rescuenet-dashboard` |
| **Authorization** — *what may it do?* | Mosquitto's native **static ACL file**, granting the publisher write-only and the dashboard read-only on the incident topic |
| **Credential provisioning** — *how does a client obtain its credential?* | **Configured at deployment time**, not dynamically issued. Both accounts are created in the Compose configuration and do not change during an incident |

| Client | Account | Broker ACL |
|---|---|---|
| Backend publisher | `rescuenet-publisher` | **Publish only** on `rescuenet/v1/incident/+/notify` |
| Dashboard subscriber | `rescuenet-dashboard` | **Subscribe only** — no publish permission whatsoever |
| Field app | **No MQTT credential at Level 1** (AD-19) | — |

**Credentials are provisioned by configuration, not issued per session.** The earlier draft stated the dashboard credential was "issued with the session"; that is **not feasible with Mosquitto's static password file** and would have required an authentication plugin, contradicting the "smallest stack" rationale behind T-09. **The security property is unchanged** — a static, subscribe-only account satisfies AP-10 exactly as a per-session one would. **AP-23.**

**Delivery to the browser:** the dashboard receives the static credential in the `POST /v1/auth/session` response, **after** commander authentication, so it is not present in the unauthenticated JavaScript bundle. This is delivery of a configured credential, **not** issuance of a new one — the same account is returned to every authenticated commander.

**The dashboard's subscribe-only ACL is the structural enforcement of AD-15.** Even a compromised or buggy dashboard cannot write to a topic, so MQTT cannot become a write path by accident. **AP-10.**

**Prototype limits, stated plainly:** a shared static credential cannot be revoked per user, and anyone who authenticates as commander obtains it. It is a subscribe-only account on a notification topic that carries no authoritative state, so the blast radius is reading notifications. Per-user MQTT identity is Level 2.

## 4.5 The gap rule — exact

Client holds `last_applied`. A message arrives with `server_seq = Y`:

| Condition | Action |
|---|---|
| `Y == last_applied + 1` | **Apply directly.** No REST call |
| `Y <= last_applied` | **Ignore.** Duplicate or out-of-order redelivery; already applied. Idempotent |
| `Y > last_applied + 1` | **Gap.** `GET /v1/events?since=last_applied`, apply the page(s) in order, then set `last_applied = next_since`. The triggering message needs no special handling — the delta contains it |
| `Y - last_applied > 2000` | **Re-snapshot** instead of paging (§3.6) |

**Loss costs latency, never correctness.** A subscriber that receives nothing at all still converges by REST alone.

## 4.6 Client behaviour and reconnection

| Situation | Behaviour |
|---|---|
| Startup | `GET /snapshot` → set `last_applied` → **then** subscribe. Never subscribe first: messages arriving before the snapshot would create a phantom gap |
| Broker disconnect | Show **"live updates offline — last refreshed HH:MM"**. Do **not** show data as fresh (`06` §11, FR-705) |
| Reconnect | Subscribe, then **immediately** `GET /events?since=last_applied` without waiting for a message to reveal a gap. Anything missed while disconnected is repaired at once |
| Broker permanently unavailable | Dashboard degrades to REST polling of `/events?since=…`. **Fully functional, higher latency** |

## 4.7 No commands over MQTT at Level 1

MQTT carries **notifications only**. Assignments, revocations and every other instruction travel over REST (endpoints 10 and 11). A broker-delivered command would have no durable record, no acknowledgement contract and no audit trail. **AP-11.**

---

# PART 5 — MQTT message types

## 5.1 One type at Level 1

| Kind | Purpose | Why it exists |
|---|---|---|
| `EVENT_COMMITTED` | An event was durably committed at `server_seq` | The dashboard needs to render the change without waiting for a poll cycle |

**That is the complete list.** Two candidates were considered and rejected:

| Rejected | Why |
|---|---|
| `DUPLICATE_SEARCH_FLAGGED` as a separate message | The dashboard would have to correlate it with the event that caused it, and the duplicate fold would exist in two places — server and client — free to diverge. Instead the flag rides in `derived` on the event that triggered it: **one fold, one source, no correlation.** **AP-12** |
| `PROJECTION_REBUILT` | Projections are a deterministic fold (DM-30), so a rebuild produces identical results. No client action is warranted, so no notification is warranted |

## 5.2 Why the payload carries the event rather than only a pointer

`08` and the instruction both prefer small notifications. This message carries a compact event body anyway, for a **concrete, measurable reason**:

| Option | Cost per change |
|---|---|
| Pointer only (`server_seq` + "something changed") | ~60 B MQTT **+ a full REST round trip** — the live path's latency becomes REST's latency, defeating the reason MQTT exists |
| **Compact event body (chosen)** | ~230 B MQTT, **no REST call** in the common case |

At 200 changes/hour the difference is ~34 KB — trivial on the command-post link (D-01: the dashboard is online) — against removing a round trip from every single update.

**Three constraints keep this from becoming "MQTT as truth":**
1. The body is a **projection of a committed event**, published only after the durable write.
2. It carries `server_seq`, so it is always verifiable and always recoverable by REST.
3. It carries **only what the dashboard renders** — not the full authoritative row (no `schema_version`, no `received_via`, no `t_dev`). A client that needed the authoritative record must fetch it. **AP-13.**

---

## 5.3 `CoverageMetrics` — ownership and update rule

Resolving audit finding F-04. **One rule, one owner, no second source of truth.**

| Question | Answer |
|---|---|
| **What source data produces it?** | The `cell_state` read model, plus `rows × cols` from `GRID_GENERATED` for the total. Nothing else |
| **Derived from the event log or read model?** | **Derived from `cell_state`, which is itself a fold of `CELL_STATUS_REPORTED` and assignment events.** It is therefore a second-order projection of the event log — never an independent record |
| **Who owns the fold?** | **The server, exclusively.** The dashboard never computes coverage from its own applied events |
| **When is it recalculated?** | Incrementally, in the same post-commit step that updates `cell_state`. A committed event that does not change `cell_state` does not change coverage |
| **How does it change after delta events?** | It does not change *at the client*. The server recomputes and republishes; the client only ever displays the last value it received |
| **Persisted or recomputable?** | **Both.** Persisted as one row in `coverage_metrics` for fast snapshot reads, and fully recomputable from the event log like every other projection (DM-30) |
| **What happens after synchronisation?** | Recomputed as part of the normal projection update. After a full projection rebuild the values are identical, because the fold is deterministic |

**How the client obtains it — two paths, both server-authored:**

1. **Initial load:** included in `GET /snapshot` with `scope=command`.
2. **Live:** carried in the MQTT `derived.coverage` block, **on events that change `cell_state` only**.
3. **After a gap:** the REST delta repairs `cell_state`, and the **next** `derived.coverage` block carries the corrected totals. If a client needs metrics immediately after a large gap, it re-snapshots (§3.6) rather than computing them.

**Why the server owns it.** This mirrors AP-12 exactly. If the dashboard recomputed coverage from its own applied events, the same fold would exist in two places, free to diverge whenever the client's applied set differed from the server's — which is precisely the condition a gap creates. One fold, one source. **AP-24.**

**Cost:** ~60 bytes on events that change `cell_state`. On the command-post link (D-01: online) this is immaterial, and it removes an entire class of divergence.

---

# PART 6 — SMS contract

## 6.1 Evidence wording (binding, from `05` and `04` §4.0.1)

- The hardware test established that **the generated GSM-7 payloads were transmitted unaltered between the two tested handset/SIM routes, in both directions**.
- **Payloads up to 459 characters arrived intact and passed exact verification.** Exact SMS **segment counts were not observed**.
- **Carrier identities were not recorded.**
- **Binary SMS does not work on the tested route, and is not used.** SP-01b-A Q1 (2026-08-24): 10 attempts A→B, **0 delivered**, **10/10 `GENERIC_FAILURE`** from `SmsManager.sendDataMessage`. The B→A binary leg was **not captured** and is **not claimed**. **D-02a is closed in favour of GSM-7 text** (`05` §1.2a, `07` T-23).
- **Programmatic Android SMS is now validated for the text path.** SP-01b-A Q2 on two handsets and two carriers (vivo V2151/Jio, OPPO CPH2859/Airtel): **A→B 10/10 delivered**, median **1.6 s**, max **6.4 s**, `segments=1`; **B→A 8/10** — two lost, three held and burst-delivered, max ~63 s. **B→A is below the ≥9/10 pass bar and that shortfall is not glossed.** The spike's nominal "120 chars" produced **115–116 actual payload characters**.
- **The throttle threshold is NOT known.** Q3 sent 40 rapid messages on Airtel: 35 observed delivered, every captured result `OK`, **no confirmation dialog**. Record only as *throttle not observed through 40 sends; threshold remains unlocated.* **No threshold may be inferred.**
- **Exact SMS segment counts were still not observed carrier-side.** `segments=1` is the receiving handset's report at ~116 characters. **TL-10 stands.**

## 6.2 The pipeline

```mermaid
flowchart LR
    DE["DOMAIN EVENT<br/>08 Part 1"] --> WE["WIRE EVENT<br/>bit-packed, ids narrowed"]
    WE --> BA["BATCH<br/>header + N wire events"]
    BA --> CO["CODEC<br/>framing + MAC + alphabet"]
    CO --> SM["SMS PAYLOAD<br/>one or more messages"]
```

## 6.3 The contract

| Aspect | Level-1 contract |
|---|---|
| **Maximum payload** | Declared by the transport as `max_batch_bytes` = **120 B** — the GSM-7 text path (validated arithmetic, `04` §3.1). **The 134 B binary figure is withdrawn**: D-02a selected text after SP-01b-A Q1 failed, so no binary budget applies |
| **Encoding** | ✅ **FINAL — GSM-7 base64url. D-02a / T-23 closed 2026-08-24.** Binary / port-addressed is **rejected on measured evidence**, not merely unvalidated (§6.1) |
| **Framing** | `batch_id` 16 b · `part_index` 4 b · `part_total` 4 b · `origin_device_id` 12 b · `mac` 32 b = **68 b**. Widths ratified 2026-08-24 (§6.6) |
| **Batch structure** | Nine header fields, **89 b zero-padded to 12 B** — widths ratified 2026-08-24 (§6.6). The historical "7 B / 53-bit" header is **superseded**: it predates DM-38 and omits `base_seq` |
| **Sequence representation** | `base_seq` 20 b in the header; **`seq_delta` 6 b unsigned** per event (DM-38). Time: `base_t` 20 b unsigned seconds since incident start; **`t_delta` 12 b unsigned seconds** per event (§6.6) |
| **Integrity** | **`mac` = first 4 bytes of `HMAC-SHA256(hmac_secret, header ‖ packed_events)`.** Framing is **not** covered; the `mac` field itself is excluded from the input (§6.6). **Integrity and authenticity only — no confidentiality** (AD-24) |
| **Duplicate handling** | Backend dedup by `(device_id, seq)`. The gateway may additionally suppress a repeated `batch_id` to save uplink — an optimisation, never a correctness mechanism |
| **Direction** | **Uplink is primary. Downlink is acknowledgement only** (D-06) |
| **Acknowledgement** | **3-byte unauthenticated ACK**: `ack_proto` 4 b + `highest_contiguous_seq` 20 b (§6.6). Monotonic — a lower or equal value is a no-op |
| **Retry** | Base 60 s, cap 30 min, ±20% jitter — deliberately slow because SMS is METERED and the gateway downlink is throttle-constrained (TL-4) |
| **Priority** | Only `CRITICAL` events use SMS while internet is absent (AD-09). **`POSITION_REPORTED` is NEVER sent over SMS** — absolute, ratified 2026-08-24 (M8-7); `08` Part 9 corrected to match |

## 6.4 "Highest contiguous" acknowledgement — the trade, stated

If `seq` 4021, 4022 and 4024 are accepted, the ack carries **4022**. The device re-sends 4024, which is de-duplicated server-side.

**Cost:** one redundant transmission. **Saving:** the ack is a fixed ~4 bytes instead of a variable-length list. On a downlink that is throttle-constrained (TL-4), fixed and small wins. **AP-15.**

## 6.5 What the backend must never contain

The FastAPI backend contains **no SMS logic**. It receives decoded, canonical events over `POST /v1/events` from the gateway, exactly as it receives them from a direct device. Its only SMS-related awareness is the `received_via` provenance field, which is metadata, not behaviour. **AD-07 holds end to end.**

## 6.6 Ratified SMS wire format (2026-08-24) — **DM-57**

Every width below is **Final**. Prior to this section the SMS wire format was
under-specified: the header size contradicted DM-38, `evt_type` was still sized at the
superseded 3 bits in `04` §3.1, and `seq_delta`, `t_delta`, the framing widths, the MAC
coverage and the ACK layout had no values at all. Decisions **M8-1 … M8-12**.

### 6.6.1 Batch header — 9 fields, 89 bits, zero-padded to **12 B**

| # | Field | Width | Semantics |
|---|---|---|---|
| 1 | `proto_version` | 4 b | Wire-format version, independent of `schema_version` (DM-34) |
| 2 | `device_id` | 12 b | Authoring device (Final, `08` §1.1) |
| 3 | `team_id` | 8 b | Point-in-time attribution |
| 4 | `agency_id` | 4 b | Point-in-time attribution |
| 5 | `incident_id` | 12 b | Scope |
| 6 | `schema_version` | 4 b | Domain schema version |
| 7 | `base_seq` | 20 b | DM-38; per-event `seq` = `base_seq + seq_delta` |
| 8 | `base_t` | 20 b unsigned | **Seconds since incident start** (range 12.1 days) |
| 9 | `event_count` | 5 b | 1–31 events |

**The historical "7 B / 53-bit" header is superseded.** It came from `04` §3.1's SP-01a
arithmetic, which predates **DM-38** and contains no `base_seq`, `incident_id` or
`schema_version`. It is retained as historical evidence and must not be used as the wire size.

### 6.6.2 Event layouts — **SCOPE A**, the four SMS-eligible uplink types

Common prefix on every event: `evt_type` **4 b** (DM-01 Final; codes per `08` §14.1) ·
`seq_delta` **6 b unsigned** · `t_delta` **12 b unsigned seconds** relative to `base_t`.

| Type | Field order after the common prefix | Widths | Total |
|---|---|---|---|
| `CELL_STATUS_REPORTED` (7) | `cell_index`, `status`, `responder_id` | 13, 3, 10 | **48 b** |
| `RESOURCE_DELTA_REPORTED` (9) | `item_id`, `qty_delta` **(signed)**, `responder_id` | 8, 8, 10 | **48 b** |
| `TEAM_STATUS_REPORTED` (11) | `team_status`, `responder_id` | 3, 10 | **35 b** |
| `SURVIVOR_REPORTED` (8) | `presence_mask`, `cell_index`, `person_count`, `survivor_status`, [`triage`], [`rel_lat`], [`rel_lon`], `responder_id` | 3, 13, 6, 3, [3], [16], [16], 10 | **57 b min · 92 b max** |

`presence_mask` is 3 bits, one per optional field in the order `triage`, `rel_lat`, `rel_lon`.
**Only fields whose bit is set are encoded.** No sentinel value is ever substituted — a
sentinel could collide with a valid value and would break the bijection (DM-25).

All fields unsigned except `qty_delta`, `rel_lat`, `rel_lon`, which are **two's-complement
signed**. Units: `rel_lat`/`rel_lon` metres from incident origin (±32 km at 1 m); `t_delta`
seconds; `qty_delta` catalogue units.

**The seven non-SMS types have no SMS layout and must not be given one.**
`INCIDENT_DECLARED`, `GRID_GENERATED`, `TEAM_REGISTERED`, `DEVICE_ENROLLED`,
`ASSIGNMENT_ISSUED`, `ASSIGNMENT_REVOKED` and `POSITION_REPORTED` travel the JSON/HTTPS path,
which already carries all eleven canonical types losslessly. **No variable-length field
therefore exists in the SMS codec** (M8-6, M8-8).

### 6.6.3 Delta rules

Events are packed in **ascending `seq`**. If `seq − base_seq > 63`, or the event's time offset
from `base_t` exceeds 4095 s, the event **does not fit this batch**. It is **not truncated and
not reordered**: it stays `PENDING` and is carried by a later batch (`08` §10.1 rule 2).

### 6.6.4 Framing — 68 bits, outside the MAC

| # | Field | Width | Semantics |
|---|---|---|---|
| 1 | `batch_id` | 16 b | Diagnostics and gateway dedup. Not an identity (DM-14) |
| 2 | `part_index` | 4 b | **Always 1 at Level 1** |
| 3 | `part_total` | 4 b | **Always 1 at Level 1** |
| 4 | `origin_device_id` | 12 b | The authoring device, for gateway relay (AP-16) |
| 5 | `mac` | 32 b | §6.6.5 |

Level 1 is **single-segment only**; `part_index`/`part_total` are retained for protocol
compatibility and for M9, which owns reassembly (M8-9, M8-12).

### 6.6.5 MAC — exact coverage

```
mac = HMAC-SHA256(hmac_secret, header ‖ packed_events)[0:4]
```

The authenticated byte sequence is the header (89 b) followed immediately by the packed event
bits, MSB-first, zero-padded to a byte boundary before hashing. **Framing is not covered**,
and the `mac` field itself is excluded from its own input.

This is exactly what the contract requires and no more: **DM-23** requires the header be
covered ("header loss invalidates the batch — MAC covers it"), and **AP-16** requires
authorship be covered, which lives in the header attribution fields plus per-event
`responder_id`. **TR-10 requires rejection of a *tampered payload*, not of altered framing** —
framing authentication is not a documented requirement, and `batch_id`/`part_index`/
`part_total` are reassembly metadata belonging to **M9** (M8-10).

### 6.6.6 ACK — 3 bytes, unauthenticated

| # | Field | Width | Semantics |
|---|---|---|---|
| 1 | `ack_proto` | 4 b | ACK format version |
| 2 | `highest_contiguous_seq` | 20 b | §6.4 semantics |

**24 b = 3 B.** No `device_id`: the ACK is delivered to the device's own SMS address, so
identity would consume wire bytes to restate what the channel already establishes. **No ACK
MAC**: no document requires downlink authentication, and a forged ACK can only cause a
redundant re-send, which the server de-duplicates by `(device_id, seq)`.

**ACKs are monotonic.** A value lower than or equal to the current watermark is a **no-op**;
only a strictly higher contiguous sequence advances acknowledgement. Replays and duplicates
are therefore harmless (M8-11).

### 6.6.7 Transport representation and budget

| | |
|---|---|
| Packed budget | **120 B**, and this is the **complete** blob: framing ‖ header ‖ events |
| Encoding | base64url (RFC 4648 §5), **no padding** |
| Character cost | 120 B → **exactly 160 characters** (120 mod 3 = 0) |
| GSM-7 | All 64 base64url characters are in the GSM 03.38 default alphabet, so each costs **one septet**, with no escape sequences |
| Segment | 160 septets = **exactly one single-segment SMS**, at the limit with zero headroom |
| Segmentation | **Single-segment only at Level 1.** Concatenation is not implemented in M8 |

**Fixed overhead is framing 68 b + header 89 b = 157 b**, leaving **803 bits for events**.

| Type | Bits | Max per 120 B batch |
|---|---|---|
| `TEAM_STATUS_REPORTED` | 35 | **22** |
| `CELL_STATUS_REPORTED` | 48 | **16** |
| `RESOURCE_DELTA_REPORTED` | 48 | **16** |
| `SURVIVOR_REPORTED` (no optionals) | 57 | **14** |
| `SURVIVOR_REPORTED` (all optionals) | 92 | **8** |

22 events is within `event_count`'s 5-bit range (31) and within `seq_delta`'s 63-step span.
**Padding occurs only once, at the end of the whole blob.** Mixed batches pack greedily in
priority order (`CRITICAL` first, `06` §5.3); an event that does not fit is left `PENDING`.

---

# PART 7 — Gateway contract

**The gateway is the same APK in gateway mode (T-22).** There is no second application.

## 7.1 Responsibilities

| Stage | Behaviour |
|---|---|
| **Mode** | Selected at enrolment (`mode: "GATEWAY"`). The backend issues a token with the `GATEWAY` role |
| **Receiving** | Registers for the SMS broadcast; buffers parts by `batch_id` |
| **Reassembly** | Waits for all `part_total` parts. Incomplete batches **expire and are discarded** — the origin device retries the whole batch, which is safe by idempotency |
| **Decoding** | Codec produces canonical domain events |
| **Validation** | **Structural only** — framing intact, MAC present, parts complete. **The gateway performs no domain validation**; that is the backend's job (Part 2.6) |
| **Duplicate detection** | Suppresses a `batch_id` already forwarded, as an uplink optimisation. Correctness still rests on backend dedup |
| **Forwarding** | `POST /v1/events` with the gateway's own token, `origin_device_id` set to the **authoring** device, and the original `mac` passed through |
| **Local persistence** | Decoded batches persist in a forward-queue before any HTTP attempt. **A crash between receiving an SMS and forwarding it loses nothing** |
| **No internet** | Batches accumulate in the forward-queue and are sent when connectivity returns. The gateway is itself store-and-forward |
| **Batching** | Multiple SMS batches from multiple devices may be coalesced into one HTTPS request — the internet link is not the constrained one |
| **Diagnostics** | SMS received, batches reassembled, MAC failures, forward-queue depth, last successful forward |

## 7.2 The gateway is a relay, not an author — and the API enforces it

**The gateway never rewrites attribution.** Forwarded events keep their original `device_id`, `seq`, `responder_id`, `team_id`, `agency_id` and `t_dev`. If the gateway re-authored events, every field observation would be attributed to the gateway handset and PS-B7 would be unanswerable.

This creates an authorization requirement that ordinary uploads do not have:

| Caller role | Rule |
|---|---|
| `FIELD` | Every event's `device_id` **must equal** the authenticated device. No MAC required — TLS plus bearer token is the authentication |
| `GATEWAY` | Events **may** carry a different `device_id`, **but the batch MUST carry a valid `mac`** computed with the *originating* device's secret |

**This is the concrete reason the per-device HMAC secret exists.** The gateway's own token authenticates *the relay*; the MAC authenticates *the author*. Without it, a compromised gateway could fabricate events attributed to any team. **AP-16.**

A batch failing MAC verification is rejected `401` and **surfaced in diagnostics** — never silently dropped.

---

# PART 8 — Authentication

## 8.1 The model

| Identity | Represented by | Issued at | Lifetime |
|---|---|---|---|
| **User (responder)** | `responder_id` on every event | Enrolment | Incident |
| **Agency / team** | `agency_id`, `team_id` on every event | Enrolment | Point-in-time, never rewritten (DM-04) |
| **Device** | `device_id` + opaque bearer token | Enrolment | Long-lived, revocable |
| **Device authenticity over SMS** | `hmac_secret` | Enrolment, over TLS, **once** | Long-lived |
| **Commander** | Session token | `POST /v1/auth/session` | Expires; re-login |

## 8.2 Deliberate simplifications

| Question | Level-1 answer |
|---|---|
| **Token refresh?** | **No.** Device tokens are long-lived and revocable server-side. A refresh flow would add an endpoint, a failure mode, and an offline edge case — for a prototype whose devices are enrolled once, by hand, for one incident. **AP-17** |
| **Offline behaviour** | The token is cached and **never re-validated locally**. Every field action works with no connectivity (FR-105). Authorisation is enforced at ingestion, not on device |
| **Cached credentials** | Token and `hmac_secret` in Android encrypted storage. `hmac_secret` is never transmitted after enrolment |
| **Revocation** | `device_credential.revoked_at`. Takes effect at the **next contact** — a revoked offline device keeps working until it syncs, and is then rejected. **This is an accepted limitation** (AL-04), not an oversight |
| **Gateway authentication** | Same mechanism, `GATEWAY` role, plus per-batch MAC verification of forwarded events (Part 7.2) |
| **Enterprise identity** | **None.** No OAuth, no OIDC, no directory. `06` §14 already accepts trust-on-first-use |

---

# PART 9 — Error contract

## 9.1 One shape, everywhere

```json
{
  "error": {
    "code": "UNKNOWN_CELL",
    "message": "cell_index 99999 is not within the incident grid",
    "retryable": false,
    "details": { "cell_index": 99999, "grid_cells": 5000 }
  }
}
```

`code` is a stable machine-readable string; `message` is for humans; **`retryable` is the field clients act on.**

## 9.2 Statuses actually used

| Status | When | Client behaviour |
|---|---|---|
| **400** | Malformed request — unparseable JSON, missing required field | **Do not retry.** A defect; surface in diagnostics |
| **401** | Missing/invalid/revoked token, or MAC verification failed | Device: stop, surface "re-enrolment required". Gateway: surface the MAC failure. **Never retry blindly** |
| **403** | Authenticated but not permitted — e.g. a `FIELD` token uploading another device's events | **Do not retry.** Defect or misconfiguration |
| **404** | Unknown incident, team, assignment or join code | **Do not retry** |
| **409** | Grid already generated for this incident (FR-205 immutability) | **Do not retry.** Commander UI explains why |
| **413** | Batch exceeds the maximum request size | **Do not retry as-is.** Split the batch and re-send — the codec already bounds SMS batches, so this indicates an internet-path defect |
| **422** | Semantically invalid but well-formed | **Do not retry.** Per-event rejections inside a `200` are the normal path; a whole-request `422` means the envelope itself is invalid |
| **500** | Unexpected server fault | **Retry with backoff.** Events stay `PENDING` |
| **503** | Database or dependency unavailable | **Retry with backoff.** `Retry-After` honoured when present |

## 9.3 Statuses deliberately not used

| Status | Why not |
|---|---|
| **429** | **No rate limiting at Level 1.** The client population is a handful of enrolled devices with backoff already built in; adding throttling would invent a failure mode the prototype cannot otherwise produce. If the gateway ever bursts, backoff handles it. **AP-18** |
| **201 for `POST /v1/events`** | Ingestion returns `200` with per-event results, because a batch is not a created resource (AP-04) |

**The critical rule:** only `500` and `503` are retryable at the *request* level. Within a `200` response, only `retryable: true` rejections return to `PENDING`; permanent verdicts drive that row to `REJECTED` (§2.7) rather than looping forever on a constrained link.

**Request-level vs event-level failure — do not conflate them.** A `401`/`403`/`413` fails the *whole request*, so **every** event in it stays `PENDING` (the batch was never evaluated). Only a per-event rejection inside a `200` can produce `REJECTED`. **AP-22.**

---

# PART 10 — Bandwidth contract

## 10.1 Per-operation estimates

| Operation | Request | Response | Batched | Paged | Frequency |
|---|---|---|---|---|---|
| `POST /v1/enrol` | ~120 B | ~300 B | — | — | Once per device |
| `POST /v1/auth/session` | ~80 B | ~200 B | — | — | Once per shift |
| `POST /v1/events` (19 events, JSON) | **~4.5 KB** | ~1 KB | ✅ | — | Every sync |
| `POST /v1/events` (19 events, **SMS path**) | **~171 B** | ~4 B ack | ✅ | — | When internet absent |
| `GET /v1/events?since=` (200 events) | ~80 B | **~40 KB** | — | ✅ | Every sync / gap |
| `GET /snapshot` (`scope=field`) | ~80 B | **~20–80 KB** | — | ❌ | Once per session |
| `GET /snapshot` (`scope=command`, worst case) | ~80 B | **~120 KB** | — | ❌ | Once per session |
| `POST /v1/assignments` (3 cells) | ~160 B | ~120 B | — | — | Occasional |
| MQTT notification | — | **~230 B** | — | — | Per committed event |
| `GET /export` | ~80 B | ~50–300 KB | — | — | Rare, human-triggered |

## 10.2 The two most expensive operations

**1 · `GET /snapshot` with `scope=command`.** Worst case — every one of 5,000 cells touched — `cell_state` dominates. Mitigations, all already in the design:

- **Untouched cells are omitted entirely** (DM-12). Early in an incident the snapshot is nearly empty
- **`cell_state` uses positional arrays** `[cell_index, status_code, team_id]`, ~15 B/cell rather than ~45 B as objects
- **Grid is parametric** — cell geometry and labels are never transmitted (DM-10). This alone saves hundreds of kilobytes
- **Grid cell cap** of **8,191** (`MAX_CELLS`), enforced at `POST /grid` with `422`, bounding the worst case (Part 10.5)

**2 · `GET /v1/events` during a long catch-up.** Bounded by page size and the 2,000-event re-snapshot threshold (§3.6).

## 10.5 `MAX_CELLS` — the authoritative Level-1 grid limit

**`MAX_CELLS = 8,191`. This is the single authoritative Level-1 maximum and every document states this number.**

**It is derived, not chosen.** The SMS wire schema encodes `cell_index` in a **13-bit** field (`04` §3.1), addressing 0…8,191 — 8,192 distinct values. `MAX_CELLS` is set to 8,191 so that:

| Property | Value |
|---|---|
| Maximum cells in a Level-1 grid | **8,191** |
| Valid `cell_index` range | **0 … 8,190** |
| `cell_index` 8,191 | **Reserved, never allocated** — a one-value safety margin at the top of the field |
| Wire field width | 13 bits, unchanged (`04` §3.1) |

**Target vs hard maximum — these are different numbers and must not be conflated:**

| Figure | Meaning | Source |
|---|---|---|
| **5,000 cells** | **Evaluation / scale target.** The synthetic-load figure for NFR-09 and SP-03 render testing | `01` NFR-09, AMB-05 |
| **8,191 cells** | **Hard implementation maximum**, enforced by the API and bounded by the wire schema | This section |

**NFR-09 remains satisfied:** 8,191 > 5,000, so the hard maximum comfortably accommodates the target.

**Codec completeness:** every `cell_index` a valid Level-1 grid can produce (0…8,190) is representable in 13 bits with no truncation, wrap or collision. **A test proving this is mandatory** — see `11` TR-11.

**Why not widen to 14 bits:** it would work (+1 bit/event, immaterial per DM-01's precedent) but is unnecessary — 8,191 already exceeds the target by 64%, and not changing the validated wire arithmetic is preferable to re-deriving it.

---

## 10.3 The dashboard must not re-download the incident

**Rule: exactly one snapshot per dashboard session.** Enforced by design, not discipline:

| Mechanism | Effect |
|---|---|
| MQTT carries a compact event body (AP-13) | The common case costs **zero** REST calls |
| Gap → **delta**, not snapshot | Repairs cost ~200 B/event, not a full reload |
| Re-snapshot only above a 2,000-event gap | A bounded, rare, deliberate fallback |
| **No per-entity read endpoints** (AP-01) | There is no endpoint to poll even if someone wanted to |
| Reconnect → delta from `last_applied` | Reconnection never triggers a reload |

## 10.4 Fields omitted when unnecessary

| Context | Omitted |
|---|---|
| SMS batch | `device_id`, `team_id`, `agency_id`, `incident_id`, `schema_version` — in the header once (DM-23); cell labels and geometry — derived (DM-10); `entity_type` — implied by `type` |
| MQTT notification | `schema_version`, `received_via`, `t_dev`, `seq` gaps — not rendered by the dashboard (AP-13) |
| Snapshot | Untouched cells; all derived geometry; all labels |
| Delta | Everything before the cursor |

**Compression: none, anywhere** (AD-20). Bit-packed SMS payloads have little residual redundancy, and the internet path is not the constrained one.

---

# PART 11 — Contract examples

All conform to `08` Part 1.

### 11.1 Login (commander)

```json
{ "incident_id": 9, "password": "spine-demo-2026" }
```
```json
{ "token": "sess_9f2b7c41e0a84d13", "expires_at": "2026-08-22T20:00:00Z",
  "role": "COMMANDER", "incident_id": 9,
  "mqtt": { "url": "wss://host/mqtt", "username": "rescuenet-dashboard",
            "password": "<configured>", "topic": "rescuenet/v1/incident/9/notify" } }
```

### 11.2 Event upload

```json
{
  "batch_id": "b-17-0091",
  "origin_device_id": 17,
  "events": [
    { "device_id": 17, "seq": 4023, "type": "SURVIVOR_REPORTED",
      "entity_type": "SURVIVOR", "entity_id": 0,
      "payload": { "cell_index": 214, "person_count": 2,
                   "survivor_status": "TRAPPED", "triage": "RED",
                   "rel_lat": 1420, "rel_lon": -880 },
      "t_dev": "2026-08-22T10:02:41Z",
      "responder_id": 71, "team_id": 3, "agency_id": 1, "incident_id": 9,
      "schema_version": 1 },
    { "device_id": 17, "seq": 4021, "type": "CELL_STATUS_REPORTED",
      "entity_type": "CELL", "entity_id": 214,
      "payload": { "cell_index": 214, "status": "SEARCHED" },
      "t_dev": "2026-08-22T10:00:14Z",
      "responder_id": 71, "team_id": 3, "agency_id": 1, "incident_id": 9,
      "schema_version": 1 }
  ]
}
```

`SURVIVOR_REPORTED` is packed first — it is the only `CRITICAL` type (D-04, `08` Part 2.2).

### 11.3 Duplicate event upload — same batch re-sent after a lost response

Byte-identical request to 11.2. The client re-sends because the events are still `PENDING`; it does **not** mint new `seq` values.

### 11.4 Event upload response

```json
{
  "accepted": [
    { "device_id": 17, "seq": 4023, "server_seq": 1202, "was_duplicate": false },
    { "device_id": 17, "seq": 4021, "server_seq": 1201, "was_duplicate": false }
  ],
  "rejected": [],
  "server_seq_high": 1203
}
```

Response to the **duplicate** upload in 11.3 — note identical `server_seq` values, and no new rows:

```json
{
  "accepted": [
    { "device_id": 17, "seq": 4023, "server_seq": 1202, "was_duplicate": true },
    { "device_id": 17, "seq": 4021, "server_seq": 1201, "was_duplicate": true }
  ],
  "rejected": [],
  "server_seq_high": 1203
}
```

With one invalid event mixed in — still `200`:

```json
{
  "accepted": [ { "device_id": 17, "seq": 4021, "server_seq": 1201, "was_duplicate": false } ],
  "rejected": [ { "device_id": 17, "seq": 4025, "code": "UNKNOWN_CELL",
                  "retryable": false, "message": "cell_index 99999 not in grid" } ],
  "server_seq_high": 1203
}
```

### 11.5 Delta request

```
GET /v1/events?since=1201&limit=200
Authorization: Bearer sess_9f2b7c41e0a84d13
```

### 11.6 Delta response

```json
{
  "events": [
    { "device_id": 17, "seq": 4023, "type": "SURVIVOR_REPORTED",
      "entity_type": "SURVIVOR", "entity_id": 0,
      "payload": { "cell_index": 214, "person_count": 2,
                   "survivor_status": "TRAPPED", "triage": "RED",
                   "rel_lat": 1420, "rel_lon": -880 },
      "t_dev": "2026-08-22T10:02:41Z",
      "responder_id": 71, "team_id": 3, "agency_id": 1, "incident_id": 9,
      "schema_version": 1, "server_seq": 1202,
      "t_srv": "2026-08-22T11:31:02Z", "received_via": "SMS" }
  ],
  "next_since": 1202,
  "has_more": false,
  "current_server_seq": 1203
}
```

### 11.7 MQTT notification

Topic `rescuenet/v1/incident/9/notify`, QoS 1, retain `false`:

```json
{
  "v": 1, "incident_id": 9, "server_seq": 1201, "kind": "EVENT_COMMITTED",
  "event": {
    "device_id": 17, "seq": 4021, "type": "CELL_STATUS_REPORTED",
    "entity_type": "CELL", "entity_id": 214, "team_id": 3, "agency_id": 1,
    "payload": { "cell_index": 214, "status": "SEARCHED" },
    "t_srv": "2026-08-22T11:31:02Z"
  },
  "derived": {
    "duplicate_search": true,
    "coverage": { "total": 5000, "searched": 1287, "in_progress": 40,
                  "needs_research": 3, "unsearched": 3670 }
  }
}
```

### 11.8 MQTT gap recovery

```
dashboard last_applied = 1199

  MQTT in: server_seq 1200   →  1200 == 1199+1  →  apply, last_applied = 1200
  MQTT in: server_seq 1201   →  LOST — never delivered
  MQTT in: server_seq 1202   →  1202 >  1200+1  →  GAP

  GET /v1/events?since=1200&limit=200
  ← { "events": [ …1201…, …1202… ], "next_since": 1202,
      "has_more": false, "current_server_seq": 1203 }

  apply in order → last_applied = 1202
  (the triggering message 1202 needs no special handling — the delta contained it)
```

### 11.9 SMS batch (wire layout — encoding **FINAL: GSM-7 text**, D-02a/T-23 closed 2026-08-24)

```
BATCH HEADER (12 B — 89 bits; the "7 B" of earlier revisions is SUPERSEDED, see §6.6.1)
  proto_version   1
  device_id       17
  team_id         3
  agency_id       1
  incident_id     9
  schema_version  1
  base_seq        4021
  base_t          2026-08-22T10:00:00Z
  event_count     2

EVENT 1  CRITICAL first          ~13 B
  type=SURVIVOR_REPORTED  seq_delta=+2  t_delta=+161s
  cell_index=214  person_count=2  survivor_status=TRAPPED  triage=RED
  rel_lat=1420  rel_lon=-880  responder_id=71

EVENT 2                          ~8 B
  type=CELL_STATUS_REPORTED  seq_delta=0  t_delta=+14s
  cell_index=214  status=SEARCHED  responder_id=71

FRAMING
  batch_id=b-17-0091  part_index=1  part_total=1  mac=4 B
  → GSM-7 base64url → 1 message
```

Semantically identical to the JSON in 11.2 — the proof of DM-26 (two representations, one model).

### 11.10 SMS gateway forwarding

The gateway decodes the batch above and forwards it. Note the gateway's **own** token in the header, the **originating** device in the body, and the MAC passed through:

```
POST /v1/events
Authorization: Bearer dev_gw_3c81f0a95e7b   ← gateway's token, role GATEWAY
```
```json
{
  "batch_id": "b-17-0091",
  "origin_device_id": 17,
  "mac": "9f3a1c04",
  "events": [
    { "device_id": 17, "seq": 4023, "type": "SURVIVOR_REPORTED",
      "entity_type": "SURVIVOR", "entity_id": 0,
      "payload": { "cell_index": 214, "person_count": 2,
                   "survivor_status": "TRAPPED", "triage": "RED",
                   "rel_lat": 1420, "rel_lon": -880 },
      "t_dev": "2026-08-22T10:02:41Z",
      "responder_id": 71, "team_id": 3, "agency_id": 1, "incident_id": 9,
      "schema_version": 1 },
    { "device_id": 17, "seq": 4021, "type": "CELL_STATUS_REPORTED",
      "entity_type": "CELL", "entity_id": 214,
      "payload": { "cell_index": 214, "status": "SEARCHED" },
      "t_dev": "2026-08-22T10:00:14Z",
      "responder_id": 71, "team_id": 3, "agency_id": 1, "incident_id": 9,
      "schema_version": 1 }
  ]
}
```

**Attribution is unchanged.** `responder_id: 71`, `team_id: 3`, `agency_id: 1`, `device_id: 17` — the gateway appears nowhere in the events it relays (AP-16).

### 11.11 Error response

```json
{
  "error": {
    "code": "MAC_VERIFICATION_FAILED",
    "message": "batch MAC does not match the secret for device 17",
    "retryable": false,
    "details": { "origin_device_id": 17, "batch_id": "b-17-0091" }
  }
}
```

---

# PART 12 — Idempotency proofs

| Scenario | Outcome | Mechanism |
|---|---|---|
| **Same request sent twice** | Identical response; no duplicate rows; **no second MQTT publish** | `ON CONFLICT (device_id, seq) DO NOTHING`; publish happens only for newly-inserted rows |
| **Same batch sent twice** | Every event de-duplicated independently; `was_duplicate: true`; same `server_seq` values | Batches carry no state (DM-14) |
| **Same event sent twice** | Second is `accepted` with the **original** `server_seq` | Primary key |
| **Timeout after server commit** | Client re-sends; server returns the original `server_seq`; client marks `ACKED`. **Cost: one redundant batch. Loss: none** | Identity allocated at creation, not at send (§2.5) |
| **SMS duplicate** | Identical to any other duplicate. Multi-part redelivery and carrier retries are safe | Same primary key; gateway `batch_id` suppression is an optimisation only |
| **MQTT duplicate** (QoS 1 redelivery) | `Y <= last_applied` → ignored | Gap rule (§4.5) |
| **MQTT message loss** | Gap detected on the next message, or on reconnect; REST delta repairs it | Gap rule + reconnect delta (§4.6) |
| **Permanently rejected event re-sent** | Deterministically re-rejected with the same code — the verdict is a function of the event, which is immutable. No duplicate row, no state churn | Same primary key; validation is pure |
| **Request-level failure (`401`/`413`)** | **All** events stay `PENDING`; none becomes `REJECTED`. The batch was never evaluated per-event (AP-22) | §9.2 |
| **REST retry** | Safe for `POST /v1/events` (dedup), `GET` (read-only). **Not safe for `POST /v1/assignments`** — each call is a distinct commander decision, so the dashboard disables the control while in flight. **AP-19** |

**Nothing in this table loses data.** Every failure costs at most one redundant transmission.

---

# PART 13 — Security

| Concern | Level-1 contract | Honest limit |
|---|---|---|
| **Authentication** | Opaque bearer tokens; join code at enrolment | Trust-on-first-use (AL-04) |
| **Authorization** | Read-all within incident; write only own team's events; `GATEWAY` role may relay with a valid MAC | Enforced at ingestion only |
| **Transport encryption** | TLS on all REST; TLS on the MQTT WebSocket listener | Prototype may use a self-signed cert — state it if so |
| **MQTT credentials** | Two **statically provisioned** accounts in Mosquitto's password file; static ACL grants publish to the backend and **subscribe-only** to the dashboard (AP-23). Delivered to the browser in the session response, after authentication | Shared static account — no per-user revocation. Subscribe-only on a non-authoritative topic, so the exposure is reading notifications. Per-user MQTT identity is Level 2 |
| **SMS trust boundary** | 4-byte truncated HMAC per batch. *Verification is implemented at **M8** with the canonical codec; **M5** issues and stores the `hmac_secret` (DM-49).* | **No confidentiality.** Content is visible to the carrier and to anyone with device access. A 32-bit MAC resists casual forgery, not a determined attacker (AD-24) |
| **Gateway authentication** | Gateway token authenticates the **relay**; per-batch MAC authenticates the **author** | A compromised gateway cannot fabricate attributed events without a device secret (AP-16) |
| **Event attribution** | `responder_id`, `team_id`, `agency_id`, `device_id` immutable on every event | Attribution proves *which device*, not *which human held it* |
| **Replay protection** | Monotonic `seq` + ingestion dedup — a replayed batch is a no-op | Prevents replay; does not prevent capture and reading |

**Not built at Level 1:** rate limiting (AP-18), at-rest encryption, mTLS, certificate pinning, token rotation, intrusion detection.

---

# PART 14 — Traceability

| Contract element | Requirement | Architecture | Data model | Feasibility |
|---|---|---|---|---|
| `POST /v1/events` batch ingestion | FR-801, FR-807 | AD-28 | DM-06, DM-14 | `04` §3.2 |
| Partial batch acceptance (AP-04) | FR-806 | P-4 | DM-17 | — |
| Duplicates reported as accepted | FR-807 | AD-28 | `08` Part 5 | `04` §3.2 |
| `server_seq` cursor | FR-802 | AD-12, AD-16 | DM-21 | — |
| Snapshot-then-delta | FR-802, NFR-01 | AD-12 | DM-30 | `04` §3.1 |
| MQTT notification-only | PS-K2 | **AD-15**, AD-16, AD-17 | (absent from `08` by design) | — |
| `retain: false` (AP-09) | — | AD-15 | — | — |
| Subscribe-only ACL (AP-10) | — | AD-15 | — | — |
| Gap rule | EC-02 | AD-16, AD-17 | DM-21 | — |
| SMS codec boundary | PS-K5 | **AD-07** | DM-24, DM-25, DM-27 | `04` §4.0.1 |
| SMS batch layout | NFR-01 | AD-06 | DM-23, DM-38 | `04` §3.1 |
| Receive-mostly ack (AP-15) | — | **D-06** | — | `04` §3.1 (TL-4) |
| Gateway relay, not author (AP-16) | PS-B7, FR-107 | `06` §8 | DM-04 | — |
| Same APK gateway | MC-01 | — | — | **T-22** |
| No token refresh (AP-17) | FR-105 | `06` §14 | — | — |
| No rate limiting (AP-18) | — | — | — | — |
| Two-tier priority in batching | **D-04** | AD-09 | `08` Part 2.2 | `04` §3.1 |
| Assignment collision surfaced, not blocked (AP-03) | **FR-303** | AD-22 | 7.2 rule 4 | `04` §5.3 |
| No per-entity read endpoints (AP-01) | NFR-01 | — | DM-30 | — |
| `REJECTED` outbox state (AP-14) | FR-806 | P-4 | **DM-39, DM-40 — amends DM-17** | — |
| Client acts on `retryable`, not code (AP-21) | FR-806 | — | DM-39 | — |
| CRITICAL never rejected for reference errors (AP-20) | **PS-B9**, FR-501 | P-4 | DM-30 | — |
| Request-level vs event-level failure (AP-22) | FR-806 | — | DM-39 | — |

---

# PART 15 — Contract consistency check

| # | Check | Verdict | Basis |
|---|---|---|---|
| 1 | **Every REST payload matches `08`** | ✅ | Examples 11.2, 11.4, 11.6 use the canonical event verbatim; only server-assigned fields (`server_seq`, `t_srv`, `received_via`) are absent before ingestion (`08` 16.7) |
| 2 | **Every MQTT payload matches `08`** | ✅ | 11.7 carries a strict **subset** of canonical fields plus a `derived` block. It adds no field `08` does not define (AP-13) |
| 3 | **SMS carries the same semantic event** | ✅ | 11.9 and 11.2 are the same two events in two representations — DM-25 (lossless), DM-26 (two encodings, one model) |
| 4 | **MQTT is never authoritative** | ✅ | Three independent guarantees: publish is post-commit only; `retain: false` (AP-09); dashboard ACL is **subscribe-only** (AP-10). MQTT appears in no table in `08` |
| 5 | **REST delta recovery works** | ✅ | 11.8 traces a concrete loss → gap → delta → convergence. Cursor never expires (AP-06) |
| 6 | **Duplicate uploads are idempotent** | ✅ | Part 12, all eight scenarios. 11.3/11.4 show identical `server_seq` on re-send |
| 7 | **`server_seq` gap detection works** | ✅ | §4.5 covers all four cases including `Y <= last_applied` and the re-snapshot threshold |
| 8 | **Device `seq` remains device-local** | ✅ | §3.3: never a cursor, never a global ordering key. It appears only as half of the identity and in `base_seq`/`seq_delta` framing |
| 9 | **Offline events eventually synchronise** | ✅ | Outbox → batch → transport → dedup → ack. Every failure in Part 2.4 preserves the event; only `500`/`503` and `retryable: true` return to `PENDING`; permanent verdicts are retained locally in `REJECTED` (§2.7) |
| 12 | **`REJECTED` never deletes an event** | ✅ | It is a delivery state on the outbox row. The event remains in the local log permanently and is auditable there (`08` 6.2, DM-39). No code path deletes an event for any reason |
| 13 | **Permanent failures do not block later valid events** | ✅ | Two independent levels: partial batch acceptance (AP-04) inside the batch, and `PENDING`-only selection across the queue (§2.7.3) |
| 14 | **Retryable failures stay `PENDING`** | ✅ | Entry to `REJECTED` requires `retryable: false` inside a `200`. Transport failures, timeouts, lost responses, `500`, `503` and request-level failures all return to `PENDING` (§2.7.1, AP-22) |
| 15 | **Rejections carry sufficient diagnostics** | ✅ | Four never-pruned outbox columns (`08` 6.1, DM-40) plus a device-side diagnostics view and server-side counters (§2.7.4) |
| 16 | **Server distinguishes retryable from permanent** | ✅ | Every rejection carries `retryable`; §2.6 classifies every code; the client never interprets code strings (AP-21) |
| 17 | **Canonical event schema unchanged** | ✅ | All rejection state is outbox delivery metadata (DM-39). `08` Part 1 is untouched; no new field is transmitted or stored in `event` |
| 18 | **Life-critical data cannot be lost to a reference typo** | ✅ | `SURVIVOR_REPORTED` is never permanently rejected for `UNKNOWN_CELL`; it is accepted and flagged in the read model (AP-20) |
| 10 | **Gateway operates without changing domain semantics** | ✅ | Part 7.2: attribution untouched; gateway does no domain validation; backend cannot distinguish a relayed event from a direct one except by `received_via` |
| 11 | **Low-bandwidth constraints satisfied** | ✅ | Part 10: SMS batch 171 B; snapshot bounded by DM-12, DM-10, positional arrays and the 8,191-cell `MAX_CELLS` limit; dashboard structurally cannot re-download the incident (§10.3) |

**Open items carried forward:** ~~D-02a/T-23 (SMS encoding)~~ ✅ **CLOSED 2026-08-24 — GSM-7 text, `max_batch_bytes` 120 B** · ~~SP-01b-A pending~~ ✅ **executed** · **TL-10 still open** — carrier-side segment counts were not observed and the throttle threshold was not located; both are measurement gaps behind the transport interface and **neither blocks M8** · SP-06 pending (Mosquitto)

**AP-14 is approved and applied.** `08` amended (DM-39, DM-40); checks 12–18 above were added to cover it, and checks 1–11 were re-run against the amended documents — all pass.

---

# API / MQTT DECISION REGISTER

| ID | Decision | Reason | Traceability | Alternatives | Risk | Level | Status |
|---|---|---|---|---|---|---|---|
| AP-01 | No per-entity read endpoints | Removes the temptation to poll; snapshot+delta is the contract | NFR-01, DM-30 | REST resources per entity | Dashboard needs everything in the snapshot | L1 | **Final** |
| AP-02 | Enrolment is deliberately non-idempotent | Two handsets must never share a `device_id` | **D-05** | Idempotent by join code | A wasted code produces an orphan device | L1 | **Final** |
| AP-03 | Assignment collision returns `201` + `already_held`, not `409` | FR-303 requires the collision **surfaced**, not blocked | **FR-303**, AD-22 | `409 Conflict` | Commander may proceed knowingly — intended | L1 | **Final** |
| AP-04 | Partial batch acceptance; `200` with per-event results | Whole-batch rejection would permanently block the outbox | FR-806, P-4 | All-or-nothing batches | Clients must handle mixed responses | L1 | **Final** |
| AP-05 | Duplicates land in `accepted`, flagged | Client action is identical either way | **AD-28** | Separate `duplicates` array | Diagnostics must read the flag | L1 | **Final** |
| AP-06 | Cursor is plain `server_seq`, never opaque | No server state, no expiry, no failed resumption | AD-12, DM-21 | Opaque cursor tokens | Exposes an internal counter — acceptable | L1 | **Final** |
| AP-07 | Initial sync is snapshot, not log replay | Server already holds the fold | DM-30 | Replay from `server_seq` 0 | Snapshot is the largest payload — bounded in §10.2 | L1 | **Final** |
| AP-08 | One MQTT topic per incident at Level 1 | Dashboard wants everything; subtopics are a free L2 seam | AD-19 | Per-type topics now | — | L1 | **Final** |
| AP-09 | `retain: false`, always | A retained message would look like current state — the exact AD-15 failure | **AD-15** | Retain latest per topic | New subscribers must snapshot — intended | L1 | **Final** |
| AP-10 | Dashboard MQTT credential is **subscribe-only** | Makes "MQTT is not a write path" structural, not merely stated | **AD-15** | Shared credential | Broker ACL must be configured — SP-06 | L1 | **Final** |
| AP-11 | No MQTT commands at Level 1 | Commands need durability, ack and audit — all REST properties | AD-15 | Assignment push over MQTT | Assignments arrive on next sync (AD-19) | L1 | **Final** |
| AP-12 | Duplicate flag rides in `derived`, not a separate message | One fold, one source; avoids server/client divergence | **D-01b**, DM-07 | `DUPLICATE_SEARCH_FLAGGED` type | Slightly larger message | L1 | **Final** |
| AP-13 | MQTT carries a compact event body, not just a pointer | Removes a REST round trip from every update; ~230 B on an online link | `06` §9.1 | Pointer-only notifications | Must stay a strict subset of canonical fields | L1 | **Final** |
| AP-14 | **`REJECTED` outbox delivery state** for permanent validation failures | Retrying an unfixable event forever wastes the scarcest resource; the event is retained and surfaced, so nothing is lost | **DM-39, DM-40 — amends DM-17**, P-4 | Retry forever; discard | Wording is load-bearing: must never read as "event deleted" | L1 | **FINAL — approved 2026-08-22** |
| AP-15 | SMS ack carries highest **contiguous** accepted `seq` | Fixed ~4 B beats a variable list on a throttle-constrained downlink | **D-06**, TL-4 | Explicit accepted list | One redundant resend per gap | L1 | **Final** |
| AP-16 | Gateway token authenticates the relay; batch MAC authenticates the author | Without it a compromised gateway could fabricate attributed events | PS-B7, AD-24 | Trust the gateway token alone | MAC is 32-bit — weak, disclosed | L1 | **Final** |
| AP-17 | No token refresh at Level 1 | Adds an endpoint, a failure mode and an offline edge case for no prototype benefit | FR-105, AL-04 | Short tokens + refresh | Long-lived tokens; revocation lags to next contact | L1 | **Final** |
| AP-18 | No rate limiting; `429` not used | Handful of enrolled devices, backoff already built in | — | Token-bucket throttling | A runaway client could flood — accepted at prototype scale | L1 | **Final** |
| AP-19 | `POST /v1/assignments` is **not** idempotent; UI disables the control in flight | Each call is a distinct commander decision | FR-301 | Idempotency-Key header | Double-click could double-assign — UI-guarded | L1 | **Final** |
| AP-20 | **CRITICAL events are never permanently rejected for reference errors**; accepted and flagged instead | A mistyped `cell_index` must never discard a real survivor's location | **PS-B9**, FR-501, P-4 | Reject uniformly; reject nothing | Read model must surface the flag or it is invisible | L1 | **Final — new, introduced by AP-14** |
| AP-21 | Client acts on the `retryable` boolean, never on the `code` string | New codes need no client change; a client cannot mis-classify an unseen code. Absent flag fails safe to retryable | AP-14 c.7 | Client-side code table | Server must set the flag correctly on every rejection | L1 | **Final** |
| AP-22 | Request-level failures never produce `REJECTED` | A `401`/`413` means the batch was never evaluated per-event, so no verdict exists | AP-14 c.5 | Treat any 4xx as permanent | Conflating the two would strand valid events | L1 | **Final** |
| AP-23 | MQTT credentials are **statically provisioned by configuration**, not issued per session; delivered to the browser in the session response after authentication | Per-session issuance is not feasible with Mosquitto's static password file and would require a plugin, contradicting T-09's minimalism. The subscribe-only security property is unchanged | **F-03**, AP-10, AD-15, T-09 | Auth plugin; rewrite password file per login; embed in the JS bundle | Shared static account — no per-user revocation; subscribe-only on a non-authoritative topic | L1 | **Final** |
| AP-24 | `CoverageMetrics` is **server-owned**, derived from `cell_state`, carried in the snapshot and in `derived.coverage` on events that change `cell_state`. The dashboard never computes it | A client-side fold would duplicate the server's fold and diverge exactly when a gap occurs. Mirrors AP-12's one-fold principle | **F-04**, AP-12, FR-703, DM-30 | Client-side recomputation; a separate metrics endpoint | ~60 B on cell-state-changing events — immaterial on the command-post link | L1 | **Final** |

---

**Next deliverable (not started):** the implementation plan for the Spine's eleven elements, in the build order fixed in `05` §3. Still not code.
