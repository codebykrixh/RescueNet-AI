# RescueNet AI — Level-1 Test Strategy and Register

**Date:** 2026-08-22 · **Created to close audit finding F-09** ([`10`](10-final-contract-audit.md) §9)
**Scope:** every Level-1 contract defined in [`06`](06-system-architecture.md), [`08`](08-data-and-event-model.md) and [`09`](09-api-and-mqtt-contracts.md)
**Frameworks:** fixed by T-17 in [`07`](07-technology-selection.md) — no new technology is introduced here

> **No code.** This is a planned-test register. Every entry is `PLANNED`.

---

## 1. Why this document exists

`03` §3 defined per-package test strategies and `07` T-17 selected frameworks — both written **before** docs 08 and 09. The audit found that the newest and least-reviewed contracts had **no planned tests at all**: the `REJECTED` state machine, AP-20/21/22, gateway attribution, MAC verification, partial batch acceptance and parametric grid derivation.

That is the wrong risk profile. This register closes it, and adds coverage for every other Level-1 contract so the rule below can hold.

**Governing rule: every Level-1 contract has at least one planned automated test.** Where a contract can only be verified manually, it is listed as such with a reason — never left implicit.

## 2. Test levels

| Level | Runs | Framework | Speed |
|---|---|---|---|
| **U** Unit — pure logic, no I/O | Every build, CI | pytest · JUnit5 · Vitest | ms |
| **I** Integration — with a real Postgres or broker | Every build, CI | pytest + Compose services | seconds |
| **D** Device — requires a physical handset | Before each demo rehearsal | Instrumented / Robolectric | minutes |
| **M** Manual — cannot be automated, with a stated reason | Checklist per build | — | — |

**The merge/convergence suite is not new work:** `04` §3.2's 13 assertions port directly into pytest (T-17), which is why Python was selected.

---

## 3. Test register

### 3.1 Contracts introduced by docs 08–09 — the audit gap

| ID | Contract | Asserts | Lvl | Framework | Traces to |
|---|---|---|---|---|---|
| **TR-01** | `REJECTED` outbox state | Full state machine: `PENDING→IN_FLIGHT→REJECTED` on `retryable:false`; **no other path reaches `REJECTED`**; `IN_FLIGHT→PENDING` on every transient failure | U | JUnit5 | AP-14, DM-39 |
| **TR-02** | Retryable vs permanent | `retryable:true` → `PENDING` with backoff; `retryable:false` → `REJECTED`; **the domain event remains in the local log in both cases** | U | JUnit5 | AP-14 c.2/c.5, DM-39 |
| **TR-03** | AP-21 — client reads the boolean, not the code | An **unrecognised** `code` with `retryable:true` still returns to `PENDING`; an unrecognised code with `retryable:false` still rejects; a **missing** `retryable` field fails safe to `PENDING` | U | JUnit5 | AP-21 |
| **TR-04** | AP-22 — request vs event level | `401`/`403`/`413`/`500`/`503` leave **every** event `PENDING` and produce **zero** `REJECTED` rows; only a per-event rejection inside a `200` can reject | U | JUnit5 | AP-22 |
| **TR-05** | AP-20 — `UNKNOWN_CELL` on ROUTINE | `CELL_STATUS_REPORTED` with an out-of-grid `cell_index` → rejected, `retryable:false` | I | pytest | AP-20 |
| **TR-06** | **AP-20 — `UNKNOWN_CELL` on CRITICAL** | `SURVIVOR_REPORTED` with an out-of-grid `cell_index` → **accepted**, persisted, and flagged in the `survivor_report` read model. **Never rejected.** Life-critical data cannot be lost to a reference typo | I | pytest | AP-20, PS-B9 |
| **TR-07** | Partial batch acceptance | A batch of 3 with 1 invalid → `200`; 2 in `accepted` with `server_seq`; 1 in `rejected`; **the valid two are persisted** | I | pytest | AP-04 |
| **TR-08** | Duplicate delivery idempotency | Same batch twice → identical `server_seq` values, `was_duplicate:true`, **one** row per event, **one** MQTT publish | I | pytest | AD-28, AP-05 |
| **TR-09** | **Gateway attribution** | A batch relayed under a `GATEWAY` token persists events whose `device_id`, `responder_id`, `team_id`, `agency_id`, `t_dev` are **byte-identical to the originals**. The gateway appears nowhere except `received_via` | I | pytest | AP-16, DM-04 |
| **TR-10** | MAC verification | Valid MAC → accepted. Tampered payload, wrong secret, or missing MAC on a `GATEWAY` batch → `401`, **zero events persisted**, failure surfaced in diagnostics | I | pytest | AP-16, AD-24 · **owned by M8** (DM-49) — the MAC covers packed wire bytes, so it needs the M8 codec. M5 issues the `hmac_secret` it verifies against |
| **TR-11** | **Maximum cell index round-trip** | Every `cell_index` in `0…8,190` encodes and decodes through the SMS codec to the identical value — **no truncation, no wrap, no collision across the full range**. `MAX_CELLS`+1 is rejected at `POST /grid` with `422` | U | JUnit5 + pytest | **F-01**, `09` §10.5 |
| **TR-12** | Parametric `GRID_GENERATED` | One event yields the full cell set; `cell_index ↔ (row,col) ↔ label ↔ bounds` round-trips exactly; **no per-cell event and no label is ever transmitted** | U | JUnit5 + pytest | DM-10, FR-203, FR-204 |
| **TR-13** | MQTT `server_seq` gap recovery | `Y == X+1` applies directly with **no** REST call; `Y <= X` ignored; `Y > X+1` triggers exactly one delta from `X` and converges; gap `> 2000` re-snapshots | U + I | Vitest + pytest | AD-16, AD-17, `09` §4.5 |
| **TR-14** | **MQTT cannot mutate authoritative state** | Publishing a well-formed notification directly to the topic changes **no** row in `event` and **no** read model. Killing the broker mid-run leaves ingestion and REST fully correct | I | pytest | **AD-15**, AP-11 |
| **TR-15** | Subscribe-only MQTT credential | The dashboard account's publish attempt is **refused by the broker ACL**; its subscribe succeeds. The publisher account cannot subscribe | I | pytest + Mosquitto | AP-10, **AP-23** |

### 3.2 Remaining Level-1 contracts

| ID | Contract | Asserts | Lvl | Framework | Traces to |
|---|---|---|---|---|---|
| **TR-16** | Merge and convergence | The 13 assertions of `04` §3.2: partition, reunion, duplicate delivery, out-of-order, clock skew, a node that never met the server, four-node identical key sets | U | pytest | FR-806, `04` §3.2 |
| **TR-17** | **Duplicate search predicate (D-01b)** | The full seven-step scenario: both events preserved, both auditable with attribution, flag names both teams, **nothing discarded**. Order-independent — passes with either `server_seq` ordering | U + I | pytest | **D-01b**, AD-22, DM-22 |
| **TR-18** | Inventory delta commutativity | Two offline decrements on one item sum correctly in either arrival order; negative totals are displayed, not clamped | U | pytest | `08` §7.2 rule 2 |
| **TR-19** | Single-transaction local write | Event + `seq` allocation + outbox insert commit atomically; an interrupted transaction leaves **none** of the three; a consumed `seq` may leave a legal gap | D | Instrumented | AD-10, DM-13, **SP-04** |
| **TR-20** | Offline write path | With all radios disabled, each of the three critical actions completes locally, survives force-kill and reboot, and **makes no network call** | D | Instrumented | FR-402, AD-02 |
| **TR-21** | Delta cursor determinism | The same `since` yields the same page; `next_since` advances only on successful apply; paging is resumable after interruption; the byte cap can return fewer than `limit` | I | pytest | AP-06, `09` §3.5 |
| **TR-22** | Event identity | `seq` strictly monotonic per device; gaps accepted by the server; `SEQ_NOT_MONOTONIC` rejected; `device_id` allocated from **1…4,095** with 0 reserved for the server | U + I | JUnit5 + pytest | D-05, DM-13, DM-36 |
| **TR-23** | Ordering semantics | Folds use `server_seq` only; `t_dev` never orders anything; **the AL-05 inversion is reproducible and visible in the audit view** | U | pytest | AD-13, DM-21, AL-05 |
| **TR-24** | Two-tier priority | `SURVIVOR_REPORTED` is packed before every ROUTINE event; ROUTINE is **never** selected for a METERED transport while internet is absent | U | JUnit5 | **D-04**, AD-09 |
| **TR-25** | Codec round-trip | All 11 event types encode and decode losslessly; every batched event fits its Part-9 byte budget | U | JUnit5 | DM-25, NFR-01 |
| **TR-26** | Codec never truncates | An event that cannot be represented is **not sent** and stays `PENDING` — never silently shortened | U | JUnit5 | `08` §10.1 rule 2 |
| **TR-27** | Snapshot economy | Untouched cells are absent; `cell_state` uses positional arrays; the response respects the `scope` role restriction | I | pytest | DM-12, `09` §1.2 |
| **TR-28** | Assignment collision | Assigning a held cell returns `201` with `already_held` naming the holder — **not** `409`, and the commander is not blocked | I | pytest | **FR-303**, AP-03 |
| **TR-29** | Coverage metrics single fold | Metrics come only from the server; a dashboard that applies events **without** re-computing still shows correct totals after the next `derived.coverage`; a projection rebuild yields identical values | I | pytest | **AP-24**, `09` §5.3 |
| **TR-30** | Append-only enforcement | The application role's `UPDATE` and `DELETE` on `event` are **refused by the database** | I | pytest | DM-29 |
| **TR-31** | Attribution completeness | No event can be persisted without `responder_id`, `team_id`, `agency_id`, `device_id`, `t_dev`, `t_srv` | I | pytest | FR-1002, DM-04 |
| **TR-32** | Audit reconstruction | "What happened to grid B-14?" returns the full ordered narrative from `event` alone, **touching no projection** | I | pytest | `08` Part 13, DM-32 |
| **TR-33** | Enrolment non-idempotency | Two enrolments with one code yield **two distinct `device_id`s**; an exhausted or expired code returns `409` | I | pytest | AP-02 · **owned by M5** (`12` §3.2) — tests endpoint 1, which M4 does not build |
| **TR-34** | Export validity | GeoJSON parses and opens in third-party GIS; CSV matches the documented columns | I | pytest | FR-905, EC-04 |

### 3.3 Manual-only, with reasons

| ID | Check | Why not automatable |
|---|---|---|
| **TM-01** | Three-tap doctrine | Tap counting on a real device with real fingers | 
| **TM-02** | Glove operation | Physical |
| **TM-03** | Contrast and target-size audit | Tooling assist, human judgement |
| **TM-04** | First-time-user task completion (NFR-04) | Requires people who have never seen the app |
| **TM-05** | Real-carrier SMS delivery | SP-01b-A; carrier behaviour is outside our control |
| **TM-06** | Projector colour legibility | Venue-dependent |

---

## 4. Level-1 contract coverage matrix

Every Level-1 contract, and the test that covers it. **No row is empty.**

| Contract area | Covered by |
|---|---|
| Event identity and dedup | TR-08, TR-22 |
| Merge and fold semantics | TR-16, TR-17, TR-18, TR-23, TR-29 |
| Duplicate search (D-01b) | **TR-17** |
| Outbox and delivery states | TR-01, TR-02, TR-03, TR-04, TR-19 |
| Offline operation | TR-19, TR-20 |
| Ingestion and validation | TR-05, TR-06, TR-07, TR-28, TR-31, TR-33 |
| Sync and delta | TR-13, TR-21, TR-27 |
| MQTT | TR-13, TR-14, TR-15 |
| SMS codec | TR-11, TR-12, TR-25, TR-26 |
| Gateway | TR-09, TR-10 |
| Grid | TR-11, TR-12 |
| Priority and bandwidth | TR-24, TR-25, TR-27 |
| Security | TR-10, TR-15, TR-22, TR-30, TR-31 |
| Audit | TR-30, TR-31, TR-32 |
| Interoperability | TR-34 |
| Usability | TM-01…TM-04 |

## 5. Tests that would have caught the audit findings

Recorded because it justifies the register's shape:

| Finding | Test that catches it |
|---|---|
| **F-01** cell-index width vs grid cap | **TR-11** — a full-range round-trip fails immediately at index 8,192 |
| **F-04** coverage metrics ownership | **TR-29** — a client-side fold diverges from the server's |
| **F-03** MQTT credential feasibility | **TR-15** — a per-session credential cannot satisfy it against a static password file |

## 6. Execution policy

| Suite | When |
|---|---|
| All `U` | Every commit |
| All `I` | Every commit, against Compose services |
| All `D` | Before each demo rehearsal, minimum weekly |
| All `TM` | Per rehearsal, from a checklist |

**TR-11, TR-14, TR-16 and TR-17 are release-blocking**: they cover the wire-safety property that F-01 exposed, the MQTT non-authority guarantee, the merge correctness the whole design rests on, and the flagship demo scenario.
