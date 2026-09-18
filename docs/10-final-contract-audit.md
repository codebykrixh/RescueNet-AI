# RescueNet AI — Final Cross-Document Contract Audit

**Date:** 2026-08-22 · **Scope:** docs 01–09, complete · **Method:** manual review plus mechanical checks against the document text
**Mandate (v1.0):** identify problems only.
**v1.1 — 2026-08-22:** CRITICAL and HIGH findings remediated on instruction. Remediation record in §14. MEDIUM and LOW findings deliberately left open.

---

## 1. Executive summary

Nine documents, ~5,300 lines, 38 requirement IDs at Level 1, 28 architecture decisions, 40 data-model decisions, 22 API decisions, 23 technology decisions. The audit ran 40 specified checks plus mechanical text verification.

**Headline: the discipline held where it matters most.** Every claim-wording constraint survives intact — no document claims binary SMS was validated, that segment counts were observed, that carriers were recorded, or that the application sends SMS. `server_seq` is never described as causal anywhere. MQTT never appears as authoritative in any document. These were the highest-risk failure modes and all are clean.

**However: 1 CRITICAL and 4 HIGH findings block implementation.** All are small, bounded documentation defects rather than design failures — the estimated total remediation is under half a day of edits. The critical one is a genuine encode-breaking contradiction that would cause silent data corruption if an implementer resolved it in the wrong direction.

| Severity | Count | Nature | v1.1 status |
|---|---|---|---|
| **CRITICAL** | 1 | Wire schema cannot represent the range the API permits | ✅ **RESOLVED** |
| **HIGH** | 4 | Two conflicting numeric caps · contract/technology mismatch · unspecified live-update path · test strategy predates the newest decisions | ✅ **ALL RESOLVED** |
| **MEDIUM** | 5 | Citation error · unlisted limitation · divergent projection lists · superseded proposals unmarked · drift-prone duplicates | ⏸ **Open by instruction** |
| **LOW** | 3 | Diagram/contract mismatch · unstated reserved range · scoping omission | ⏸ **Open by instruction** |

**Correction to v1.0 (self-audit).** The v1.0 summary counted 5 MEDIUM and 4 LOW, but §12 listed only 12 findings with F-12 classified LOW and the drift-prone duplicates of §10 carrying no F-ID. Reconciled in v1.1: **F-12 is MEDIUM** (an unmarked superseded proposal is a live drift mechanism, matching F-07's reasoning) and the §10 duplicates are now **F-13, MEDIUM**. Totals: **13 findings — 1 CRITICAL, 4 HIGH, 5 MEDIUM, 3 LOW.**

---

## 2. Cross-document consistency matrix

Result of each of the 40 specified checks. **Verified** means mechanically confirmed against document text, not merely reviewed.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Every Level-1 requirement has an implementation path | ⚠️ **Partial** | §5 — one gap (F-04) |
| 2 | Exactly one authoritative source per requirement | ⚠️ **Partial** | §10 — drift-prone duplicates, F-09 |
| 3 | Canonical event schema consistent everywhere | ✅ **Verified** | All 14 doc-09 JSON examples parse; **zero** non-canonical fields on any event object |
| 4 | `(device_id, seq)` consistently the event identity | ✅ **Verified** | D-05 → AD-05 → DM-06 → AP-02/AP-05 unbroken |
| 5 | `server_seq` never treated as causal | ✅ **Verified** | 8 occurrences of `server_seq`+causal, all explicitly *denying* causality (`08` 8.1/8.2, AD-13) |
| 6 | Cursor distinguished from `server_seq` | ✅ **Verified** | `09` §3.3 — cursor **is** `server_seq`, stated as such, not as a separate token (AP-06) |
| 7 | `REJECTED` only in delivery/outbox metadata | ✅ **Verified** | `08` 6.1/6.2 DM-39; no rejection field in `08` Part 1 or the `event` table |
| 8 | Events never deleted for delivery failure | ✅ **Verified** | `08` 6.2, DM-39/DM-40; `09` §2.7.2; no DELETE grant (DM-29) |
| 9 | Retryable failures remain `PENDING` | ✅ **Verified** | `09` §2.7.1, AP-21, AP-22 |
| 10 | Partial batch acceptance consistent | ✅ **Verified** | AP-04 in `09` §2.3, §2.7.3, §15 check 13 |
| 11 | Request-level failures do not create `REJECTED` | ✅ **Verified** | AP-22, `09` §9.2 |
| 12 | CRITICAL survivor reports safe from `UNKNOWN_CELL` | ✅ **Verified** | AP-20, `09` §2.6.2 |
| 13 | MQTT notification-only everywhere | ✅ **Verified** | AD-15, AP-11; MQTT absent from every `08` table |
| 14 | MQTT cannot write authoritative state | ✅ **Verified** | AP-10 subscribe-only ACL — but see **F-03** on feasibility |
| 15 | Gap detection always leads to REST delta | ✅ **Verified** | AD-17, `09` §4.5 all four branches |
| 16 | Retained messages disabled | ✅ **Verified** | AP-09 `retain: false`; `06` §9.3 "retained messages are a cache, never truth" |
| 17 | Dashboard MQTT credentials subscribe-only | ✅ **Stated** | AP-10 — feasibility questioned in **F-03** |
| 18 | REST remains authoritative | ✅ **Verified** | `06` §9.1, `09` §1.0/§4.7 |
| 19 | SMS only a transport/codec concern | ✅ **Verified** | AD-07, DM-24, `09` §6.5 |
| 20 | SMS encoding | ✅ **CLOSED 2026-08-24** | D-02a/T-23 **FINAL: GSM-7 text, 120 B**. Full wire format ratified in `09` §6.6 (DM-57). The former provisional markings are superseded — historical record retained in `05` §1.2a |
| 21 | No claim binary SMS validated | ✅ **Verified** | Mechanical scan: zero unqualified claims |
| 22 | No claim segment counts observed | ✅ **Verified** | Mechanical scan: zero |
| 23 | No claim the app sends SMS | ✅ **Verified** | Mechanical scan: zero |
| 24 | Gateway is the same APK | ✅ **Verified** | T-22, `09` Part 7 |
| 25 | Gateway relays, does not author | ✅ **Verified** | AP-16; example 11.10 proven byte-identical to 11.2 |
| 26 | Offline events can eventually sync | ✅ **Verified** | `06` §5.4, `09` §15 check 9 |
| 27 | Duplicate delivery idempotent | ✅ **Verified** | AD-28, AP-05, `09` Part 12 |
| 28 | Duplicate search is a derived predicate | ✅ **Verified** | AD-22, DM-07, AP-12 |
| 29 | `GRID_GENERATED` parametric | ✅ **Verified** | DM-10 — but see **F-01** |
| 30 | MQTT payloads non-authoritative | ✅ **Verified** | AP-13 — strict subset, post-commit only |
| 31 | Backend event storage authoritative | ✅ **Verified** | AD-04, `08` §11.3 |
| 32 | `07` stack matches `06` and `09` | ⚠️ **One mismatch** | **F-03** |
| 33 | No deprecated technology as Level 1 | ⚠️ **Partial** | **F-07** — superseded proposals unmarked in `01` |
| 34 | Level-1 scope consistent across `02`,`03`,`05`,`07` | ⚠️ **One conflict** | **F-02** |
| 35 | Provisional decisions marked | ✅ **Verified**; **updated 2026-08-24** | Closed since the audit: **D-02a, T-23, DM-27** (GSM-7 text, `09` §6.6) · **SP-01b-A** (executed) · **SP-04**/**T-03** (TR-19 5/5). Still provisional: T-10, T-14, SP-02, SP-03, SP-06 |
| 36 | Validated claims phrased to the evidence | ✅ **Verified** | Standing wording block present in `06` §0, `09` §6.1; enforced in `05` §7 |
| 37 | No quantitative claim exceeds evidence | ✅ **Verified** | All figures carry sample size or "unvalidated"; TL-10 explicitly de-rates the batching arithmetic |
| 38 | Contradictions between documents | ❌ **3 found** | §3 |
| 39 | Duplicated decisions that could drift | ⚠️ **4 found** | §10 |
| 40 | Requirements with no test strategy | ❌ **Gap found** | **F-05**, §9 |

---

## 3. Contradictions

### F-01 · CRITICAL — the wire schema cannot represent the grid size the API permits

| Document | Statement |
|---|---|
| `04` §3.1 / `spikes/sp01a_codec_budget.py:15` | `"cell_id": 13` bits — comment: *"8192 cells >= 5000 target"*. Addressable range **0…8,191** |
| `09` §10.2 | *"**Grid cell cap** of 10,000, enforced at `POST /grid` with `422`"* |
| `09` §1.2 endpoint 4 | `422` when *"`rows × cols` exceeds the cap"* |

**A grid of 10,000 cells produces `cell_index` values from 8,192 to 9,999 that cannot be encoded in the 13-bit wire field.**

**Why CRITICAL rather than HIGH:** the failure is silent. An implementer who trusts `09` builds a 10,000-cell grid; the codec truncates or wraps the index; a `CELL_STATUS_REPORTED` for cell 9,000 arrives attributed to cell 808. Search coverage would be recorded against the wrong cell — the precise failure PS-B4/PS-B5 exist to prevent — and only on the SMS path, so it would pass every internet-path test.

**Affects:** `04` §3.1 · `08` Part 9 byte table · `09` §10.2 · `spikes/sp01a_codec_budget.py`

### F-02 · HIGH — two different grid caps

| Document | Cap |
|---|---|
| `03` §3.1 failure modes | *"warn and cap above **~5,000 cells**"* |
| `09` §10.2 | *"Grid cell cap of **10,000**"* |
| `01` NFR-09 / AMB-05 | Target scale: **5,000 cells** |

Two documents specify different enforcement limits for the same API behaviour, and neither matches the other's justification. Compounds F-01: resolving F-01 requires choosing one cap.

### F-07 · MEDIUM — `07` cites the wrong document for the proposals it supersedes

`07` §0 and §4 state: *"`03` §6 proposed a set of technical choices explicitly tagged **P**"* and *"`03` §6 TC-06 proposed it"*.

**TC-01…TC-13 are in `01` §6, not `03` §6.** `03` §6 is "Reliability claim discipline". The supersession is legitimate and correctly reasoned; only the citation is wrong. It matters because traceability is a governing discipline of this project (`02` §10.3), and a broken citation is the mechanism by which a superseded proposal quietly returns.

---

## 4. Requirement coverage

### 4.1 Level-1 requirement → implementation path

Sampled across all eleven Spine elements; every Level-1 requirement in `02` §5 was traced through `06` → `08` → `09`.

| Requirement cluster | Path | Status |
|---|---|---|
| FR-101…107 identity/attribution | `08` Part 3 entities → `09` endpoints 1, 5, 6 → per-event attribution DM-04 | ✅ |
| FR-201…204 incident + grid | `08` §2.1 events 1–2 → `09` endpoints 3, 4 | ✅ |
| FR-301…305, 307, 309 allocation/status | `08` §2.2 event 7, §7.2 rules 1/4/6 → `09` endpoints 10, 11 | ✅ |
| FR-303 duplicate detection | `08` §7.2 rule 1 → `09` AP-03, AP-12 | ✅ |
| FR-401…404, 407–410 field app | `06` §5, `08` Part 6 | ✅ |
| FR-405 position | `08` §2.2 event 10, PI-08 | ✅ |
| FR-501 survivor | `08` §2.2 event 8 → `09` AP-20 | ✅ |
| FR-601…603, 606 inventory | `08` §2.2 event 9, §7.2 rule 2 | ✅ |
| FR-701…705 dashboard | `06` §11, `09` endpoint 9 + Part 4 | ⚠️ **F-04** |
| FR-801…807, 1001, 1002 sync/audit | `06` §5, `08` Parts 4–8, `09` Parts 2–3 | ✅ |
| FR-901…903, 905 interoperability | `09` §1.1 + OpenAPI, endpoint 12 | ✅ |

### F-04 · HIGH — the live-update path for coverage metrics is unspecified

`FR-703` (aggregate metrics: % searched, cells outstanding) is served at initial load by `09` endpoint 9 (`scope=command`). **No document specifies how metrics update thereafter.**

- `06` §6.2 lists `CoverageMetrics` as a projection — the only mention in any document
- `08` §11.2 does **not** include a `coverage_metrics` table
- `09` §4.3 MQTT `EVENT_COMMITTED` carries no metrics
- `09` §10.3 forbids re-fetching the snapshot

Two implementations are equally consistent with the documents: the dashboard recomputes metrics client-side from applied events, or the server maintains and publishes them. They differ in where the fold lives — exactly the divergence AP-12 was written to prevent for the duplicate flag. **Ownership must be assigned before implementation.**

### 4.2 Problem-statement coverage
Unchanged from `02` §9: every PS clause retains Level-1 coverage except **PS-H1** ("AI" in the title), tracked as AMB-01 and answered at Level 3 by OF-01. No regression.

---

## 5. Data-model coverage

| Aspect | Status |
|---|---|
| Canonical event schema consistent across `08`/`09` | ✅ Mechanically verified — zero non-canonical fields |
| 11 event types complete for Level 1 | ✅ |
| `(device_id, seq)` identity | ✅ Unbroken chain D-05 → AD-05 → DM-06 → AP-02 |
| Merge rules deterministic and total | ✅ `08` §7.2, six explicit functions |
| `REJECTED` confined to delivery metadata | ✅ DM-39; canonical schema untouched |
| Projection list consistent between `06` and `08` | ❌ **F-06** |

### F-06 · MEDIUM — divergent projection lists

| `06` §6.2 | `08` §11.2 |
|---|---|
| `CellState`, `CellHistory`, `DuplicateSearchView`, `TeamPosition`, `Inventory`, `SurvivorList`, `CoverageMetrics` | `cell_state`, `duplicate_search`, `assignment_state`, `team_state`, `team_position`, `resource_stock`, `survivor_report`, `projection_state` |

`assignment_state` and `team_state` appear only in `08`; `CellHistory` and `CoverageMetrics` only in `06`. `CellHistory` is defensible as a query rather than a table, but the two lists are presented as the same set and are not. Feeds F-04.

### F-08 · LOW — reserved `device_id` range unstated
DM-36 reserves `device_id = 0` for server-authored events. No document states that enrolment allocates from **1…4,095**. An implementer could allocate 0 to the first handset.

---

## 6. API coverage

| Check | Status |
|---|---|
| 14 endpoints cover every Level-1 write and read | ✅ |
| No endpoint without a requirement | ✅ AP-01 justifies each exclusion |
| Error contract complete and consistently applied | ✅ Part 9, AP-22 |
| Idempotency proven for all 10 scenarios | ✅ Part 12 |
| Examples conform to `08` | ✅ 14/14 parse; relayed batch byte-identical to direct |
| `06` read-path components map to `09` endpoints | ⚠️ **F-10** |

### F-10 · LOW — `06` shows Delta API and Audit API as separate components
`06` §10.1 renders `DELTA` and `AUD` as distinct boxes; `09` merges both into endpoint 8 with query filters. Defensible consolidation, but the architecture diagram and the contract disagree on component count.

---

## 7. Transport coverage

| Check | Status |
|---|---|
| SMS confined to codec/transport | ✅ AD-07, DM-24, `09` §6.5 |
| Encoding confined to framing (DM-27) | ✅ **and now closed** — D-02a/T-23 FINAL 2026-08-24; DM-27 held: no domain, merge, projection or column changed |
| No overclaim on SMS evidence | ✅ Mechanically verified |
| Gateway relays, never authors | ✅ AP-16, verified in examples |
| Gateway is the same APK | ✅ T-22 |
| Transport-agnostic sync interface | ✅ `06` §7, AD-06/AD-08 |
| `PeerTransport` costs Level 1 nothing | ✅ AD-26, `06` §15 |
| SMS-only device downlink limitation disclosed | ⚠️ **F-05** |

### F-05 · MEDIUM — a permanently SMS-only device never receives assignments, and this is not an accepted limitation

D-06 makes the SMS downlink **acknowledgement-only**. `09` §6.3 confirms. `06` §13 lists "receiving new assignments" under *Requires connectivity*.

**Consequence:** a field device that never reaches internet can upload observations indefinitely but can never receive an assignment, a revocation, or any other team's state. It is write-only to the shared picture.

This is a *correct* consequence of D-06, not a design error. But it is a significant operational limitation and it is **not listed in `05` §6 Accepted Limitations** (AL-01…AL-14). AL-03 covers "SMS fails when cellular is down", which is a different condition. Anyone reading `05` §6 as the limitation register would not learn this.

---

## 8. Security coverage

| Concern | Status |
|---|---|
| Auth model consistent `06`/`07`/`09` | ✅ Opaque tokens + per-device HMAC |
| Gateway token vs batch MAC distinction | ✅ AP-16 — the strongest security reasoning in the set |
| SMS trust boundary honestly bounded | ✅ AD-24 — no confidentiality claimed, 32-bit MAC disclosed as weak |
| Replay protection | ✅ Monotonic `seq` + dedupe |
| MQTT ACL enforces AD-15 | ⚠️ **F-03** |
| Attribution immutable and complete | ✅ DM-04, `08` Part 13 |

### F-03 · HIGH — per-session MQTT credentials may not be feasible with the selected broker

| Document | Statement |
|---|---|
| `09` §4.4 | Dashboard credential *"Username/password **issued with the session**"* |
| `07` T-09 | Mosquitto, *"file-based auth"*, chosen for minimalism |

Mosquitto's default authentication is a **static password file**; per-session credential issuance requires either an auth plugin (added complexity, contradicting the "smallest stack" rationale) or rewriting and reloading the password file per login (fragile, and a demo-day failure mode).

The **security property** — subscribe-only, no publish permission (AP-10) — is achievable with a single static credential and a static ACL. Only the *issuance mechanism* is in question. But because AP-10 is the structural guarantee behind check 14, the mechanism has to actually work.

---

## 9. Test coverage

### F-09 · HIGH — test strategy predates the newest decisions

`03` §3 defines per-package test strategies and `07` T-17 selects frameworks. Both were written **before** docs 08 and 09. Mechanical scan of `03` and `07` for test coverage of the newer contracts:

| Contract element | Introduced in | Test strategy exists? |
|---|---|---|
| `REJECTED` state machine + transitions | `09` AP-14 / `08` DM-39 | ❌ **None** |
| `retryable` handling; `REJECTED` never from request-level failure | AP-21, AP-22 | ❌ **None** |
| CRITICAL carve-out for `UNKNOWN_CELL` | AP-20 | ❌ **None** |
| Gateway relay preserves attribution | AP-16 | ❌ **None** |
| Batch MAC verification and rejection | `09` §6.3, Part 7.2 | ❌ **None** |
| MQTT gap detection → REST delta | AD-16/17, `09` §4.5 | ⚠️ Only as spike SP-06, not as a regression test |
| Partial batch acceptance | AP-04 | ❌ **None** |
| `duplicate_search` projection | AD-22, `08` §7.2 rule 1 | ⚠️ Covered by `04` §3.2 simulation, not by a planned suite |
| Parametric grid derivation (`cell_index` ↔ label ↔ bounds) | DM-10 | ❌ **None** — and this is where F-01 would be caught |

**Existing coverage is genuinely strong** for merge/convergence (`04` §3.2's 13 assertions port directly per T-17) and for offline persistence (the airplane-mode checklist in `03` §3.4). The gap is entirely in contracts defined after `03` was written.

---

## 10. Duplicated decisions at risk of drift

| Decision | Restated in | Risk |
|---|---|---|
| D-06 receive-mostly gateway | `04`, `05`, `06`, `08`, `09` — 5 documents | **Medium.** Changing the ack format would require 5 edits |
| Merge rules | `06` §6.2 **and** `08` §7.2 | **High.** Two normative statements of the same rules; `08` is more complete. See F-06 |
| Byte budgets | `04` §3.1, `08` Part 9, `09` Part 10 | **Medium.** `08` DM-38 already de-rated `04`'s figures; a third restatement in `09` could drift again |
| Accepted limitations | `03` §5/§6, `05` §6, `06` §12, `09` Part 13 | **Medium.** F-05 is exactly this failure — a limitation stated in `06` but absent from `05`'s register |

**Recommendation (not applied):** designate one document as normative per topic — `08` for merge rules and byte budgets, `05` §6 as the single limitation register — and have the others cite rather than restate.

---

## 11. Unresolved risks carried forward

| Risk | Status |
|---|---|
| SP-01b-A — programmatic SMS, binary encoding, throttle | ✅ **EXECUTED 2026-08-24.** Q1 binary FAILED (0/10, `GENERIC_FAILURE`) → D-02a/T-23 closed as GSM-7 text. Q3 did **not** locate the throttle threshold — TL-10 remains open and non-blocking (`05` §1.2a) |
| SP-02 — peer sync viability | Pending, Level 2 only |
| SP-03 — MapLibre at 5,000 cells | Pending. Blocks T-14 |
| SP-04 — Room durability | Pending. Blocks AD-10/NFR-07 claim |
| SP-06 — Mosquitto WebSocket + gap recovery | Pending. Now also gates **F-03** |
| TL-10 — segment economy unvalidated | Disclosed; batching arithmetic remains theoretical |
| AL-05 — order inversion | Disclosed; demo-immune per DM-22 |
| TR-01 — Android Studio absent | **Still the single largest schedule risk** |

---

## 12. Exact recommended fixes

**Not applied.** Each is precise enough to execute without re-deciding anything.

| ID | Severity | Fix | Files |
|---|---|---|---|
| **F-01** | **CRITICAL** | Choose one: **(a)** lower the API grid cap to **8,191 cells** and state that it derives from the 13-bit wire field; or **(b)** widen `cell_id` to **14 bits** (+1 bit/event, ~0.1 B — immaterial per DM-01's precedent) and keep a 10,000 cap. **(a) is recommended** — it needs no re-sizing and 8,191 exceeds the NFR-09 target of 5,000. Add a cross-reference in `08` Part 9 tying the cap to the wire width so the two cannot drift again | `09` §10.2, §1.2 endpoint 4 · `08` Part 9 · `04` §3.1 note · `spikes/sp01a_codec_budget.py` |
| **F-02** | **HIGH** | Adopt the single cap chosen in F-01 everywhere; replace `03` §3.1's "~5,000" with the exact figure and mark it as derived, not independent | `03` §3.1 · `09` §10.2 |
| **F-03** | **HIGH** | Replace "issued with the session" with **a single static subscribe-only dashboard credential plus a static broker ACL**, provisioned in Compose config. Preserves AP-10's security property with Mosquitto's native capability. Add ACL verification to SP-06's pass criteria | `09` §4.4, Part 13 · `07` §5.1, SP-06 |
| **F-04** | **HIGH** | Assign ownership of `CoverageMetrics`: **recommend server-side**, added to `08` §11.2 as a derived table and carried in the snapshot, with the dashboard recomputing incrementally from applied events between snapshots — mirroring AP-12's "one fold, one source" principle. State it explicitly wherever chosen | `08` §11.2 · `09` §1.2 endpoint 9, §4.3 · `06` §6.2 |
| **F-09** | **HIGH** | Add a test-strategy addendum covering the nine untested contract elements in §9. Most are pure-logic and cheap: the `REJECTED` machine and partial-batch acceptance are pytest cases; parametric grid derivation is a JUnit round-trip that **would catch F-01 automatically** | new addendum, or `03` §3 / `07` T-17 |
| **F-05** | **MEDIUM** | Add to `05` §6 as **AL-15**: *"A device that never reaches internet can upload observations but never receives assignments, revocations or other teams' state — SMS downlink is acknowledgement-only (D-06)."* | `05` §6 |
| **F-06** | **MEDIUM** | Reconcile the projection lists; make `08` §11.2 normative and have `06` §6.2 cite it | `06` §6.2 · `08` §11.2 |
| **F-07** | **MEDIUM** | Correct the citation from `03` §6 to `01` §6 in both places; add a supersession note at `01` §6 pointing to `07` | `07` §0, §4 · `01` §6 |
| **F-08** | **LOW** | State that enrolment allocates `device_id` from 1…4,095, reserving 0 | `08` DM-36 · `09` endpoint 1 |
| **F-10** | **LOW** | Note in `06` §10.1 that Delta and Audit are one endpoint with filters | `06` §10.1 |
| **F-11** | **LOW** | Scope NFR-01's ≤512 B/update budget explicitly to *event updates*, not snapshot or export | `01` NFR-01 · `09` Part 10 |
| **F-12** | **LOW** | Add supersession markers to `01` §6 TC-03 (HLC/CRDT-style → superseded by AD-13/AD-14) so a superseded proposal cannot be mistaken for guidance | `01` §6 |

**Estimated total remediation: under half a day.** No fix requires re-deciding anything; F-01 and F-04 require a choice between two stated options, both already reasoned.

---

## 14. Remediation record — v1.1

### F-01 · CRITICAL · ✅ RESOLVED

| | |
|---|---|
| **Original finding** | The SMS codec sizes `cell_index` at 13 bits (0…8,191) while `09` capped grids at 10,000 cells. Cells 8,192–9,999 unencodable; failure silent and SMS-path-only |
| **Fix applied** | `MAX_CELLS = 8,191` established as the single authoritative Level-1 limit in a new normative section `09` §10.5, stating it is **derived from the 13-bit field, not chosen**. Valid `cell_index` 0…8,190; index 8,191 reserved as a one-value margin. Cross-reference added at `08` Part 9 binding the cap to the field width so they cannot drift. Note added at `04` §3.1 (5a) recording the derivation — **no measured result altered**. Spike comment clarified, **value unchanged** |
| **Verification** | `grep` for `10,000` across all docs → only one illustrative geometry line remained, now annotated as exceeding `MAX_CELLS`. `MAX_CELLS`/8,191 appears in `03`, `04`, `08`, `09`, `11` and the spike. Spike re-executed: byte figures **identical** to the recorded results. NFR-09 target of 5,000 < 8,191 ✅. Codec completeness: 0…8,190 fits 13 bits with no truncation or collision |
| **Test added** | **TR-11** — full-range round-trip of every valid index, plus `MAX_CELLS`+1 rejected with `422`. Release-blocking |
| **Status** | **RESOLVED.** No FINAL decision changed; wire width untouched |

### F-02 · HIGH · ✅ RESOLVED

| | |
|---|---|
| **Original finding** | `03` capped at ~5,000, `09` at 10,000 — two enforcement limits for one behaviour |
| **Fix applied** | Both replaced with `MAX_CELLS = 8,191`. `09` §10.5 adds an explicit **target vs hard maximum** table: 5,000 is the NFR-09 evaluation target; 8,191 is the implementation maximum. `03` §3.1 point 8 now states the cap and flags its own 5,000 references as the target |
| **Verification** | Only one grid limit now exists across all documents. Both figures appear with distinct, stated meanings |
| **Status** | **RESOLVED** |

### F-03 · HIGH · ✅ RESOLVED

| | |
|---|---|
| **Original finding** | `09` §4.4 said dashboard MQTT credentials are "issued with the session"; Mosquitto's static password file (T-09) cannot do that without a plugin |
| **Fix applied** | `09` §4.4 rewritten to separate **authentication** (static password file, two accounts), **authorization** (static ACL: publisher write-only, dashboard subscribe-only) and **credential provisioning** (**configured at deployment, not dynamically issued** — stated explicitly). The configured credential is delivered to the browser in the session response *after* commander authentication, so it is absent from the unauthenticated bundle. Session response and example 11.1 updated. Security table row updated with the honest limit: a shared static account has no per-user revocation. **No plugin introduced.** Registered as AP-23 |
| **Constraints preserved** | Subscribe-only ✅ · dashboard cannot publish ✅ · Mosquitto retained ✅ · MQTT notification-only ✅ |
| **Verification** | `grep` for "issued with the session" → zero outside the historical note. AP-10's security property unchanged. **TR-15** asserts the ACL refuses a dashboard publish |
| **Status** | **RESOLVED** |

### F-04 · HIGH · ✅ RESOLVED

| | |
|---|---|
| **Original finding** | `CoverageMetrics` appeared once across nine documents; no update path after the snapshot; two implementations equally consistent |
| **Fix applied** | New `09` §5.3 defines one rule answering all six required questions: **source data** = `cell_state` + grid `rows × cols`; **derived** from the read model, itself a fold of the event log; **recalculated** in the same post-commit step as `cell_state`; **after delta events** the client does not recompute — the server republishes; **persisted** as `coverage_metrics` for snapshot speed and **fully recomputable** (DM-30); **after synchronisation** recomputed by the normal projection update, identical after any rebuild. Carried in the snapshot and in MQTT `derived.coverage` on cell-state-changing events only. `coverage_metrics` added to `08` §11.2 as a derived table. Registered as AP-24 |
| **No second source of truth** | The dashboard **never** computes coverage. One fold, server-side — mirroring AP-12 |
| **Verification** | Single owner stated in `08` and `09`; MQTT example carries `derived.coverage`; **TR-29** asserts a non-recomputing client stays correct and a rebuild is identical |
| **Status** | **RESOLVED** |

### F-09 · HIGH · ✅ RESOLVED

| | |
|---|---|
| **Original finding** | Test strategy predated docs 08–09; nine contract elements had no planned tests |
| **Fix applied** | Created [`11-test-strategy.md`](11-test-strategy.md): **34 planned automated tests (TR-01…TR-34) plus 6 manual checks (TM-01…TM-06)**, with a coverage matrix in which **no Level-1 contract area is empty**. All fifteen required subjects covered: `REJECTED` (TR-01), retryable vs permanent (TR-02), AP-21 (TR-03), AP-22 (TR-04), `UNKNOWN_CELL` routine (TR-05) and **critical** (TR-06), partial batch acceptance (TR-07), idempotency (TR-08), gateway attribution (TR-09), MAC verification (TR-10), max cell index round-trip (TR-11), parametric grid (TR-12), MQTT gap recovery (TR-13), MQTT cannot mutate state (TR-14), subscribe-only credentials (TR-15) |
| **Verification** | Frameworks limited to those already selected in T-17/T-09 — **no new technology**. §5 records which tests would have caught F-01, F-03 and F-04 |
| **Status** | **RESOLVED** |

---

## 15. Post-remediation verification

| # | Check | Result |
|---|---|---|
| 1 | Mechanical consistency checks re-run | ✅ Claim-wording checks 21–23 clean; check 5 clean; check 16 clean |
| 2 | All JSON examples valid | ✅ **20 blocks** across `08` and `09`, zero invalid |
| 3 | All Mermaid diagrams valid | ✅ **13 diagrams**, zero structural problems |
| 4 | Old 10,000-cell limit removed | ✅ Only one illustrative geometry reference remains, explicitly annotated as exceeding `MAX_CELLS` |
| 5 | Contradictory MQTT credential language removed | ✅ Zero occurrences outside the historical note |
| 6 | Canonical event schema unchanged | ✅ `08` Part 1 field table intact; **zero** non-canonical fields on any event object; rejection metadata absent from the canonical event |
| 7 | No new technology introduced | ✅ `11` uses only pytest, JUnit5, Robolectric, Vitest, Mosquitto, instrumented — all from T-17/T-09 |
| 8 | No requirement removed | ✅ Counts unchanged: 85 FR + 20 NFR rows in `01`, 14 AL in `05`; registers AD 28, DM 40, T 23; AP **22 → 24** (AP-23, AP-24 added by these fixes) |

---

## 13. Final implementation readiness verdict

**What is genuinely sound.** The core reasoning chains hold end to end and under mechanical scrutiny: event identity from D-05 through to the API examples; MQTT's confinement, enforced structurally rather than by convention; SMS isolation behind the codec boundary; evidence discipline, with not one overclaim in ~5,300 lines despite considerable pressure to produce a compelling narrative; and the merge semantics, which are the hardest part and are already validated 13/13 against a real scenario.

**What blocks implementation.** One critical contradiction that would silently corrupt cell attribution over the SMS path — precisely the failure the system exists to prevent, and precisely the kind that passes internet-path testing. Four HIGH findings, of which F-09 matters most structurally: the newest and least-reviewed contracts are exactly the ones with no planned tests, and a parametric-grid round-trip test would have caught F-01 without human review.

These are documentation defects, not design failures. Nothing found requires reopening a FINAL decision. But F-01 must not be resolved by an implementer choosing arbitrarily at the keyboard, and F-04 must not be resolved by two components each assuming the other owns the fold.

---

### v1.0 verdict — superseded
`NOT READY FOR IMPLEMENTATION` — blocking on F-01 (CRITICAL) and F-02, F-03, F-04, F-09 (HIGH).

### v1.1 verdict — after remediation

All five blocking findings are resolved and independently verified (§14, §15). No FINAL decision was reopened, no architecture was redesigned, no feature was added, and no new technology was introduced. Two new API decisions (AP-23, AP-24) were registered, both forced by the findings rather than chosen.

**Remaining open — by instruction, not oversight:**

| Severity | Count | Findings |
|---|---|---|
| CRITICAL | **0** | — |
| HIGH | **0** | — |
| MEDIUM | **5** | F-05 unlisted SMS-only limitation · F-06 divergent projection lists · F-07 citation error · F-12 unmarked superseded proposal · F-13 drift-prone duplicated decisions |
| LOW | **3** | F-08 reserved `device_id` range · F-10 diagram/contract component mismatch · F-11 NFR-01 scoping |

None of the eight remaining findings can cause data loss, silent corruption, or an unimplementable contract. Each is a documentation-clarity or drift-prevention item safely addressed during implementation.

# READY FOR IMPLEMENTATION
