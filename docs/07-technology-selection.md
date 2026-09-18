# RescueNet AI — Technology Selection (v1.0)

**Date:** 2026-08-22 · **Stage:** Technology selection only · **Target:** Minimum Demonstrable Spine (D-03)
**Baseline:** [`06-system-architecture.md`](06-system-architecture.md) — approved, and **not modified by this document**
**Inputs:** [`01`](01-requirements-analysis.md) · [`02`](02-prototype-scope.md) · [`03`](03-feasibility-analysis.md) · [`04`](04-feasibility-validation.md) · [`05`](05-final-decisions.md)

> **No code, no folders, no dependencies installed.** Selection and justification only.

> **Scope note.** `03` §6 proposed a set of technical choices explicitly tagged **P — "for approval, all replaceable."** This document supersedes those proposals. It does **not** touch any decision marked FINAL in `05`.

---

## 0. Selection method

**Optimisation order**, applied in this priority when candidates conflict: reliable working prototype → fast implementation → low bandwidth → offline-first → clean backend → demo reliability → automated testing → Claude Code implementability.

**Depth is proportionate.** Full eleven-criterion comparisons are given for the five areas where the choice is genuinely consequential and where you asked for them — mobile, backend, dashboard, MQTT broker, database. The remaining categories get a concise rationale, because the decision is either forced by an earlier choice or genuinely low-stakes.

**Honesty marker.** Statements about Android API behaviour below are **documented platform behaviour, reasoned from knowledge — not validated on our devices.** SP-01b-A remains pending, and per `05` §7 nothing here may be claimed as proven.

---

## 1. Mobile framework and language — three realistic approaches

The decisive question is not UI speed. It is: **can this framework reach the Android APIs the SMS transport needs, without a third-party plugin we do not control?**

### 1.1 The Android SMS reality (documented behaviour, unvalidated on our devices)

| Capability | Requirement | Notes |
|---|---|---|
| Programmatic send | `SEND_SMS` runtime permission; `SmsManager` | App need **not** be the default SMS handler |
| Receive | `RECEIVE_SMS`; `SMS_RECEIVED` broadcast | Default-handler status not required to receive the broadcast |
| Binary / port-addressed | `sendDataMessage`; `DATA_SMS_RECEIVED` with a port filter | **NOT USED — rejected 2026-08-24.** SP-01b-A Q1: 10/10 `GENERIC_FAILURE` on vivo V2151 / Jio, 0/10 received. One direction tested; the other was not captured and is not claimed (`05` §1.2a) |
| Play Store distribution | SMS permissions are restricted and need a declaration | **Irrelevant** — prototype is sideloaded (`03` AS-03) |

### 1.2 Expo managed mode — verified as insufficient

You asked not to assume. **Expo managed mode cannot implement this transport.** `expo-sms` opens the system compose UI and requires the user to physically press send — it cannot send a batch programmatically, cannot receive, and cannot touch port-addressed SMS. Expo *with* a development build, config plugin and a custom native module can — but at that point it is bare React Native plus additional tooling, with none of managed mode's benefits retained. **Managed Expo is rejected on capability, not preference.**

### 1.3 Comparison

| Criterion | **A · Native Android (Kotlin)** | **B · Flutter (Dart)** | **C · React Native (bare CLI)** |
|---|---|---|---|
| **Development speed** | Slower UI work; Gradle build loop | Fast UI; hot reload | Fast UI; hot reload |
| **Offline capability** | Excellent — Room/SQLite, real transactions | Excellent — drift/SQLite, real transactions | Good — op-sqlite; WatermelonDB brings its own sync opinions that would fight our event log |
| **MQTT compatibility** | N/A at L1 (**AD-19**); mature clients for L2 | N/A at L1; clients exist | N/A at L1; clients exist |
| **Android capability** | **Direct, first-class.** Zero indirection to `SmsManager` | Via platform channel — ~50 lines of Kotlin, fully under our control | Via native module; old-arch/new-arch churn adds risk |
| **Testing** | JVM unit tests for codec/outbox/merge — fast, no emulator; Robolectric; instrumented for SP-04 | `dart test` for pure logic — fast; widget tests | Jest for pure logic — fast |
| **Maintainability** | Single language, single platform, no bridge | Two languages at the boundary | Two languages plus bridge-version churn |
| **Performance** | Best | Very good | Good |
| **Low-bandwidth suitability** | Identical — codec is ours in every case | Identical | Identical |
| **Claude Code suitability** | Strong; verbose but highly predictable | Strong; concise | Strong; most churn across versions |
| **Prototype complexity** | Lowest layer count for the riskiest features | One extra layer | Two extra layers |
| **Major risks** | Slower screen construction | Depending on unmaintained telephony plugins — avoidable by writing our own channel | Native-module churn; WatermelonDB fighting the event-log design |

### 1.4 Decision — **FINAL: Native Android, Kotlin**

**The deciding argument is that we are Android-only by decision** (`03` AMB-13, AL-12; iOS is Level 3). Flutter's and React Native's principal advantage is cross-platform reach — a benefit we have already decided not to consume. Paying an abstraction layer for an unused benefit, directly on top of our two riskiest features (SMS transport and durable local writes), is the wrong trade for a prototype whose grade depends on demo reliability.

Supporting reasons: our UI is deliberately minimal (three-tap doctrine, PI-07), so UI velocity matters less than usual; JVM unit tests exercise codec, outbox and merge logic with no emulator, which is the highest-value test surface (`03` §3.8); and this is consistent with the approved analysis in `03` §3.4.

**Runner-up and switch condition:** Flutter with a hand-written platform channel — genuinely viable. **Switch if** the team's existing fluency is Flutter, since fluency would outweigh the layer argument. Do **not** switch to gain iOS; iOS is out of scope.

---

## 2. Local database — comparison

| Criterion | **A · Room (SQLite)** | **B · SQLDelight** | **C · Plain SQLite + hand-written DAO** |
|---|---|---|---|
| Development speed | Fast; annotation-driven | Fast; SQL-first with typed results | Slowest; most boilerplate |
| Offline capability | Excellent; real ACID transactions | Excellent | Excellent |
| Transaction spanning event + seq + outbox (**AD-10**) | Supported | Supported | Supported |
| Testing | In-memory database for unit tests | In-memory; SQL verified at compile time | Manual |
| Maintainability | Very good; migrations built in | Very good | Poor |
| Performance | More than sufficient at prototype volumes | Same | Same |
| Claude Code suitability | Strong — extremely conventional | Strong | Weaker, more to get wrong |
| Major risks | Annotation-processing build time | Smaller ecosystem | Hand-rolled migration bugs |

**FINAL: Room over SQLite.** It gives the single-transaction guarantee AD-10 requires, an in-memory mode that makes outbox and sequence-allocation tests fast, and built-in migrations. SQLDelight would work; the difference is not material, and Room is the more conventional target for automated implementation.

**SP-04 validates the durability claim** (force-kill and reboot survival). Until it runs, NFR-07 remains unproven per `05` §7.

---

## 3. Backend runtime and framework — comparison

| Criterion | **A · Python + FastAPI** | **B · Node.js + TypeScript + Fastify** |
|---|---|---|
| **Development speed** | Very fast; Pydantic models double as validation and schema | Very fast; shares language with the dashboard |
| **Offline capability** | N/A (server side) | N/A |
| **MQTT compatibility** | `aiomqtt` (async) or `paho-mqtt` — mature | `mqtt.js` — mature, same library family as the dashboard |
| **Android capability** | N/A | N/A |
| **Testing** | **pytest — the strongest fit.** SP-05 is already Python; its 13 convergence assertions port directly into the real suite | Vitest/Jest — good; SP-05 would need re-writing |
| **Maintainability** | Excellent; explicit and readable | Excellent; single language across backend and dashboard |
| **Performance** | Sufficient — prototype scale is hundreds of events, not thousands/second | Somewhat faster; irrelevant at our volumes |
| **Low-bandwidth suitability** | Identical — the codec is ours | Identical |
| **Claude Code suitability** | Very strong; tightest path from spec to a working, tested endpoint | Very strong |
| **Prototype complexity** | One extra language in the project (three total) | One fewer language (two total) |
| **Major risks** | Async/sync discipline around the MQTT client | Type-config overhead; ESM/CJS friction |

### 3.1 Decision — **FINAL: Python + FastAPI**

Two concrete reasons, neither of them popularity:

1. **Test continuity.** `04` §3.2's merge/convergence simulation is already written in Python and already passes 13/13 against the D-01b scenario. Under FastAPI those assertions become the backbone of the real merge test suite directly, rather than being translated — and merge correctness is the single most important thing this system must get right.
2. **Three of your eighteen categories collapse into one choice.** FastAPI supplies validation (Pydantic v2, category 13) and API documentation (automatic OpenAPI, category 15) without additional selection or dependency. That is the "smallest stack" criterion doing real work.

**The Node counter-argument is real and I want it on the record:** it would reduce the project from three languages to two, and share types natively with the dashboard. It loses because type sharing is recoverable — `openapi-typescript` generates dashboard types from FastAPI's OpenAPI output — whereas test continuity is not recoverable without rewriting the one artefact that already proves our hardest logic.

**Structure: modular monolith, single deployable.** Modules — `ingestion`, `events`, `projections`, `api`, `mqtt`, `sms_gateway`, `audit` — enforcing `06` §3's dependency direction inside one process. No microservices, no event bus, no Redis.

---

## 4. Database — comparison

| Criterion | **A · PostgreSQL** | **B · SQLite on the server** |
|---|---|---|
| Development speed | Fast; one Docker service | Fastest; zero services |
| Event-model fit (append-only, `(device_id, seq)` PK, monotonic `server_seq`) | Excellent — `BIGSERIAL`/identity, composite PK, `JSONB` for payloads | Adequate at prototype scale |
| Concurrent writers (API + SMS gateway forward + projection engine) | **Proper MVCC** | Single-writer lock; workable but a real constraint |
| Testing | Disposable instance via Compose; transactional fixtures | Trivially fast in-memory |
| Maintainability | Standard, well-understood | Fewer moving parts |
| Performance | More than sufficient | Sufficient at Spine scale |
| Low-bandwidth suitability | N/A | N/A |
| Claude Code suitability | Strong | Strong |
| Major risks | One more service to run on demo day | Write contention under concurrent ingestion paths |

**FINAL: PostgreSQL.** The deciding factor is concurrent writers: `06` §10 has the REST ingestion path, the SMS gateway forward path and the projection engine all writing, and SQLite's single-writer model would make that a source of demo-day flakiness. It is also one Compose service, so the cost is small.

**Explicitly NOT selected: PostGIS.** `03` §6 TC-06 proposed it, but that was a **P-tagged proposal, not a FINAL decision**, so refining it reopens nothing. The Spine's grid is a bounding box subdivided into rectangular cells (`05` §3 element 2); cell bounds are plain numeric columns and containment is arithmetic in application code. **PostGIS is Level 2**, needed only if polygon drawing or true geospatial queries arrive. Adding it now would be exactly the over-engineering you asked to avoid.

### 4.1 Access layer — **FINAL: SQLAlchemy 2.0 (Core-leaning) + Alembic**

The event store is append-only with a fixed shape, so heavy ORM mapping earns little; but **migrations matter** across a multi-week build, and Alembic supplies them. Raw `asyncpg` with hand-written SQL was the alternative — rejected because hand-rolled migrations are a predictable source of avoidable defects. Use Core-style explicit SQL for the event store and hot read paths; light ORM only where it genuinely reduces code.

---

## 5. MQTT broker — comparison

| Criterion | **A · Eclipse Mosquitto** | **B · EMQX** |
|---|---|---|
| Development speed | Single small binary; a few lines of config | Heavier; more configuration surface |
| Offline capability | N/A | N/A |
| MQTT compatibility | MQTT 3.1.1 and 5; **WebSocket listener** for the browser | Full, plus clustering and rules |
| Testing | Trivial to start and stop in Compose | Heavier in CI |
| Maintainability | Minimal | More to keep configured |
| Performance | Far beyond our needs | Far beyond our needs |
| Low-bandwidth suitability | Fine — MQTT overhead is small either way | Fine |
| Claude Code suitability | Strong; config is a short file | Strong but more surface to get wrong |
| Prototype complexity | **Lowest** | Higher for capabilities we do not use |
| Major risks | Must remember to enable the WebSocket listener for the dashboard | Operational weight we cannot justify |

**FINAL: Mosquitto.** Our broker requirement is topic fan-out of post-commit notifications to one or two dashboard clients (`06` §9). Clustering, rule engines and bridging are capabilities we have architecturally excluded. **AD-15 means the broker holds no truth**, so durability and clustering features are irrelevant by design.

**Required config:** a WebSocket listener, because the dashboard subscribes from a browser. Flagged as a small verification item (§F).

### 5.1 MQTT client libraries — **FINAL**
- **Backend publisher:** `aiomqtt` (async, wraps Paho) to match FastAPI's async model; `paho-mqtt` on a background thread is the documented fallback if the async lifecycle proves awkward. **Provisional at the library level** (§F) — the choice is contained behind a small publisher module and is not architectural.
- **Dashboard subscriber:** `mqtt.js` over WebSockets — the standard browser client.
- **Mobile:** **none at Level 1** (AD-19). Level 2 would use the Paho or HiveMQ Android client.

---

## 6. Commander dashboard — comparison

The framework choice is genuinely **low-stakes here**, and it is worth saying why: the hard parts are (a) rendering thousands of cells, which the map library does imperatively via WebGL, and (b) `server_seq` gap detection and REST reconciliation, which is a few dozen lines of plain logic in any framework.

| Criterion | **A · React + Vite + TypeScript** | **B · SvelteKit** | **C · Vanilla TypeScript + Vite** |
|---|---|---|---|
| Development speed | Fast | Fast; less boilerplate | Slower once panels and lists appear |
| MQTT compatibility | `mqtt.js` — identical in all three | Identical | Identical |
| Map integration | Most mature MapLibre bindings and examples | Good; fewer examples | Direct imperative use — actually simplest |
| Testing | Vitest for gap-detection logic | Vitest | Vitest |
| Maintainability | Good; conventional structure | Good | Degrades as UI grows |
| Performance | Map does the heavy lifting | Slightly leaner | Leanest |
| Low-bandwidth suitability | Bundle size irrelevant — dashboard is online at the command post (**D-01**) | Same | Same |
| Claude Code suitability | Strongest — most predictable patterns | Strong | Strong but more hand-rolled state |
| Prototype complexity | Moderate | Moderate | Lowest at first, rises fastest |
| Major risks | Over-structuring a one-screen app | Fewer worked examples for MapLibre | State handling sprawl |

**FINAL: React + Vite + TypeScript.** Chosen for structural predictability around the cell-detail panel, alert list and metrics strip, and the most worked examples for MapLibre integration — not for popularity. **This decision is low-risk and reversible**; SvelteKit would serve equally well, and nothing in `06` depends on it.

### 6.1 Styling — **FINAL: Tailwind CSS**
Build-time only, no runtime, and it keeps the colour-plus-pattern requirements (FR-304, FR-408 principle) explicit in markup. **Component libraries such as MUI are rejected** — heavy, opinionated, and we need perhaps a dozen components.

### 6.2 Mapping — **FINAL: MapLibre GL JS**
The requirement is decisive: **5,000 cell polygons coloured by status** (NFR-09 synthetic load). MapLibre renders vector geometry in WebGL with **data-driven styling**, so recolouring by a status property is a style expression rather than 5,000 DOM updates. Leaflet is DOM/canvas-based and would struggle at this polygon count; deck.gl is more capability than we need. MapLibre also runs **with no basemap at all** — a blank style plus a GeoJSON source — which matters because the Spine ships without tile packs (`05` §3).

**Provisional until SP-03** confirms render timings at 5,000 cells (§F).

---

## 7. Remaining categories — concise rationale

| # | Category | **Decision** | Why |
|---|---|---|---|
| 12 | **Authentication** | Opaque bearer tokens (random, stored server-side as SHA-256) + a per-device HMAC-SHA256 secret for SMS batch MACs. Android side: token in `EncryptedSharedPreferences`. Commander: incident password → session token | Matches `06` §14 exactly. Opaque tokens are **revocable**, unlike self-contained JWTs, and Python's `secrets`/`hmac`/`hashlib` are **standard library** — zero dependencies. No OAuth, no identity provider: `06` §14 already accepts trust-on-first-use (AL-04) |
| 13 | **Validation / schema** | Backend: **Pydantic v2** (arrives with FastAPI). Mobile: Kotlin data classes + `kotlinx.serialization`. Wire codec: **hand-written bit-packing, no library** | The compact codec is bespoke by necessity (`04` §3.1); no library produces 8–13-byte events |
| 14 | **Testing** | Backend **pytest** + `pytest-asyncio` + `httpx` async client; disposable Postgres via Compose. Mobile **JUnit5** for codec/outbox/merge (no emulator) + Robolectric + a minimal instrumented suite for SP-04. Dashboard **Vitest** for gap-detection logic | Merge/convergence tests are pure logic and must run fast and often. Playwright/e2e is **Level 2** — a scripted demo-scenario runner is cheaper evidence |
| 15 | **API documentation** | FastAPI's automatic **OpenAPI** + Swagger UI; commit `openapi.json`; generate dashboard types with `openapi-typescript` | This *is* the FR-901/FR-902 evidence for EC-04 — the documented contract an external agency reads |
| 16 | **Logging / observability** | Structured JSON logs to stdout (stdlib `logging` with a JSON formatter, or `structlog`); a `/health` endpoint; a **sync-diagnostics endpoint** exposing watermarks, outbox depth and recent `server_seq` | The diagnostics endpoint is deliberate: it is how EC-01 evidence gets captured during the demo. **No Prometheus, no Grafana, no tracing stack** |
| 17 | **Container / dev environment** | **Docker Compose**, three services: `backend`, `postgres`, `mosquitto`. Android Studio outside Compose | One command to a running system. No Kubernetes |
| 18 | **Deployment** | Single host — a laptop or one small VM — running the same Compose file. Backend is one container (modular monolith) | `05` D-01 removed the edge-server requirement, so a single deployable is sufficient. Cloud hosting is optional and changes nothing |

### 7.1 The SMS gateway — a technology decision worth stating

`06` §8 requires a gateway handset that receives SMS, reassembles batches and forwards over HTTPS. **Decision: the same Android APK running in "gateway mode"**, not a separate application.

It reuses the SMS receiver, the codec and the framing logic that already exist for the field app, so the gateway costs a mode flag rather than a second codebase. The alternative — a USB GSM modem plus a server-side daemon — introduces hardware, which is in tension with MC-01 and unnecessary given the handsets we already have.

---

## A. Final recommended stack

| Layer | Technology |
|---|---|
| **Mobile** | Native Android, Kotlin (min API per `03` NFR-11) |
| **Mobile local store** | Room over SQLite |
| **Mobile SMS access** | Android `SmsManager` / SMS broadcast receivers, direct |
| **SMS gateway** | Same APK in gateway mode |
| **Backend runtime** | Python |
| **Backend framework** | FastAPI — modular monolith, single deployable |
| **Database** | PostgreSQL (no PostGIS at Level 1) |
| **Access layer** | SQLAlchemy 2.0 (Core-leaning) + Alembic |
| **MQTT broker** | Eclipse Mosquitto, with WebSocket listener |
| **MQTT clients** | `aiomqtt` backend · `mqtt.js` dashboard · none on mobile |
| **Dashboard** | React + Vite + TypeScript |
| **Styling** | Tailwind CSS |
| **Mapping** | MapLibre GL JS |
| **Auth** | Opaque bearer tokens + per-device HMAC secret |
| **Validation** | Pydantic v2 · `kotlinx.serialization` · hand-written codec |
| **Testing** | pytest · JUnit5 + Robolectric · Vitest |
| **API docs** | OpenAPI via FastAPI + `openapi-typescript` |
| **Observability** | Structured JSON logs · `/health` · sync-diagnostics endpoint |
| **Dev environment** | Docker Compose — backend, postgres, mosquitto |
| **Deployment** | Single host, same Compose file |

**Deliberately not used:** Kubernetes · microservices · message/event bus · Redis · Elasticsearch · GraphQL · CRDT frameworks · PostGIS · component libraries · service mesh · tracing stack · Expo managed mode · WatermelonDB.

---

## B. Technology decision table

| ID | Area | Decision | Status | Traces to | Alternatives rejected | Key risk |
|---|---|---|---|---|---|---|
| T-01 | Mobile framework | Native Android / Kotlin | **FINAL** | `03` §3.4, AL-12, AD-07 | Flutter; React Native bare; **Expo managed (rejected on capability)** | Slower UI construction |
| T-02 | Mobile language | Kotlin | **FINAL** | T-01 | Java | — |
| T-03 | Local database | Room / SQLite | **FINAL** | AD-10, NFR-07 | SQLDelight; raw SQLite | Durability unproven until SP-04 |
| T-04 | Backend runtime | Python | **FINAL** | `04` §3.2 test continuity | Node.js; Kotlin/JVM | Third language in the project |
| T-05 | Backend framework | FastAPI, modular monolith | **FINAL** | `06` §10, "prefer modular monolith" | Fastify; Django; Flask | Async discipline around MQTT client |
| T-06 | Database | PostgreSQL | **FINAL** | `06` §10.2, concurrent writers | Server-side SQLite | One more service on demo day |
| T-07 | PostGIS | **Not used at Level 1** | **FINAL** | `05` §3 element 2 | Adopting PostGIS now | Needed if polygon drawing is promoted |
| T-08 | Access layer | SQLAlchemy 2.0 + Alembic | **FINAL** | Migration safety | Raw asyncpg + hand migrations | ORM misuse on the hot append path |
| T-09 | MQTT broker | Mosquitto | **FINAL** | `06` §9, AD-15 | EMQX; HiveMQ; NanoMQ | WebSocket listener must be enabled |
| T-10 | Backend MQTT client | `aiomqtt` | **PROVISIONAL** | AD-15 | `paho-mqtt` on a thread | Async lifecycle friction |
| T-11 | Dashboard MQTT client | `mqtt.js` over WebSockets | **FINAL** | `06` §11 | EventSource/SSE; raw WebSocket | Broker WS config |
| T-12 | Dashboard framework | React + Vite + TypeScript | **FINAL** *(low-risk, reversible)* | `06` §11 | SvelteKit; vanilla TS | Over-structuring one screen |
| T-13 | Styling | Tailwind CSS | **FINAL** | FR-304, FR-408 | MUI; plain CSS | — |
| T-14 | Mapping | MapLibre GL JS | **PROVISIONAL** — pending SP-03 | NFR-09, FR-702 | Leaflet; OpenLayers; deck.gl | Render performance at 5,000 cells |
| T-15 | Authentication | Opaque tokens + per-device HMAC secret | **FINAL** | `06` §14, AD-24 | JWT; OAuth/OIDC | Trust-on-first-use — AL-04, disclosed |
| T-16 | Validation | Pydantic v2 · kotlinx.serialization · hand-written codec | **FINAL** | `06` §8, `04` §3.1 | Marshmallow; protobuf; CBOR | Codec is bespoke and must be tested hard |
| T-17 | Testing | pytest · JUnit5 + Robolectric · Vitest | **FINAL** | `03` §3.8, `04` §3.2 | Playwright e2e at L1 | Test discipline under deadline (R-05) |
| T-18 | API docs | OpenAPI via FastAPI | **FINAL** | FR-901, FR-902, EC-04 | Hand-written docs | Drift — mitigated by generating from schema |
| T-19 | Observability | JSON logs + `/health` + sync-diagnostics | **FINAL** | EC-01 evidence, NFR-18 | Prometheus/Grafana/OTel | — |
| T-20 | Dev environment | Docker Compose, 3 services | **FINAL** | "single deployable" | Kubernetes; bare-metal | Compose version drift across machines |
| T-21 | Deployment | Single host, same Compose file | **FINAL** | D-01 | Managed cloud; k8s | Demo-day host failure — keep a spare |
| T-22 | SMS gateway | Same APK, gateway mode | **FINAL** | `06` §8, D-06, MC-01 | USB GSM modem + daemon | Gateway handset is a single point of failure (R-07) |
| T-23 | SMS encoding | **GSM-7 text** (base64url alphabet); `max_batch_bytes` **120 B** | ✅ **FINAL** — D-02a closed 2026-08-24 | `05` §1.2a, `09` §6.1/§6.3 | Binary / port-addressed — **rejected on evidence**: SP-01b-A Q1 returned 10/10 `GENERIC_FAILURE`, 0/10 delivered | Contained inside the codec by AD-07 |

---

## C. Dependency and licence considerations

| Component | Licence | Note |
|---|---|---|
| Kotlin / Android SDK | Apache 2.0 / Android SDK terms | Standard |
| Room, AndroidX | Apache 2.0 | Standard |
| Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest | PSF / MIT / BSD | All permissive |
| PostgreSQL | PostgreSQL Licence | Permissive |
| Mosquitto | **EPL 2.0 / EDL 1.0 dual** | Permissive for our use — we run it unmodified as a service, we do not link it |
| `aiomqtt` / `paho-mqtt` | BSD / EPL+EDL | Permissive |
| React, Vite, Vitest, Tailwind, `mqtt.js` | MIT | Permissive |
| **MapLibre GL JS** | **BSD-3-Clause** | Chosen partly because it is the open fork; the pre-fork Mapbox GL JS v2+ licence would be a genuine constraint |
| Basemap tiles (Level 2) | Depends on source | **OpenStreetMap-derived requires attribution** — AMB-14 remains open |

**No copyleft obligations** attach to our source. Nothing in the stack requires a commercial licence at prototype scale. **Action:** carry OSM attribution into the dashboard if and when tiles are added.

---

## D. Development environment requirements

| Requirement | Detail |
|---|---|
| **Android Studio + SDK** | **Currently absent** — verified in `04` §4.0. This blocks SP-01b-A, SP-02, SP-04 and all mobile work. **Highest-priority setup item** |
| JDK | Bundled with Android Studio |
| Docker + Compose | Backend, Postgres, Mosquitto |
| Python 3.12+ | Present (3.12.10) |
| Node.js 20+ | Present (24.18.0) |
| Git | Present |
| Two developer machines minimum | Mobile and backend work in parallel |

---

## E. Hardware requirements

| Item | Status | Purpose |
|---|---|---|
| 2 × Android handsets | **Confirmed available** | Field app + gateway; SP-01b-A, SP-02, SP-04 |
| 2 × SMS-capable SIMs | **Confirmed available** | SMS transport; SP-01b-M already executed on them |
| 1 × laptop for backend + dashboard | Assumed | Demo host |
| **Spare charged handset for the gateway** | **Not yet arranged** | R-07 — gateway failure on demo day is rated Low × Critical |
| Projector/display | Venue | Verify status colours survive a dim projector (`03` §3.9) |

---

## F. Remaining technology spikes

| ID | Spike | Question | Blocks | Time-box |
|---|---|---|---|---|
| ~~**SP-01b-A**~~ | Programmatic SMS: binary Q1, text Q2, throttle Q3 | **EXECUTED 2026-08-24** on vivo V2151/Jio and OPPO CPH2859/Airtel | ✅ **T-23 / D-02a CLOSED** — Q1 failed, GSM-7 text selected. Q3 did **not** locate the throttle (`05` §1.2a) | done |
| **SP-03** | MapLibre at 5,000 cells + 200 markers | Does the dashboard stay interactive? | **T-14** | 0.5 day |
| **SP-04** | Room durability: force-kill, reboot, mid-transaction interrupt | Do acknowledged writes always survive? | **T-03**, AD-10, NFR-07 | 0.5 day |
| **SP-06** *(new)* | Mosquitto WebSocket listener + `mqtt.js` from the browser, plus `aiomqtt` publish from FastAPI | Does the end-to-end MQTT path work, including gap-detection under a forced disconnect? | **T-10**, AD-16, AD-17 | 0.5 day |
| SP-02 | Peer sync viability | Is L2-01 promotable? | Level 2 only | 1 day |

**SP-01b-A was the critical one. It is done** — executed 2026-08-24 once the Android toolchain was installed, on two handsets and two carriers. It closed T-23/D-02a in favour of **GSM-7 text**. The residual unknowns it did *not* close — segment economy (TL-10) and the throttle threshold — are non-blocking measurement gaps, not decisions (`05` §1.2a).

---

## G. Risks

| ID | Risk | Rating | Mitigation |
|---|---|---|---|
| TR-01 | Android Studio not installed — blocks all mobile work and three spikes | **High × High** | Install first, before any implementation |
| TR-02 | Programmatic SMS behaves differently from documented behaviour | Med × High | SP-01b-A; codec isolation (AD-07) means only the codec changes |
| TR-03 | Three languages (Kotlin, Python, TypeScript) spread attention thin | Med × Med | Modular monolith and a minimal dashboard keep two of the three small |
| TR-04 | MapLibre degrades at 5,000 cells | Low × Med | SP-03; fall back to cell aggregation or a coarser default grid |
| TR-05 | `aiomqtt` async lifecycle friction inside FastAPI | Low × Low | Documented fallback to `paho-mqtt` on a thread; contained in one module |
| TR-06 | Mosquitto WebSocket listener misconfigured, silently breaking live updates | Med × Med | SP-06; dashboard must show "live updates offline" rather than appearing fresh (`06` §11) |
| TR-07 | Gateway handset fails on demo day | Low × **Critical** | Spare charged handset, pre-paired (§E) |
| TR-08 | Room annotation processing slows the build loop | Low × Low | Accepted |
| TR-09 | Test discipline abandoned under deadline (inherits R-05) | High × High | Merge tests port directly from SP-05 on day one — the cheapest possible start |

---

## H. Architecture compatibility check

| # | Check | Verdict | How this stack satisfies it |
|---|---|---|---|
| 1 | **Offline field app works** | ✅ | Native Kotlin + Room: every action is a local transaction. No network call on any critical path (AD-02). Nothing in the stack introduces one |
| 2 | **SQLite/local persistence works** | ✅ *pending SP-04* | Room provides the single transaction spanning event write, seq allocation and outbox insert that AD-10 requires. Durability claim unproven until SP-04 |
| 3 | **REST works** | ✅ | FastAPI serves ingestion, delta, queries, export and audit — the only durable-write entry point (`06` §10.2) |
| 4 | **MQTT works** | ✅ *pending SP-06* | Mosquitto + `aiomqtt` publisher + `mqtt.js` subscriber. Publishing is post-commit only; the broker has no write path to Postgres, preserving AD-15 |
| 5 | **MQTT gap recovery works** | ✅ *pending SP-06* | `server_seq` is a Postgres monotonic identity column, included in every published message; the dashboard compares against `last_applied_server_seq` and calls the REST delta endpoint on a gap (AD-16, AD-17) |
| 6 | **SMS isolated behind the transport interface** | ✅ | `SmsManager` access and the codec live only in the `SmsTransport` and codec modules. The sync layer sees `max_batch_bytes`, a generic capability. **D-02a can be resolved without touching anything above the transport interface** (AD-07) |
| 7 | **PostgreSQL supports the event model** | ✅ | Composite primary key `(device_id, seq)` gives idempotent ingestion by construction; a monotonic identity column gives `server_seq`; `JSONB` carries event payloads; append-only with no UPDATE or DELETE on the event table |
| 8 | **Dashboard recovers missed MQTT messages** | ✅ *pending SP-06* | REST snapshot on load, `mqtt.js` live, gap check → REST delta, fresh snapshot on long disconnect (`06` §11) |
| 9 | **Android supports required native capabilities** | 🟡 **partially validated 2026-08-24** | `SmsManager` **text** send/receive validated on two handsets and two carriers (A→B 10/10, B→A 8/10, `segments=1`). **Port-addressed binary FAILS** — 10/10 `GENERIC_FAILURE` (`05` §1.2a). Text is the ratified path (T-23) |
| 10 | **Automated tests reproduce sync/merge scenarios** | ✅ | pytest carries `04` §3.2's 13 convergence assertions directly — partition, reunion, duplicate delivery, out-of-order, clock skew, and the D-01b duplicate-search scenario. JUnit5 covers codec round-trip and outbox state machine with no emulator. Vitest covers gap detection |

**Nothing in this stack alters `06`.** Every choice implements an existing contract; none changes one.

---

## I. What happens next

Implementation has **not** begun and no folders, code or dependencies exist. Before it starts:

1. **Install Android Studio** (TR-01 — blocks the most).
2. ~~Run **SP-01b-A**~~ ✅ **done 2026-08-24** — closed T-23/D-02a. ~~**SP-04**~~ ✅ **done** — closed T-03 (TR-19, 5/5 physical-device cycles). Still to run: **SP-06**, **SP-03** — they close T-10 and T-14.
3. Confirm this stack, or name substitutions.

On your approval the next deliverable is an **implementation plan** for the Spine's eleven elements in the build order fixed in `05` §3 — still not code.
