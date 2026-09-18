# RescueNet AI — Implementation Plan

**Date:** 2026-08-22 · **Stage:** Implementation readiness · **Target:** Minimum Demonstrable Spine (D-03)
**Contract:** [`01`](01-requirements-analysis.md)–[`11`](11-test-strategy.md), all approved. **This document adds no design.** It sequences work already specified.

> **No application code, no UI, no migrations, no endpoints, no Android activities were created.** This is a plan and an assessment.

---

## 1. Repository inspection (Task 1)

### 1.1 Current state

| Item | Finding |
|---|---|
| **Git repository root** | **`/Users/krish` (the home directory) — not the project.** `.git` exists at `$HOME`; there is none in `RescueNet/` |
| **Commits** | **0** |
| **Tracked files** | **0** |
| **RescueNet under version control** | **None.** 20 files and 5,995 lines of approved specification exist on disk only |
| `.gitignore` | Absent, at both project and home level |
| Existing source | **None** — no application code of any kind |
| Existing dependency manifests | **None** — no `package.json`, `requirements.txt`, `pyproject.toml`, or Gradle files |
| Existing spike code | `spikes/` — 4 Python scripts, 1 Kotlin spike app, 2 READMEs. **Preserve** |
| Existing test code | **None** beyond the spikes. `sp05_merge_convergence.py` becomes the seed for TR-16/TR-17 |
| Existing documentation | `docs/01`–`docs/11`, 5,995 lines. **Preserve** |

### 1.2 Two findings that block M0

**B-1 · The git repository is rooted at the home directory.**
`git rev-parse --show-toplevel` returns `/Users/krish`. Consequences:

- The entire approved specification — 5,995 lines representing the whole project to date — is **protected by nothing**. There is no commit, no history, no recovery point.
- A `git add .` from this directory would attempt to stage **~32 home-directory entries** including `.claude.json`, `.gitconfig`, `.zsh_history`, `Documents/`, `Downloads/` and `Library/`. Some contain credentials.

This must be corrected before any commit. It is not a code problem and it is quick to fix (§7), but it is genuinely urgent: the most valuable artefact in the project is currently a single accidental `rm` away from being gone.

**B-2 · Docker is not installed.** T-20 selects Docker Compose with three services (`backend`, `postgres`, `mosquitto`). Without it there is no PostgreSQL and no Mosquitto, so M0 cannot deliver its environment and every integration (`I`) test from M3 onward cannot run.

### 1.3 Nothing was deleted
No file was removed or modified during inspection. All feasibility evidence and documentation is intact.

---

## 2. Toolchain verification (Task 3)

**Nothing was installed.**

| Tool | Status | Version | Needed for |
|---|---|---|---|
| **Python** | ✅ AVAILABLE | 3.12.10 | M1–M5, M10 backend; pytest |
| **pip** | ✅ AVAILABLE | 25.0.1 | Backend dependencies |
| **uv** | ⚪ MISSING | — | **Not required.** Optional pip alternative; not in `07` |
| **Node.js** | ✅ AVAILABLE | 24.18.0 | M11 dashboard |
| **npm** | ✅ AVAILABLE | 11.16.0 | M11 dashboard |
| **Java / JDK** | ✅ AVAILABLE | 26.0.2 | Necessary but **not sufficient** for Android |
| **Git** | ✅ AVAILABLE | 2.50.1 | All milestones — **but see B-1** |
| **Docker** | ❌ **MISSING** | — | **M0 blocker.** Postgres + Mosquitto (T-06, T-09, T-20) |
| **Docker Compose** | ❌ **MISSING** | — | Ships with Docker Desktop |
| **Android Studio** | ❌ MISSING | — | M6–M9, M12; spikes SP-01b-A, SP-02, SP-04 |
| **Android SDK** | ❌ MISSING | — | As above |
| **adb** | ❌ MISSING | — | As above |
| **Gradle** | ❌ MISSING | — | Ships with Android Studio |
| **Kotlin** | ❌ MISSING | — | Ships with Android Studio |
| **PostgreSQL CLI** | ⚪ MISSING | — | **Not required** — Postgres runs in Compose |

**Assessment.** The backend and dashboard toolchains are complete apart from Docker. The Android toolchain is entirely absent — this is **TR-01**, flagged as the largest schedule risk since `07`, and it is still open.

---

## 3. Repository structure proposal (Task 4)

**Not created.** Proposed for approval.

```
RescueNet/
├── .gitignore                      # NEW — required before first commit
├── README.md                       # NEW — entry point, links to docs/
│
├── docs/                           # PRESERVED — 01..12, the project contract
│
├── spikes/                         # PRESERVED — throwaway, excluded from build & CI
│   ├── sp01a_codec_budget.py       #   evidence artefacts; never imported by src
│   ├── sp01b_manual_payloads.py
│   ├── sp05_merge_convergence.py   #   seed for TR-16/TR-17, to be rewritten not copied
│   └── android-sms-spike/
│
├── backend/                        # M1–M5, M10 — modular monolith, single deployable
│   ├── pyproject.toml
│   ├── src/rescuenet/
│   │   ├── domain/                 # M2 — events, merge rules. NO sql, NO http, NO mqtt
│   │   ├── store/                  # M3 — event append, dedup, server_seq
│   │   ├── projections/            # M3 — read models, all rebuildable
│   │   ├── api/                    # M4 — REST only
│   │   ├── auth/                   # M5 — tokens, HMAC verification
│   │   ├── mqtt/                   # M10 — publisher only, post-commit
│   │   └── config/
│   ├── migrations/                 # M3 — Alembic. NOT created yet
│   └── tests/{unit,integration}/
│
├── mobile/                         # M6–M9, M12 — Android Studio project
│   └── app/src/{main,test,androidTest}/kotlin/…/
│       ├── domain/                 # mirrors backend domain semantics
│       ├── store/                  # M6 — Room, event log + outbox
│       ├── sync/                   # M7 — outbox engine, transport interface
│       ├── transport/              # M8 — InternetTransport, SmsTransport
│       ├── codec/                  # M8 — ALL wire/SMS knowledge lives here
│       ├── gateway/                # M9 — gateway mode
│       └── ui/                     # M12 — LAST
│
├── dashboard/                      # M11 — React + Vite + TS
│   ├── package.json
│   └── src/{api,mqtt,map,views}/
│
├── shared/
│   ├── fixtures/                   # canonical event JSON, consumed by ALL THREE
│   │                               #   test suites — one source, no drift
│   └── openapi/openapi.json        # generated from FastAPI, committed
│
├── deploy/
│   ├── docker-compose.yml          # backend + postgres + mosquitto
│   └── mosquitto/{mosquitto.conf,passwd,acl}   # static creds + ACL, AP-23
│
└── tests/contract/                 # M13 — cross-component scenario tests
```

**Two structural choices worth stating:**

- **`shared/fixtures/`** holds the canonical event examples from `08` Part 16 as real JSON files, consumed by pytest, JUnit and Vitest alike. Three independently-written fixture sets would drift; one cannot. This directly mitigates audit finding F-13.
- **`spikes/` is excluded from every build and CI path.** It is evidence, not source. Per `spikes/README.md`, nothing there may be copied into `src` — it is rewritten from the requirements.

---

## 3.1 Reference-table ownership (added 2026-08-23 — closes an M3 review gap)

`08` §11.1 specifies four **reference and credential tables** alongside `event`, but
earlier revisions of this plan assigned them to **no milestone at all**. The M3 contract
review surfaced that as the reason `event.incident_id` had no foreign key. Ownership is
now fixed here so the ambiguity cannot recur.

| Table | Owning milestone | Why there | Status |
|---|---|---|---|
| `incident` | **M4** | M4 owns `POST /v1/incidents` (`09` endpoint 3), which is what creates incidents. The table has no writer before M4 | Not created |
| `agency` | **M4** | Seeded reference data consumed by `POST /v1/teams` (`09` endpoint 5) | Not created |
| `resource_item` | **M4** | Seeded catalogue consumed by the snapshot (`09` endpoint 9) | Not created |
| `device_credential` | **M5** | M5 owns enrolment, tokens and HMAC secrets. **Never in the event log** (DM-11) | Not created |

**`event.incident_id` foreign key.** `08` §11.1 specifies `incident_id | int | FK → incident`.
M3 created the column as a plain indexed integer because its target table did not exist.
**The foreign key is added in the M4 reference-table migration, once `incident` exists** —
not by a new M3 migration. Until then `incident_id` carries no referential integrity, which
is recorded as a known, time-boxed gap rather than an accepted limitation.

**Nothing here moves existing functionality between milestones.** M3's deliverables are
unchanged; these tables were simply never assigned, and now are.

---

## 3.2 Endpoint ownership: M4 vs M5 (added 2026-08-23 — closes a docs/12 conflict)

Earlier revisions gave M4 "all 14 endpoints" while simultaneously giving M5 "enrolment
issuing `device_id`, opaque token, HMAC secret" and "session login returning the configured
MQTT block" — which **are** endpoints 1 and 2. TR-33 was listed under both milestones. The
conflict is resolved as follows and this assignment is final.

| # | Method + path | Owner | Why |
|---|---|---|---|
| 1 | `POST /v1/enrol` | **M5** | Issues `token` and `hmac_secret`, which live in `device_credential` — an M5 table |
| 2 | `POST /v1/auth/session` | **M5** | Session authentication |
| 3 | `POST /v1/incidents` | **M4** | Operational |
| 4 | `POST /v1/incidents/{id}/grid` | **M4** | Operational |
| 5 | `POST /v1/teams` | **M4** | Operational |
| 6 | `POST /v1/teams/{id}/join-code` | **M5** | Mints join codes consumed by endpoint 1; needs join-code storage |
| 7 | `POST /v1/events` | **M4** | Operational |
| 8 | `GET /v1/events` | **M4** | Operational |
| 9 | `GET /v1/incidents/{id}/snapshot` | **M4** | Operational |
| 10 | `POST /v1/assignments` | **M4** | Operational |
| 11 | `DELETE /v1/assignments/{id}` | **M4** | Operational |
| 12 | `GET /v1/incidents/{id}/export` | **M4** | Operational |
| 13 | `GET /v1/diag/sync` | **M4** | Operational |
| 14 | `GET /health` | **M4** | Delivered at M1; unchanged |

**M4 = 11 endpoints (3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14). M5 = 3 endpoints (1, 2, 6).**

**Supporting artefacts:** `device_credential` → M5 · join-code storage → M5 (`08` §11.1a) ·
`incident`, `agency`, `resource_item` → M4 (§3.1). **TR-33 has exactly one owner: M5.**

### 3.2.1 Transitional security state — M4 endpoints ship unauthenticated

`09` §1.1 assigns an `Auth` requirement to 13 of the 14 endpoints, and `09` §1.2 endpoint 9
additionally specifies role-constrained `AuthZ`. **`09` Part 8, which defines the
authentication model, is an input to M5 — not to M4.**

Consequently the 11 endpoints M4 delivers are implemented **without authentication or
authorization enforcement**. This is recorded here explicitly so it cannot be mistaken for
an oversight or for an accepted limitation:

- It is a **transitional state of the build**, not a design decision.
- **The documented authentication requirements in `09` §1.1 and Part 8 are unchanged.**
  Nothing has been weakened, relaxed or reinterpreted.
- **M5 must enforce them on every endpoint M4 delivered.** That is an M5 completion
  criterion, not an optional extra.
- **The system is not production-ready until M5 closes this.** Any demonstration between
  M4 and M5 runs an open API and must be described as such.

---

## 3.3 Security-artefact ownership: M5 vs M8 (added 2026-08-23)

The M5 readiness review found that batch MAC verification cannot be built at M5: the MAC
covers **packed SMS wire bytes**, and the canonical encoding is the M8 codec. Splitting
issuance from verification resolves it without weakening either.

| Artefact | Owner | Note |
|---|---|---|
| `device_credential` table (incl. `role`) | **M5** | DM-44, `08` §11.1b |
| `join_code` table and semantics | **M5** | DM-45, `08` §11.1a |
| Opaque token issuance + `SHA-256` storage | **M5** | DM-43 |
| **`hmac_secret` generation and recoverable storage** | **M5** | DM-47 |
| Session semantics — 24 h TTL, no refresh | **M5** | DM-46, AP-17 |
| `incident.password_hash` | **M5** | DM-48 — `hashlib.scrypt`, n=2^14 r=8 p=1 |
| `device_credential.incident_id` + surrogate PK | **M5** | DM-50 — commander session scope |
| Bootstrap incident provisioning | **Operational, not M5 API** | DM-52 — out-of-band tool; no endpoint |
| `responder_id` / `agency_id` on enrolment | **Provisional** | DM-53 — temporary defaults, future decision |
| Authentication + authorization on all M4 endpoints | **M5** | `09` §1.1, Part 8 |
| **Canonical wire encoding (codec)** | **M8** | AD-07 |
| **Batch MAC verification + TR-10** | **M8** | DM-49 |

**Dependency direction: M8 → M5.** M8 verifies MACs using secrets M5 issued. M5 has no
dependency on M8 and must not wait for it.

**TR-10 is intact.** Its specification in `11` is unchanged; only its owning milestone
moved, because its precondition lives there.

**Transitional gap until M8 (DM-51).** `FIELD` credentials are bound to their own
`device_id`, but `GATEWAY`-relayed events have **unverified author authenticity** because
the MAC needs the M8 codec. Disclosed, bounded, and closed by M8 — not worked around.

---

## 3.4 Outbox ownership: M6 vs M7 (added 2026-08-23 — closes an M6 preflight ambiguity)

The M6 preflight found that M6 and M7 both appear to touch the outbox: M6's outputs name the
Room schema "incl. the four rejection columns", while M7's outputs name the "outbox state
machine (`PENDING`/`IN_FLIGHT`/`ACKED`/`REJECTED`)". Read together these look like a conflict.
They are not — the split is **representation versus behaviour**, and it is recorded here so no
implementation has to infer it.

| Concern | Owner | Note |
|---|---|---|
| Room representation of the 12-column outbox | **M6** | `08` §6.1 — the columns, types and keys |
| Persisted representation of `PENDING` · `IN_FLIGHT` · `ACKED` · `REJECTED` | **M6** | The enum and its storage. Representation only |
| The four AP-14 rejection columns (`rejected_code`, `rejected_message`, `rejected_at`, `rejected_batch_ref`) | **M6** | `08` §6.1, **DM-39** — outbox metadata, never on the event |
| Local event log row shape | **M6** | `08` §12.2, **DM-54** |
| Persisted per-device `seq` counter | **M6** | `06` §4.2 — gaps legal, reuse not |
| Atomic write of event + `seq` allocation + outbox row in **one transaction** | **M6** | **AD-10**, `06` §5.1, §5.2 — this is TR-19 / SP-04 |
| Outbox **transition behaviour** — the state machine itself | **M7** | `08` §6.2 |
| Retry and backoff (persisted `attempt_count`, `next_attempt_at`) | **M7** | `08` §6.3; values in §6.3.1, **DM-56** |
| Two-tier priority and drain order | **M7** | D-04, `06` §5.3, AD-09 |
| Transport interface and `InternetTransport` | **M7** | `06` §7 |
| **Restart recovery `IN_FLIGHT` → `PENDING`** | **M7** | `08` §6.2 note; M7 completion criteria state it explicitly |
| ACK and REJECT processing | **M7** | `09` Parts 2–3, **AP-14** |
| Delta application and the `last_applied_server_seq` watermark | **M7** | `06` §5.4, `08` §12.1. Storage and atomicity now fixed by **`08` §12.3 / DM-55** — a Room `sync_state` table, advanced **in the same transaction as the delta** |
| Bit-packed codec, `base_seq`/`base_t` header, framing, truncated MAC, `SmsTransport` | **M8** | `08` Parts 9–10, AD-07, DM-49 |

**The M6/M7 line, stated once:** M6 makes the outbox **exist and be writable atomically**;
M7 makes it **move**. A milestone that stores a state value does not thereby own the rules
for entering or leaving it.

**Restart recovery stays in M7.** `IN_FLIGHT` → `PENDING` on start is a transition, it is
named in M7's completion criteria, and it is untestable without the sending path M7 builds —
nothing can be `IN_FLIGHT` before a transport exists. **M6 does not implement it.**

**The watermark stays in M7 — and is now fully specified.** `last_applied_server_seq`
appeared in `06` §5.4 and `08` Parts 4 and 12 as a value with no device-side storage location;
the M7 preflight raised that as a blocker. **`08` §12.3 (DM-55)** closes it: a dedicated Room
`sync_state` table, with the watermark advance required to occur **in the same transaction
that applies the delta events**, so the two commit together or not at all. M6 neither creates
nor reads that table.

**CRITICAL backoff is now specified too.** `08` §6.3 said only that `CRITICAL` uses "a shorter
base and a lower cap". **`08` §6.3.1 (DM-56)** fixes the numbers — Internet 1 s/60 s, SMS
10 s/5 min, with `ROUTINE` unchanged at 2 s/5 min and 60 s/30 min. Both were M7 blockers; both
are closed. Neither changes M6.

**TR ownership is unchanged.** TR-19 and TR-20 remain exactly as `11` specifies them, at
level **D — Instrumented**. TR-19 remains M6's test and remains SP-04. TR-20 is listed under
both M6-adjacent offline coverage and M7; `11` is authoritative and is not modified here.

---

## 3.5 Android toolchain versions — **M6 implementation decision** (added 2026-08-23)

No document previously pinned any Android build version. The M6 preflight established that
`07` T-01/T-02/T-03 fix the *technologies* (Native Android · Kotlin · Room) and `01` NFR-11
fixes the *floor* (Android 8+), but compileSdk, AGP, Gradle, Kotlin, KSP and Room versions
were undeclared. They are chosen here as an explicit M6 implementation decision.

**Every value below was verified by building, not by reading release notes.**

| Setting | Value | Basis |
|---|---|---|
| `minSdk` | **26** | `01` NFR-11 — "Android 8+, 2 GB RAM". The only version derivable from an existing requirement |
| `compileSdk` | **37** | `android-37.0` is the installed platform; `build-tools 37.0.0` present |
| `targetSdk` | **37** | Matches `compileSdk` |
| **Android Gradle Plugin** | **9.3.1** | Latest stable |
| **Gradle** | **9.7.1** | **AGP 9.3.1 refuses anything below 9.5.0** — see below. 9.7.1 is the current stable release |
| **Kotlin** | **2.3.20** | The Kotlin that KSP 2.3.11 is built against — `symbol-processing-api` 2.3.11 declares `kotlin-stdlib` **2.3.20**. KGP 2.2.21 fails against AGP 9's DSL — see below |
| **KSP** | **2.3.11** | Latest. Pairs with Kotlin 2.3.20 by its own declared dependency. Room's compiler is a KSP processor, so KSP is not optional |
| **Room** | **2.8.4** | Latest stable |
| **JDK** | **Studio JBR 25.0.2** | `/Applications/Android Studio.app/Contents/jbr/Contents/Home`. The system JDK 26 is **excluded** — AGP does not support it |

### Three constraints found by building, not by reading

1. **AGP 9.3.1 requires Gradle ≥ 9.5.0.** An initial pin to Gradle 9.3.1 — chosen because
   Gradle 9.3.1 *embeds* Kotlin 2.2.21 and Studio 2026.1 ships `gradle-api-9.3.0` — was
   rejected outright by `com.android.internal.version-check`. The wrapper was repinned to
   9.7.1. **This is why the version record is written after verification, not before it.**

2. **AGP 9.0+ ships built-in Kotlin, and it is incompatible with KSP.** Applying
   `org.jetbrains.kotlin.android` alongside it fails; removing it then fails with
   *"KSP is not compatible with Android Gradle Plugin's built-in Kotlin."* AGP prescribes the
   remedy, and `gradle.properties` carries it: **`android.builtInKotlin=false`** plus the
   explicit Kotlin plugin. Room's compiler is a KSP processor, so KSP is not negotiable here.

3. **KGP is not yet compatible with AGP 9's new DSL.** With `android.newDsl=true` (the AGP 9
   default) the Kotlin plugin fails casting `ApplicationExtensionImpl` to `BaseExtension`.
   AGP's own message offers **`android.newDsl=false`** as the supported bypass, and
   `gradle.properties` carries it. This is a transition-period setting: it should be removed
   once KGP supports the new DSL, and it is recorded here so that removal is not forgotten.

### Why not the newest of everything, and why not what Studio ships

Kotlin 2.2.21 was tried first, because Gradle 9.3.1 embeds exactly that version and KSP
`2.2.21-2.0.5` names it — the strongest metadata pairing available. It failed against AGP 9's
DSL, so the pairing argument was overridden by an empirical one. KSP releases from 2.3.0
onward moved to independent versioning and no longer encode the Kotlin version they bind to,
so **Kotlin 2.3.20 ↔ KSP 2.3.11 rests on a successful KSP run over the Room entities, not on
version arithmetic.** Kotlin 2.4.10 also configured successfully, but 2.3.20 is the
version KSP 2.3.11 actually declares a dependency on, so it is the pairing with evidence
behind it rather than merely the absence of a failure.

Studio 2026.1 ships no runnable Gradle distribution, only the tooling-API client. Gradle
9.7.1 was fetched from `services.gradle.org`, SHA-256 verified against two independent Gradle
endpoints, and pinned in the wrapper with `distributionSha256Sum`. The wrapper jar's own
SHA-256 matches Gradle's published `gradle-9.7.1-wrapper.jar.sha256`.

### Test-library alignment — `kotlinx-coroutines-test` 1.9.0

Not part of the toolchain above, recorded because it changed during M6 verification. The
androidx test artefacts drag in `kotlinx-coroutines-bom` which pins `coroutines-core` to
**strictly 1.9.0**, while `coroutines-test` resolved to 1.11.0. Every instrumented test that
used `runTest` then died with `NoSuchMethodError: runBlockingK$default` — 18 of 28 — before
reaching a single assertion. Pinning `coroutines-test` to **1.9.0** matches the BOM and all 28
pass. No AGP, Gradle, Kotlin, KSP, Room or SDK version was touched.

### M7 additions — recorded after verification (added 2026-08-23)

Two facts established while implementing M7. Both are recorded here because they are now part
of how the `mobile/` project builds and runs; neither changes any value in the table above.

#### `kotlinx-serialization-json` 1.11.0

| | |
|---|---|
| **Library** | `org.jetbrains.kotlinx:kotlinx-serialization-json` **1.11.0** |
| **Gradle plugin** | `org.jetbrains.kotlin.plugin.serialization`, **at the existing Kotlin version 2.3.20** — no new toolchain pin |
| **Approval** | **Not a new dependency.** `07` row 13 and **T-16 (FINAL)** already name `kotlinx.serialization` as the mobile validation/schema technology, and §4 below lists it in the approved **Mobile** row |
| **Used by** | `sync/JsonBatchCodec.kt` — the `09` §2.2 request, §2.3 verdict and §3.4 delta envelopes |

**Why it was adopted mid-M7.** The codec was first written against Android's framework
`org.json`. That was a deviation: `org.json` appears nowhere in the §4 approved table, while
T-16 names `kotlinx.serialization`. It also failed silently — on the JVM unit-test classpath
`org.json` is a stub, and with `unitTests.isReturnDefaultValues = true` it returns empty
results instead of throwing, so three parser tests passed without parsing anything. Switching
to the ratified library fixed the deviation and made those tests real.

**Still not the wire codec.** The bit-packed encoding, `base_seq`/`base_t` batch header, SMS
framing and truncated MAC remain **M8** (`08` Parts 9–10, AD-07, DM-49). T-16 already says the
wire codec is *"hand-written bit-packing, no library"*; `kotlinx.serialization` serves the
JSON/HTTPS path only.

#### Android manifest permissions — M7 owns `INTERNET`

| Permission | Milestone | Reason |
|---|---|---|
| `android.permission.INTERNET` | **M7** | `InternetTransport` performs the HTTPS batch POST and delta pull of `06` §7.2. Without it the transport cannot make a single call |
| `android.permission.ACCESS_NETWORK_STATE` | **M7** | Backs the `available` flag of `TransportCapabilities`, which `06` §7.3 rule 1 selects on |
| **`SEND_SMS` / `RECEIVE_SMS` / `READ_SMS`** | **M8 — deliberately absent** | `SmsTransport` is M8 (`12` §3.4). M7 declares **no SMS permission**, and the manifest is the mechanical proof of that boundary |

M6 declared none at all. **This does not weaken TR-20 or AD-02**: `06` §5.2's *"No network
call exists on this path"* is a property of the local write path, which still holds no
transport reference, and TR-20 is verified on the physical handset with radios disabled.
Holding a permission and making a call on the critical path are different things.

### Scope

These values govern the `mobile/` Gradle project only. They change no backend behaviour, add
no API surface, and are not part of any wire or data contract.

## 4. Dependency policy (Task 5)

**Only technologies already approved in [`07`](07-technology-selection.md).** Adding anything else requires amending `07` first.

| Layer | Approved | ID |
|---|---|---|
| Backend | Python · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · `aiomqtt` (provisional, `paho-mqtt` fallback) | T-04, T-05, T-08, T-10, T-16 |
| Database | PostgreSQL — **no PostGIS** | T-06, T-07 |
| Broker | Eclipse Mosquitto | T-09 |
| Mobile | Kotlin · Android SDK · Room · `kotlinx.serialization` <br/>*resolved: Kotlin 2.3.20 · Room 2.8.4 · `kotlinx-serialization-json` 1.11.0 — see §3.5* | T-01, T-02, T-03, T-16 |
| Dashboard | React · Vite · TypeScript · Tailwind · MapLibre GL JS (provisional) · `mqtt.js` | T-11–T-14 |
| Testing | pytest · pytest-asyncio · httpx · JUnit5 · Robolectric · Vitest | T-17 |
| Docs | FastAPI OpenAPI · `openapi-typescript` | T-18 |
| Env | Docker Compose | T-20, T-21 |

**Forbidden, as instructed:** Kubernetes · microservices · Redis · Elasticsearch · GraphQL · PostGIS at Level 1 · CRDT frameworks · UI component libraries · any additional message broker · cloud services beyond a single host.

**Rule:** a dependency not in the table above does not get added without an explicit amendment to `07`. "It was easier" is not an amendment.

---

## 5. Critical implementation constraints (Task 6)

Each constraint, where it is enforced, and the test that guards it. A constraint with no guard is a constraint that erodes.

| # | Constraint | Enforced in | Guarded by |
|---|---|---|---|
| 1 | PostgreSQL event store is authoritative | M3 — `store/`; no other component writes truth | TR-14, TR-30 |
| 2 | Domain events are immutable | M3 — app role has `INSERT`/`SELECT` only, **no `UPDATE`/`DELETE`** | TR-30 |
| 3 | `(device_id, seq)` is event identity | M2 — composite PK; M7 — allocation inside the write txn | TR-08, TR-22 |
| 4 | `server_seq` is acceptance order, **never causal** | M3 — folds use `server_seq`; `t_dev` never orders | TR-23 |
| 5 | MQTT is notification-only | M10 — publisher module only; no subscriber in backend | TR-14 |
| 6 | MQTT cannot mutate authoritative state | M10 — no broker→store path exists; ACL is subscribe-only for clients | TR-14, TR-15 |
| 7 | Gap detection → REST delta recovery | M10 + M11 — `server_seq` on every message | TR-13 |
| 8 | SMS is transport-only | M8 — `transport/` + `codec/`; nothing above imports them | TR-25, TR-26 |
| 9 | SMS codec is transport-agnostic at the sync layer | M7 — sync sees `max_batch_bytes`, never "SMS" | TR-24, TR-25 |
| 10 | Offline events durable until acknowledged | M6 — single transaction; M7 — outbox | TR-19, TR-20 |
| 11 | Duplicate delivery idempotent | M3 — `ON CONFLICT DO NOTHING`, repeats reported accepted | TR-08 |
| 12 | `REJECTED` is delivery metadata, not deletion | M7 — outbox columns only; event untouched | TR-01, TR-02 |
| 13 | `UNKNOWN_CELL` never loses a CRITICAL survivor report | M3/M4 — severity partition (AP-20) | **TR-06** |
| 14 | `GRID_GENERATED` is parametric | M2 — one event; cells derived | TR-12 |
| 15 | `MAX_CELLS` = 8,191 | M2 — constant; M4 — `422` above it | **TR-11** |
| 16 | NFR-09 target remains 5,000 cells | M14 — synthetic load figure, distinct from the maximum | SP-03 |
| 17 | Gateway relays, never authors | M9 — attribution passed through unchanged | **TR-09** |
| 18 | Dashboard never becomes source of truth | M11 — no local store; snapshot+delta only | TR-14, TR-29 |
| 19 | **Reference tables have one owning milestone** — `incident`, `agency`, `resource_item` at **M4**; `device_credential` at **M5** | §6 M4/M5 outputs | migration presence at each milestone |

---

## 6. Milestones (Task 2)

Dependencies are strict: a milestone may not start until its dependencies are complete.

### M0 — Repository and toolchain setup
- **Inputs:** this document; `07` stack; `11` test policy
- **Outputs:** `git init` at the **project** root; `.gitignore`; directory skeleton (§3); `docker-compose.yml` with the three services; Mosquitto config with static password file and ACL; `README.md`; first commit of the existing specification
- **Dependencies:** none
- **Tests:** `docker compose up` brings all three services healthy; Mosquitto ACL loads
- **Requirements / decisions:** T-20, T-21, T-09, **AP-23**
- **Completion criteria:** repo rooted at `RescueNet/`; specification committed; `docker compose up` succeeds; broker accepts the publisher account and refuses a dashboard publish
- **Status:** **BLOCKED — B-1 and B-2 (§7)**

### M1 — Backend foundation
- **Inputs:** M0 skeleton
- **Outputs:** FastAPI application; modular package layout enforcing `06` §3 dependency direction; configuration; structured JSON logging; `/health`; pytest harness with fixtures wired to `shared/fixtures/`
- **Dependencies:** M0
- **Tests:** `/health` returns service status; an import-direction test asserting `domain/` imports nothing from `api/`, `store/`, `mqtt/` or `transport/`
- **Requirements / decisions:** T-04, T-05, T-19; **AD-03** layering
- **Completion criteria:** app starts; health green; layering test passes in CI

### M2 — Canonical event model
- **Inputs:** `08` Parts 1–3
- **Outputs:** Pydantic models for the canonical event and all 11 types; `MAX_CELLS` constant; parametric grid derivation (`cell_index ↔ row/col ↔ label ↔ bounds`); priority derived from type; validation codes from `09` §2.6
- **Dependencies:** M1
- **Tests:** **TR-12** parametric grid · **TR-22** identity · **TR-31** attribution completeness · **TR-11** (index range half)
- **Requirements / decisions:** FR-203, FR-204, FR-1002; DM-01…DM-12, DM-36, **AP-20** partition
- **Completion criteria:** every `08` Part 16 fixture round-trips; grid derivation exact at 0 and 8,190; no canonical field added or removed
- **Status:** **COMPLETE (2026-08-23).** The cell label formula was found unspecified during implementation and is now fixed in docs/05 §10; `docs/08` §16.6 carried an arithmetically impossible `B-14`/`214` pairing, corrected there.

### M3 — Event store and merge engine
- **Inputs:** M2; `08` Parts 7, 11
- **Outputs:** append-only `event` table; `server_seq` identity column; dedup on `(device_id, seq)`; the six fold rules; read models incl. `coverage_metrics`; rebuild-from-empty; Alembic migrations; `INSERT`/`SELECT`-only grant
- **Dependencies:** M2, M0 (Postgres)
- **Tests:** **TR-08** idempotency · **TR-16** convergence (13 assertions) · **TR-17** duplicate search · **TR-18** commutativity · **TR-23** ordering · **TR-29** coverage single fold · **TR-30** append-only · **TR-32** audit reconstruction
- **Requirements / decisions:** FR-806, FR-1001, FR-1002; AD-01, AD-04, AD-14, AD-27, **AP-24**
- **Completion criteria:** all six folds deterministic; projections rebuild identically from empty; `UPDATE`/`DELETE` refused by the database

### M4 — REST API
- **Inputs:** M3; `09` Parts 1–3, 9
- **Outputs:** the **11 operational endpoints — 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14** of `09` §1.1; partial batch acceptance; error contract; delta pagination; snapshot with positional `cell_state`; GeoJSON/CSV export; OpenAPI committed to `shared/openapi/`; **the `incident`, `agency` and `resource_item` reference tables (`08` §11.1) and the `event.incident_id` foreign key**
- **Explicitly NOT M4:** endpoints **1** (`POST /v1/enrol`), **2** (`POST /v1/auth/session`) and **6** (`POST /v1/teams/{id}/join-code`) — see §3.2
- **Dependencies:** M3
- **Tests:** **TR-05**, **TR-06** (CRITICAL carve-out) · **TR-07** partial acceptance · **TR-21** cursor determinism · **TR-27** snapshot economy · **TR-28** assignment collision · **TR-34** export.  *(TR-33 enrolment moved to M5 — it tests endpoint 1, which M4 does not own.)*
- **Requirements / decisions:** FR-301, FR-303, FR-802, FR-901, FR-902, FR-905; **AP-01…AP-07, AP-20, AP-22**
- **Completion criteria:** the 11 operational endpoints match `09`; OpenAPI exposes exactly those 11 and no M5 endpoint; every applicable example in `09` Part 11 reproduces exactly; `event.incident_id` is a live foreign key to `incident`

### M5 — Authentication and authorization
- **Inputs:** M4; `09` Part 8, `06` §14
- **Outputs:** endpoints **1** (`POST /v1/enrol`), **2** (`POST /v1/auth/session`) and **6** (`POST /v1/teams/{id}/join-code`); **credential issuance and storage** — `device_id` (from **1**, 0 reserved), opaque token persisted as `SHA-256` (DM-43), recoverable `hmac_secret` (DM-47), persisted `role` (DM-44); **join-code semantics** (DM-45); **session semantics** — 24 h TTL, no refresh (DM-46); `incident.password_hash` (DM-48); session login returning the configured MQTT block; **the `device_credential` table** (`08` §11.1b, DM-11) and **`join_code`** (`08` §11.1a); **authentication and authorization enforcement across every endpoint delivered in M4**
- **Explicitly NOT M5:** **batch MAC verification and TR-10** — the MAC covers packed wire bytes, so it needs the canonical codec and is owned by **M8** (DM-49). M5 issues and stores the `hmac_secret` M8 verifies against
- **Dependencies:** M4
- **Tests:** **TR-33** non-idempotent enrolment · **TR-22** reserved id range.  *(TR-10 moved to M8 — DM-49.)*
- **Requirements / decisions:** FR-104, FR-105, FR-106, FR-908; **AP-02, AP-16, AP-17, AP-23**
- **Completion criteria:** a `FIELD` token cannot upload another device's events; **every `Auth`/`AuthZ` requirement in `09` §1.1 and Part 8 is enforced on the M4 endpoints**; a revoked credential is refused at next contact.  *(The `GATEWAY`-batch-without-valid-MAC criterion moves to M8 with TR-10 — DM-49.)*

### M6 — Android local persistence
- **Inputs:** `08` Parts 5–6; T-01, T-03
- **Outputs:** Android project; Room schema for event log + outbox incl. the four rejection columns; single-transaction write of event + `seq` + outbox row
- **Dependencies:** M0, M2 (model parity), **Android toolchain**
- **Tests:** **TR-19** durability (force-kill, reboot, mid-transaction interrupt) — this is **SP-04**
- **Requirements / decisions:** NFR-07, FR-403; **AD-10**, DM-39
- **Completion criteria:** 100% of acknowledged writes survive five kill/reboot cycles
- **Status:** blocked on Android Studio

### M7 — Android event and outbox engine
- **Inputs:** M6; `08` Part 6; `09` Parts 2–3
- **Outputs:** outbox state machine (`PENDING`/`IN_FLIGHT`/`ACKED`/`REJECTED`); backoff persisted; two-tier priority; transport interface; `InternetTransport`; delta application and watermark
- **Dependencies:** M6, M4
- **Tests:** **TR-01**–**TR-04** · **TR-20** offline path · **TR-24** priority
- **Requirements / decisions:** FR-402, FR-404, FR-801, FR-808; **AD-02, AD-06, AD-08, AD-12, AP-14, AP-21, AP-22**
- **Completion criteria:** airplane-mode task set completes, survives kill and reboot, drains correctly on reconnect; `IN_FLIGHT` reverts to `PENDING` on start

### M8 — SMS codec and transport
- **Inputs:** M7; `08` Parts 9–10; `09` Part 6
- **Outputs:** bit-packed SMS codec for the **four SMS-eligible uplink event types** — `CELL_STATUS_REPORTED`, `SURVIVOR_REPORTED`, `RESOURCE_DELTA_REPORTED`, `TEAM_STATUS_REPORTED` (**SCOPE A**, ratified 2026-08-24, M8-6). The seven non-SMS types keep the existing JSON/HTTPS path, which already carries all eleven canonical types losslessly; **no SMS layout may be invented for them**. Batch header `base_seq`/`base_t`; framing + truncated MAC; `SmsTransport`; **encoding = GSM-7 text, `max_batch_bytes` 120 B — D-02a FINAL**. All bit widths are ratified in `09` §6.6 (**DM-57**) and must not be altered during implementation
- **Dependencies:** M7 ✅, ~~**SP-01b-A**~~ ✅ **executed 2026-08-24**, and **M5** ✅ — batch MAC verification consumes the `hmac_secret` M5 issues and stores (DM-49). **All satisfied.**
- **Tests:** **TR-11** max-index round-trip *(release-blocking)* · **TR-25** lossless round-trip · **TR-26** never truncates · **TR-12** · **TR-10** batch MAC verification *(moved from M5 — DM-49)*
- **Requirements / decisions:** PS-K5, NFR-01; **AD-07**, DM-23…DM-27, DM-38
- **Completion criteria:** every valid `cell_index` (0…8,190) round-trips with no collision; each of the four SCOPE-A types encodes within its `09` §6.6.7 budget; **no SMS knowledge above the transport interface** — verified by an import test

### M9 — Gateway mode
- **Inputs:** M8; `09` Part 7
- **Outputs:** gateway mode in the **same APK**; reassembly by `batch_id`; forward-queue surviving crash; HTTPS forward preserving original attribution; diagnostics
- **Dependencies:** M8, M5
- **Tests:** **TR-09** attribution preserved byte-identically · **TR-10** MAC pass-through
- **Requirements / decisions:** **D-06**, T-22; **AP-16**
- **Completion criteria:** relayed events are indistinguishable from direct ones except `received_via`; gateway with no internet buffers and later forwards

### M10 — MQTT notification and recovery
- **Inputs:** M3, M4; `09` Parts 4–5
- **Outputs:** post-commit publisher; `server_seq` on every message; `derived` block with `duplicate_search` and `coverage`; `retain: false`; static ACL verified
- **Dependencies:** M3, M0 (Mosquitto)
- **Tests:** **TR-13** gap recovery · **TR-14** cannot mutate state *(release-blocking)* · **TR-15** subscribe-only — this is **SP-06**
- **Requirements / decisions:** PS-K2; **AD-15, AD-16, AD-17, AP-09, AP-10, AP-12, AP-13, AP-23, AP-24**
- **Completion criteria:** publish is post-commit only; a direct topic publish changes no row; killing the broker leaves REST fully correct

### M11 — Commander dashboard
- **Inputs:** M4, M10; `06` §11
- **Outputs:** snapshot load; `mqtt.js` subscription; gap detection → REST delta; grid map with colour **plus** pattern; metrics strip fed only by `derived.coverage`; **data age on every marker**; duplicate-search visualisation; assignment console
- **Dependencies:** M4, M10
- **Tests:** **TR-13** client half · **TR-29** non-recomputing client stays correct
- **Requirements / decisions:** FR-701–706, FR-304, FR-705; **D-01**, AD-25, **AP-24**
- **Completion criteria:** MC-09's three questions answerable on one screen in under 30 s; broker down shows "live updates offline", never stale-as-fresh

### M12 — Field application UI
- **Inputs:** M7, M8; PI-07
- **Outputs:** three-tap flows for cell status, survivor report and inventory; offline grid view; persistent connectivity/queue header; `REJECTED` diagnostics view
- **Dependencies:** M7 *(deliberately last — the engine precedes the screens)*
- **Tests:** **TM-01** tap counts · **TM-02** gloves · **TM-03** contrast/targets
- **Requirements / decisions:** FR-407, FR-408, FR-410, NFR-04, NFR-05; **MC-05**
- **Completion criteria:** each critical action ≤3 taps, no typing, no blocking spinner, works with all radios off

### M13 — Integration testing
- **Inputs:** M1–M12
- **Outputs:** cross-component contract tests; the **D-01b seven-step scenario end-to-end on real devices**; partition/reunite; server-kill; broker-kill
- **Dependencies:** M11, M12
- **Tests:** the full `11` register, plus end-to-end scenarios
- **Requirements / decisions:** EC-01, EC-02, EC-04; **D-01b**
- **Completion criteria:** every TR passes; the four release-blocking tests (TR-11, TR-14, TR-16, TR-17) green

### M14 — Demo and evaluation instrumentation
- **Inputs:** M13
- **Outputs:** measured bytes per event type; latency figures with sample sizes; usability run with 3–5 first-time users; the four EC demo scripts, each runnable live **and** simulated; `docs/evidence/`
- **Dependencies:** M13
- **Tests:** **TM-04**, **TM-05**, **TM-06**
- **Requirements / decisions:** NFR-01, NFR-03, NFR-04; `05` §7 claim gate
- **Completion criteria:** every claim in the submission has recorded evidence with its sample size and conditions; **no claim marked 🚫 in `05` §7 appears anywhere**

---

## 7. Blockers and exact remedies

| ID | Blocker | Blocks | Remedy — **for you to run, not me** |
|---|---|---|---|
| **B-1** | Git rooted at `$HOME`; specification untracked | M0, and risks all prior work | `git init` inside `RescueNet/`, add a `.gitignore`, commit `docs/` and `spikes/`. **Do not commit from `/Users/krish`** |
| **B-2** | Docker not installed | M0, and every `I` test from M3 | Install Docker Desktop |
| **B-3** | Android toolchain absent (Studio, SDK, adb, Gradle, Kotlin) | M6–M9, M12; SP-01b-A, SP-02, SP-04 | Install Android Studio — TR-01, open since `07` |
| ~~**B-4**~~ | ~~D-02a SMS encoding unresolved~~ — ✅ **CLOSED 2026-08-24** | ~~M8 completion~~ — M8 unblocked | **Done.** B-3 cleared, **SP-01b-A executed** on two handsets / two carriers, and **D-02a ratified as GSM-7 text** with `max_batch_bytes` **120 B**. Q1 binary failed (0/10 delivered, 10/10 `GENERIC_FAILURE`) and the 134 B binary path is withdrawn. Evidence: `05` §1.2a · `07` T-23 · `09` §6.1/§6.3 |

**B-1 and B-2 block M0. B-3 does not block M1–M5, M10 or M11** — roughly 60% of the Spine is backend and dashboard work that proceeds on the toolchain already present.

**Status as of 2026-08-24: B-3 and B-4 are both cleared.** B-3 was resolved by installing Android Studio (which unblocked M6–M8 and SP-01b-A/SP-04); **B-4 closed on the SP-01b-A result** recorded in `05` §1.2a. **No blocker remains against M8.**

**Suggested parallelisation once B-1/B-2 clear:** M1→M2→M3→M4→M5 and M10→M11 on the existing toolchain, while B-3 is resolved in parallel for M6–M9 and M12.

---

## 8. Verdict

See the session report. **M0 is blocked on B-1 and B-2**, both small and both requiring actions I should not take unilaterally: creating a git repository and installing software.
