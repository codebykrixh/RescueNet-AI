# RescueNet AI — Feasibility Validation (v1.0)

**Status:** Spike results recorded · **Date:** 2026-08-22 · **Stage:** Feasibility validation — architecture still deferred
**Source of truth:** the official problem statement. **Companion documents:** [`01-requirements-analysis.md`](01-requirements-analysis.md) · [`02-prototype-scope.md`](02-prototype-scope.md) · [`03-feasibility-analysis.md`](03-feasibility-analysis.md)

> **Transport choice is NOT finalized in this document.** SP-01 is split into an analytical half (executed here) and a radio half (cannot be executed on this machine — protocol supplied in §4). The D-02 decision gate is defined in §5 and remains open.

---

## 0. What happened in this phase

| | |
|---|---|
| **Executed** | SP-01a (SMS payload budget) · SP-05 (merge & convergence simulation, new — derived from D-01) |
| **Not executable here** | SP-01b (real-carrier SMS) · SP-02 (peer sync) · SP-03 (dashboard render load) · SP-04 (offline persistence) — no Android SDK, no `adb`, no handsets, no SIMs on this machine |
| **Decisions closed** | D-01 (duplicate search effort) — applied and validated in §1 and §3.2 |
| **Decisions still open** | D-02 (Level-1 transport) — gate defined in §5 |
| **Spike code location** | `spikes/` — **isolated experimental code, explicitly not architecture**, to be discarded or rewritten before implementation |
| **Hardware spike EXECUTED** | **SP-01b-M — executed on real handsets, 2026-08-22. PARTIAL PASS.** All five payloads EXACT MATCH in both directions (§4.0.1). Segment counts not observable; latency not recorded. |
| **Hardware spikes still blocked** | SP-01b-A, SP-02, SP-04 — 2026-08-22, **not executed.** Handsets and SIMs are confirmed available to the user, but there is no execution path from this machine: `adb` absent, Android SDK absent, Gradle absent, `kotlinc` absent, no device attached over USB. Verified, not assumed. Test materials produced instead (§4.0). |

**Two results changed the plan.** SP-01a showed that text SMS is only ~11% less efficient than binary data SMS, which **substantially de-risks R-01** — carrier rejection of binary SMS is no longer a blocker, only an efficiency question. It also relocated the throttle problem: the field uplink is comfortably within limits, while the **gateway downlink** is the real chokepoint. Both findings are in §3.1.

---

## 1. D-01 APPLIED — duplicate search effort

**Decision (approved):** the prototype demonstrates **duplicate search effort**, not an artificially staged offline duplicate grid *assignment*.

This supersedes the original FR-303 demonstration framing. **Traceability is unchanged:** FR-303 keeps its ID, source (PS-B4, PS-B13) and provenance (Explicit). Only the demonstration scenario changes — and it moves *closer* to PS-B4, which describes agencies "duplicating search efforts in some zones", not duplicating assignments.

### 1.1 The required scenario, as a formal acceptance specification

| # | Required behaviour | Acceptance criterion | Verified by |
|---|---|---|---|
| 1 | B-14 is initially unsearched | Cell status projection returns `unsearched` with no search events present | SP-05 check 1 ✅ |
| 2 | Team A and Team B lose central connectivity | Both devices operate with no server contact and no peer contact | SP-05 step 2 ✅ |
| 3 | Both independently search B-14 | Two independent SEARCH events exist, one per device, created without coordination | SP-05 step 3 ✅ |
| 4 | Both search events are preserved | After merge, exactly 2 SEARCH events on B-14; neither event id absent | SP-05 checks 2–4 ✅ |
| 5 | Both remain auditable after sync | Each event retains team, responder, agency, device time and receipt order | SP-05 check 5 ✅ |
| 6 | Commander dashboard flags the duplicate | Duplicate projection returns B-14 naming both teams and both agencies | SP-05 checks 7–8 ✅ |
| 7 | No event silently discarded | Log cardinality accounts for every emitted event; no overwrite path exists for SEARCH events | SP-05 checks 3, 4, 9 ✅ |

### 1.2 Why this is a better demonstration than the one it replaces
- It is **what PS-B4 actually describes** — wasted effort in the field, not a scheduling clash in an office.
- It is **reachable without contrivance**: two teams offline, both working, is the normal condition the statement describes. Staging two offline commanders was artificial, and D-01 (online-only dashboard) made it nearly impossible anyway.
- It **exercises the merge guarantee that matters** — additive events are never lost — rather than a uniqueness constraint.
- It produces a **visible commander outcome**: a flag on B-14 naming NDRF and Fire Services, which is EC-02 evidence, not just EC-01 evidence.

### 1.3 Demo script (rehearsable, ~90 seconds)
1. Dashboard shows B-14 unsearched, outstanding count visible.
2. Both handsets: mobile data **off**, shown to the audience.
3. Team Alpha marks B-14 searched. Team Bravo marks B-14 searched. Neither sees the other.
4. Alpha syncs. Then Bravo syncs.
5. Dashboard: B-14 shows **two search records**, with team, agency, responder and time — and a **duplicate-effort flag**.
6. Say the line plainly: *"Nothing was thrown away. The commander now knows two agencies burned effort on the same cell — which is exactly the waste the problem statement describes."*

---

## 2. Spike framework

Every spike follows the eight-point structure specified, and **assumptions are recorded separately from actual results**. A result is only written into the "ACTUAL RESULT" block after the experiment has run. Blocks marked `NOT YET RUN` are empty by design — they are not predictions.

**Rule on spike code:** everything under `spikes/` is throwaway. It exists to answer one question each. It is not a prototype, not a reference implementation, and must not be copied into the build.

---

## 3. Executed spikes

### 3.1 · SP-01a — SMS payload budget *(EXECUTED)*

**1. Exact assumption being tested.** That RescueNet operational events can be encoded small enough that a realistic field batch fits in a small number of SMS messages, and that the resulting message volume stays inside Android's outgoing-SMS throttle.

**2. Smallest possible experiment.** Pure computation, no hardware: define bit-level field widths from the NFR-09 scale targets, compute per-event sizes standalone and batched, compare against the three SMS envelopes, then compute message counts for realistic scenarios. Script: `spikes/sp01a_codec_budget.py` + `sp01a_throttle_corrected.py`.

**3. Pass criteria.** A realistic 19-event field batch fits in ≤3 SMS; demo-scenario volume ≤30 messages per device per 30 minutes.

**4. Fail criteria.** A single survivor report exceeds one SMS; or demo volume exceeds the throttle; or text-SMS fallback costs >50% more messages than binary.

**5. Decision that depends on it.** Whether SMS is viable at all as the Level-1 transport, and whether binary data SMS is *required* or merely preferred (which determines how much SP-01b's outcome matters).

**6/7. Spike code.** Isolated computation only. No application code. Not architecture.

**8. ACTUAL RESULT — recorded 2026-08-22:**

| Event type | Standalone | Batched (in-batch) |
|---|---|---|
| CELL_STATUS | 93 b = **12 B** | 61 b = **8 B** |
| SURVIVOR_REPORT | 134 b = **17 B** | 102 b = **13 B** |
| POSITION | 99 b = **13 B** | 67 b = **9 B** |
| INVENTORY_DELTA | 93 b = **12 B** | 61 b = **8 B** |
| *batch header* | — | 53 b = **7 B** — ⚠️ **SUPERSEDED 2026-08-24.** Predates **DM-38**; contains no `base_seq`, `incident_id` or `schema_version`, and assumes a 3-bit `evt_type` retired by **DM-01**. The active header is **89 b = 12 B** (`09` §6.6.1). Retained as historical evidence |

| Envelope | Capacity | Mixed 19-event batch (168 B) |
|---|---|---|
| Data SMS (binary, port-addressed) | 134 B | **2 SMS** |
| Text SMS (single, base64url in GSM-7) | 120 B | **2 SMS** |
| Text SMS (concatenated segment) | 114 B | **2 SMS** |

Throttle, corrected to a **per-device** basis (the throttle is per-app-per-device, not per-incident):

| Path | Volume | Messages | Verdict |
|---|---|---|---|
| Uplink — 1 team, demo window (19 events) | | **2 SMS/device** | OK |
| Uplink — 1 team, busy hour (40 events) | | **3 SMS/device** | OK |
| Uplink — 1 team, full 8 h shift (150 events) | | **11 SMS/device** | OK |
| Downlink — gateway → 10 teams, 3 cycles/30 min | | **30 SMS** | At the limit |
| Downlink — gateway → 20 teams, 3 cycles/30 min | | **60 SMS** | **THROTTLED** |

**Findings:**
1. **PASS on all criteria.** A full field batch fits in 2 SMS; the whole D-01 demo scenario costs ~3 SMS per device.
2. **Text SMS is only ~11% less efficient than binary data SMS** (120 B vs 134 B usable). This is the significant result: **R-01 is largely de-risked**. If carriers reject port-addressed binary SMS, the GSM-7 text fallback costs a fraction more messages and nothing else. SP-01b's outcome therefore no longer threatens the transport decision — it only refines it.
3. **The throttle chokepoint is the gateway downlink, not the field uplink.** SMS has no broadcast, so one gateway handset must send N separate messages. At ≥10 teams with repeated assignment cycles it hits the limit. **Design implication: the prototype gateway must be receive-mostly** — push assignments over data when available, and use SMS downlink only for the demo's two teams.
4. **A 128-bit UUID event id is unaffordable** (16 B/event, ~5 events per SMS). `(device_id, seq)` costs 4 B. This is a concrete design constraint discovered before architecture, which is exactly where it should surface.
5. Origin-relative 16-bit coordinates cost 4 B vs 16 B for two float64s, at 1 m resolution within ±32 km.
5a. **Derived limit (added 2026-08-22, audit F-01):** the 13-bit `cell_index` field addresses 0…8,191, which fixes the Level-1 maximum grid at **`MAX_CELLS` = 8,191 cells** (valid indices 0…8,190; 8,191 reserved). Normative in `09` §10.5. **No measured result in this document changes** — this is a consequence of the schema recorded here, not a revision of it.
6. Position events are individually cheap but dominate by count — **confirms PI-08** (event-driven capture, never streaming).

**Honest limitation of this result.** This is arithmetic over a *proposed* schema, not a wire test. It proves the budget is achievable; it does not prove any encoder exists, and it says nothing about carrier behaviour. That is SP-01b.

---

### 3.2 · SP-05 — Merge & convergence simulation *(EXECUTED — new spike, derived from D-01)*

**1. Exact assumption being tested.** That the D-01 duplicate-search-effort scenario, plus the adversarial cases the SMS path will actually produce (duplicate delivery, out-of-order arrival, clock skew, a node that never meets the server), can be satisfied by an event-log union merge — **and that this can be proven before any architecture exists**.

**2. Smallest possible experiment.** ~120 lines of pure Python: an event record, per-node logs keyed by event id, a bidirectional gossip function, and three read projections (cell status, duplicate flags, inventory total). No database, no network, no device. Script: `spikes/sp05_merge_convergence.py`.

**3. Pass criteria.** All seven D-01 acceptance criteria hold, **and** duplicate delivery is idempotent, **and** inventory deltas commute, **and** all nodes converge to identical event-id sets.

**4. Fail criteria.** Any search event lost or overwritten; duplicate flag not raised; divergence between nodes after gossip; non-commuting inventory.

**5. Decision that depends on it.** Whether the merge policy recommended in `03` §3.8 (additive union + single rule for mutable state + flagging) is sufficient, or whether CRDT semantics must be promoted from Level 3.

**6/7. Spike code.** Isolated simulation. Not architecture — the real system needs persistence, encoding, transport and a schema, none of which this touches.

**8. ACTUAL RESULT — recorded 2026-08-22: 13 / 13 checks passed.**

```
[1] B-14 starts unsearched                                    PASS
[4/5] both search events preserved (2 SEARCH events on B-14)  PASS
      no silent discard — Alpha's event present               PASS
      no silent discard — Bravo's event present               PASS
      both auditable: Alpha/A7/NDRF@1000 | Bravo/B3/Fire@1005 PASS
      survivor report survived the merge                      PASS
[6]   B-14 flagged as duplicate: teams = [Alpha, Bravo]       PASS
      flag names both agencies                                PASS
[7]   duplicate delivery idempotent (5 → 5 events)            PASS
      store-and-forward: node that never met server converges PASS
      inventory deltas commute (−2 and −3 → net −5)           PASS
      clock-skewed event retained and ordered                 PASS
      all four nodes hold identical event-id sets             PASS
```

Commander audit view produced by the simulation:
```
  searched by Alpha   (NDRF  ) responder A7  device_t=1000  recv_order=1
  searched by Bravo   (Fire  ) responder B3  device_t=1005  recv_order=4
  >>> DUPLICATE SEARCH EFFORT FLAGGED: {'B-14': ['Alpha', 'Bravo']}
```

**Findings:**
1. **The D-01 scenario is satisfied by union merge, verified as executable logic before architecture exists.** This is the strongest de-risking result of the phase.
2. **CRDT semantics are not needed at Level 1** — confirms the `03` §3.8 recommendation and keeps Level 3 free of it.
3. **Store-and-forward gossip converges with no extra machinery** — a node that never contacted the server still delivered its events via a peer. This validates the §2.6 layering recommendation from `03` at near-zero cost.
4. **Inventory as deltas removes an entire conflict class** — two offline decrements summed correctly, no merge rule required.
5. Clock-skewed events (device time wrong by ~1000 s) were retained and ordered by server receipt; device time preserved for audit. Confirms the Level-1 substitute for FR-812 is workable.

**Correction made during execution.** The first run's final convergence assertion contained a self-comparing expression and did not test what its label claimed. It was rewritten to compare actual event-id key sets across all four nodes and re-run; the corrected check passes. The 13/13 figure reflects the corrected run.

**Honest limitations of this result.** This proves **merge semantics**, not an implementation. It uses in-memory dictionaries, perfect delivery within a `gossip()` call, and no persistence, encoding, partial-batch loss or concurrency. It does not prove the real system will behave this way — it proves the *rules* are sound, so that when the real system misbehaves we know the bug is in the plumbing, not the policy.

---

## 4. Spikes that could not be executed here

### 4.0 Execution status and spike numbering

**Attempted 2026-08-22. Not executed. Reason: no execution path from this machine to the handsets.** Environment verified, not assumed:

| Check | Result |
|---|---|
| `adb` (4 standard locations) | absent |
| Android SDK / `~/Library/Android` | absent |
| Gradle | absent |
| `kotlinc` | absent |
| Android Studio | absent |
| Java | present (26.0.2) — insufficient alone to build an APK |
| Android device over USB | none attached |

The handsets and SIMs being available to *you* does not make them reachable from *here*. **No result below is inferred, estimated or simulated.** Every result block stays empty until the experiment runs.

**Spike numbering — reconciliation.** Your instruction numbered the programmatic SMS test "SP-02". In this document that test is **SP-01b-A**, because **SP-02 was already assigned to peer sync** in `03`. Mapping:

| Your instruction | This document | Status |
|---|---|---|
| "SP-01b — SMS wire-format and payload test" | **SP-01b-M** (manual, no toolchain) + **SP-01b-A** (programmatic) | Materials ready |
| "SP-02 — Android SMS send/receive/throttle" | **SP-01b-A** Q1/Q2/Q3 | Materials ready, needs Android Studio |
| — | **SP-02** (peer sync) | Unchanged, still pending |

### 4.0.1 · SP-01b-M — manual SMS wire test ✅ **EXECUTED 2026-08-22 — PARTIAL PASS**

Because the build toolchain is missing, I generated a protocol that needs **only the two handsets and their stock SMS apps**. It answers the question that actually gates the transport decision — *does a full-size GSM-7 payload survive the carriers byte-identical?* — which SP-01a showed is sufficient, since text costs only ~11% more than binary.

1. **Assumption.** A 160-character GSM-7 payload sent between the two SIMs arrives unaltered, as the expected number of segments, within a usable latency.
2. **Smallest experiment.** `python3 spikes/sp01b_manual_payloads.py` prints five CRC-tagged payloads (120, 160, 161, 306, 459 chars). Paste each into the stock SMS app, send A→B and B→A, then paste what arrived into `python3 spikes/sp01b_manual_payloads.py --verify` for a mechanical EXACT MATCH / CORRUPTED verdict. **Time-box: 30 minutes.**
3. **Pass criteria.** T1 and T5 arrive EXACT MATCH in both directions; T1 shows as 1 segment; median latency <60 s.
4. **Fail criteria.** Any corruption of T1/T5; or T1 splitting unexpectedly; or latency routinely >5 min.
5. **Decision it gates.** Whether the GSM-7 text path is viable — which is the fallback that makes R-01 non-blocking. **If this passes, the SMS transport is viable even if binary SMS fails entirely.**
6/7. Payload generator only. No app, no architecture.
8. **ACTUAL RESULT — EXECUTED ON REAL HANDSETS, recorded 2026-08-22:**

| Test | Chars | Direction | Send time | Arrival time | Segments shown | Verify result |
|---|---|---|---|---|---|---|
| T1 | 160 | A→B | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T1 | 160 | B→A | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T2 | 161 | A→B | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T2 | 161 | B→A | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T3 | 306 | A→B | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T3 | 306 | B→A | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T4 | 459 | A→B | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T4 | 459 | B→A | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T5 | 120 | A→B | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |
| T5 | 120 | B→A | Not recorded | Not recorded | **Not visible** | **EXACT MATCH** |

**Totals:** 10 sends (5 payloads × 2 directions) · 10 received · **10 EXACT MATCH, 0 corrupted, 0 lost.**
Verified with the corrected tag-detecting verifier (`spikes/sp01b_manual_payloads.py --verify`).

**Not recorded / not observable in this run:** handset models · Android versions · carrier names · signal strength · send and arrival timestamps · segment counts (stock SMS app did not expose them). Per instruction these are recorded as *Not visible* / *Not recorded*, **not assumed**.

**PASS/FAIL against the predefined criteria — PARTIAL PASS**

| Predefined criterion | Verdict |
|---|---|
| T1 and T5 arrive EXACT MATCH in both directions | ✅ **PASS** |
| T1 shows as 1 segment | ⬜ **UNVERIFIED** — segment count not visible in the stock SMS app |
| Median latency <60 s | ⬜ **UNVERIFIED** — timing not recorded |

**What this result establishes**
1. The **base64url/GSM-7 alphabet survives both carriers unaltered** in both directions — no charset transcoding, no substitution, no truncation.
2. **Multi-segment payloads reassemble byte-identically.** T2 (161), T3 (306) and T4 (459) all matched exactly, so carrier-level concatenation and reassembly is transparent and lossless up to at least 459 characters. This is direct evidence that **batched events larger than one segment survive intact**.
3. The result is **bidirectional** — both SIMs and both carrier paths were exercised.

**What this result does NOT establish — stated explicitly**
1. **Segment economy is unvalidated.** An EXACT MATCH proves the payload survived; it does **not** prove T1 travelled as one segment. If a carrier split and reassembled it, the content would still match. **Therefore SP-01a's message-count arithmetic (TL-1, TL-3, TL-4) remains unvalidated** — payload integrity is not the same as segment economy.
2. **No latency figure exists.** NFR-03 remains unmeasured on the SMS path.
3. **No delivery-rate characterisation exists.** 10/10 arrived, but 10 sends is an integrity check, not a reliability statistic; the 20-send protocol in SP-01b-A is what produces that.
4. **The stock SMS app is not the RescueNet app.** Everything here went through the handset's built-in messaging client. Programmatic send/receive via `SmsManager`, the permission model, and the outgoing throttle are **entirely untested**.
5. **Binary / port-addressed SMS is untested** (SP-01b-A Q1).

---

Protocols below are specified in ready-to-run form with **empty result blocks**.

### 4.1 · SP-01b-A — programmatic SMS: binary, text, throttle ⏳ NOT YET RUN *(= your "SP-02")*
1. **Assumption.** Port-addressed binary SMS is delivered by the target Indian carriers between two handsets; and the outgoing throttle behaves approximately as documented (~30 messages / 30 minutes before a confirmation dialog).
2. **Smallest experiment.** A ~200-line throwaway Android app: `SEND_SMS` + `RECEIVE_SMS` permissions, a button that sends a fixed 134-byte payload via `sendDataMessage` to a chosen port, and a receiver logging arrival time. Send 20 messages at 30-second intervals, then 35 in rapid succession. Repeat with GSM-7 text (base64url) as control. **Time-box: 1 day.**
3. **Pass criteria.** ≥90% of binary messages delivered; median latency <60 s; throttle threshold identified.
4. **Fail criteria.** Binary SMS silently dropped by either carrier; or latency routinely >5 min; or the throttle fires below ~20 messages.
5. **Decision it gates.** Binary vs text encoding — **and no longer the transport choice itself**, because SP-01a showed text costs only ~11% more (§3.1 finding 2). If binary fails, use text; if both fail, the transport decision reopens.
6. **Spike code.** **Written and ready:** `spikes/android-sms-spike/MainActivity.kt` plus manifest and procedure in its README. Four buttons: Q1 binary x10, Q2 text x10, Q3 throttle x40, dump log. Throwaway — delete once results are recorded.
7. **Not architecture.** No RescueNet schema, no persistence, no UI beyond four buttons.
8. **ACTUAL RESULT.** `NOT YET RUN` — **blocked on Android Studio/SDK installation**, not on hardware availability (§4.0).

**Devices and conditions — record before starting**

| | Handset A | Handset B |
|---|---|---|
| Model | | |
| Android version | | |
| Carrier | | |
| Signal strength at test | | |
| Mobile data state | | |

**Q1 — binary (port-addressed) SMS, 134 B x 10**

| Direction | Sent | `SEND-RESULT OK` | `RECV BIN` received | Bytes decoded | Median latency | Max latency | Errors |
|---|---|---|---|---|---|---|---|
| A->B | 10 | | | | | | |
| B->A | 10 | | | | | | |

**Q2 — GSM-7 text SMS, 120 chars x 10**

| Direction | Sent | `SEND-RESULT OK` | `RECV TXT` received | Chars decoded | Segments | Median latency | Max latency | Errors |
|---|---|---|---|---|---|---|---|---|
| A->B | 10 | | | | | | | |
| B->A | 10 | | | | | | | |

**Q3 — throttle, 40 rapid text sends**

| Measurement | Observed |
|---|---|
| Seq at which `SEND-RESULT` first stopped being `OK` | |
| Confirmation dialog appeared? At which seq? | |
| Result code returned when throttled | |
| Messages actually delivered of 40 | |
| Recovery behaviour after 30 min | |

**Pass/fail against the predefined criteria** — tick only from the log: Q1 >=9/10 [ ] · Q2 >=9/10 [ ] · median latency <60 s [ ] · throttle threshold identified [ ]

**Limitations of whatever this produces:** two handsets, two carriers, one geography, one session. Enough to prove the mechanism; **not** enough to characterise reliability (`03` §6).

### 4.2 · SP-02 — peer sync viability ⏳ NOT YET RUN *(unchanged numbering — not the SMS test)*
1. **Assumption.** Two handsets can reliably discover each other and exchange a payload with no infrastructure, in a congested RF environment.
2. **Smallest experiment.** Throwaway app trying variant 2c (local-only hotspot + HTTP) and variant 2a (Nearby Connections): discover, connect, transfer 10 KB, record time-to-connect and success rate over 20 attempts — **once in a quiet room and once in a crowded space**, since the second condition is the one that matters. **Time-box: 1 day.**
3. **Pass criteria.** ≥80% connection success and <15 s time-to-connect **in the congested setting**.
4. **Fail criteria.** <50% success in congestion, or permission/OEM blockers on the demo devices.
5. **Decision it gates.** Whether L2-01 is promotable, and whether it may appear in the live demo (R-09).
6/7. Throwaway app; not architecture. **Not yet written** — deliberately deferred until SP-01b-A has run, since the transport decision may make it moot.
8. **ACTUAL RESULT.** `NOT YET RUN` — blocked on the same toolchain gap (§4.0).

| Variant | Attempts | Connects | Success % | Median time-to-connect | Environment (quiet / congested) | Errors |
|---|---|---|---|---|---|---|
| 2c hotspot+HTTP | 20 | | | | quiet | |
| 2c hotspot+HTTP | 20 | | | | congested | |
| 2a Nearby | 20 | | | | quiet | |
| 2a Nearby | 20 | | | | congested | |

### 4.3 · SP-03 — dashboard render load ⏳ NOT YET RUN
1. **Assumption.** A browser can render 5,000 grid cells plus 200 markers at interactive frame rates.
2. **Smallest experiment.** A static page drawing 5,000 polygons via the candidate map library's canvas/WebGL layer with synthetic data; measure initial render and pan/zoom frame timing. **Time-box: 0.5 day.**
3. **Pass criteria.** Initial render <2 s; pan/zoom stays interactive.
4. **Fail criteria.** Render >5 s or visible stutter — forces cell aggregation or tile-based rendering.
5. **Decision it gates.** Dashboard rendering approach; also produces the NFR-09 synthetic-load substitute (`03` §5.5).
6/7. Static page; not architecture.
8. **ACTUAL RESULT.** `NOT YET RUN` — needs the map library chosen first; not hardware-blocked.

| Measurement | Observed |
|---|---|
| Initial render, 5,000 cells | |
| Pan/zoom frame timing | |
| Marker count before degradation | |

### 4.4 · SP-04 — offline persistence survival ⏳ NOT YET RUN
1. **Assumption.** Local writes survive force-kill and reboot on the chosen mobile stack.
2. **Smallest experiment.** Minimal app writing 100 records to the embedded store; force-stop via `adb`; reboot; count survivors. Repeat 5×, including a write interrupted mid-transaction. **Time-box: 0.5 day.**
3. **Pass criteria.** 100% of acknowledged writes survive all cycles.
4. **Fail criteria.** Any acknowledged write lost — invalidates NFR-07 and forces a different store.
5. **Decision it gates.** Mobile stack choice (native Kotlin vs Flutter, `03` §3.4).
6/7. Throwaway app; not architecture.
8. **ACTUAL RESULT.** `NOT YET RUN` — blocked on the same toolchain gap (§4.0).

| Cycle | Records written | Force-stop survivors | Reboot survivors | Mid-transaction interrupt result |
|---|---|---|---|---|
| 1–5 | 100 each | | | |

---

## 5. Transport decision status — OPEN

**D-02 is not finalized.** Per instruction, it stays open until the spike evidence is complete.

### 5.1 What the executed evidence has already established
| Question | Status |
|---|---|
| Do events fit in an SMS budget? | **Yes, confirmed** — 19-event batch = 168 B = 2 SMS (§3.1) |
| Does binary-SMS rejection kill the SMS option? | **No** — text fallback costs ~11% more (§3.1 finding 2). R-01 downgraded from Med×High to **Low×Medium** |
| Is the throttle a demo blocker? | **Not on the uplink.** It constrains gateway downlink design instead (§3.1 finding 3) |
| Are the merge semantics sound under SMS-path conditions? | **Yes, 13/13** (§3.2) |
| Does a GSM-7 payload survive the target carriers intact? | **YES, confirmed on hardware** — 10/10 EXACT MATCH, bidirectional (§4.0.1) |
| Do multi-segment payloads reassemble losslessly? | **YES, confirmed** — up to 459 chars (§4.0.1) |
| How many segments does a 160-char payload consume? | **UNKNOWN** — not observable in the stock SMS app |
| What is SMS latency on these carriers? | **UNKNOWN** — not recorded |
| Does programmatic `SmsManager` send/receive work? | **UNKNOWN — SP-01b-A** |
| Is peer sync viable in a congested venue? | **UNKNOWN — SP-02** |

### 5.2 The decision gate
Finalize D-02 **only** when SP-01b and SP-02 have both recorded results. Then:

| SP-01b | SP-02 | Resulting decision |
|---|---|---|
| Pass (binary or text) | Any | **SMS = Level-1 mandatory fallback**; peer sync Level 2 — the `03` §2.6 recommendation stands, now on evidence |
| **↑ TRIGGERED 2026-08-22** | — | **SP-01b-M passed on the text path (§4.0.1). This row fires. D-02 closes — see `05` §1.** |
| Fail both encodings | Pass | **Peer sync = Level-1 fallback**; SMS documented as unavailable on tested carriers |
| Fail both encodings | Fail | Escalate: PS-K5 cannot be satisfied on available hardware. Fall back to a **simulated degraded transport**, labelled as simulated in every claim (`03` §5, AMB-19) |

**Unchanged regardless of outcome:** the sync engine is built transport-agnostic against a `send(bytes)`/`receive(bytes)` interface with event-log gossip above it. SP-05 has now demonstrated that this layering works, so the hedge is proven, not merely asserted.

---

## 6. Scope-risk assessment — the 67 dev-day Level-1 estimate

**Verdict: 67 dev-days is achievable but has no slack, and slack is what a demo needs.** The optimisation target is a prototype that works every time, not one that contains everything.

### 6.1 Which packages are essential to demonstrate the core problem

The problem statement's core is: *fragmented agencies → duplicated and missed search → no shared picture*. Four packages carry it, and none can be cut without a PS clause going uncovered.

| Package | Why essential | PS clauses at risk if cut |
|---|---|---|
| **L1-08** Sync engine + one degraded transport | The entire differentiator; EC-01 rests on it alone | PS-K4, PS-K5 |
| **L1-04** Offline-first field app | Without it there is no offline story and no field usability story | PS-K3, PS-K4, PS-B11 |
| **L1-03** Allocation, status, duplication | *Is* the problem statement — PS-B4, B5, B7, B13 in one package | PS-K1, PS-K2, PS-B4, PS-B5, PS-B7, PS-B13 |
| **L1-09** Commander dashboard | The shared operational picture itself; EC-02 rests on it | PS-B6, PS-K6–K9 |

Plus two enablers that cannot be removed because everything else depends on them: **L1-01** (grid) and **L1-02** (agencies/teams/attribution).

### 6.2 Which can be simplified without violating the problem statement

| Package | Full form | Simplified form still satisfying the PS | Saving |
|---|---|---|---|
| L1-01 Grid | Polygon drawing, configurable size, multiple areas | **Bounding-box only, two preset cell sizes.** PS-K1 says grid-based allocation; it does not require polygon drawing | 4 → 2 days |
| L1-02 Identity | Join by code + roles + scopes | **Seeded agencies/teams + join-by-code for the one demo join.** The join beat is EC-04 evidence and must survive | 4 → 3 days |
| L1-05 Position | GPS capture, thresholds, accuracy handling | **Cell-level position** (responder's current cell), GPS as a bonus. PS-K7 says "team positions", not "GPS coordinates" | 3 → 1 day |
| L1-06 Survivor | Full form with triage | **Count + status + optional triage.** Already minimal | 2 → 2 days |
| L1-07 Inventory | Per-team catalogue, totals | **3 fixed items per team, decrement only.** PS-K10 satisfied; nothing more is stated | 3 → 1.5 days |
| L1-09 Dashboard | Full metrics strip, filters, agency colouring | **Map + 4 metrics + agency colour.** Time-window filters and the fuller metric set are not stated anywhere | 9 → 6 days |
| L1-10 Interop | API + docs + mock partner + export | **API + generated docs + GeoJSON export.** Mock partner client is the strongest EC-04 evidence but is severable | 5 → 3 days |
| L1-08 SMS transport | Binary + text codecs | **One encoding only**, chosen by SP-01b. SP-01a shows either works | 7 → 5 days |

**Total simplified Level 1: ~45 dev-days** against 67, with every PS clause still covered.

### 6.3 Which can move to Level 2 if time is constrained

In cut order — first to go at the top:

| Cut | Package / element | What it costs | PS impact |
|---|---|---|---|
| 1 | L1-10 mock partner client | EC-04 evidence weakens from "demonstrated" to "documented API" | None — FR-901 still met |
| 2 | L1-05 GPS entirely (cell-level position only) | Team markers become cell-centred, not precise | None — PS-K7 still met |
| 3 | L1-09 metrics beyond the core four | Dashboard is leaner | None |
| 4 | L1-07 inventory beyond 3 items | Less impressive resource story | None — PS-K10 still met |
| 5 | L1-01 polygon drawing | Commander picks a bounding box | None — PS-K1 still met |
| **Never cut** | **L1-08, L1-04, L1-03, L1-09 map, L1-11** | — | Cutting any of these forfeits a scored criterion |

### 6.4 The Minimum Demonstrable Spine

The smallest end-to-end prototype that still strongly satisfies EC-01–EC-04. **~38 dev-days**, leaving ~29 days of the original 67 as genuine slack for the things that always overrun: device debugging, demo rehearsal, and the evidence pack.

| # | Element | Days | Criterion served |
|---|---|---|---|
| 0 | Spikes SP-01b, SP-02, SP-03, SP-04 | 3 | De-risks everything |
| 1 | Event log + merge + gossip over loopback transport | 7 | EC-01 (SP-05 has already validated the rules) |
| 2 | Bounding-box grid, two preset cell sizes | 2 | PS-K1 |
| 3 | Seeded agencies/teams + join-by-code + attribution | 3 | EC-04, PS-B7 |
| 4 | Field app: offline core, 3-tap actions, freshness header | 9 | EC-01, EC-03 |
| 5 | Cell allocation, 5 statuses, duplicate-effort detection | 5 | **EC-02 — the D-01 scenario** |
| 6 | Survivor report + 3-item inventory | 3 | PS-K9, PS-K10 |
| 7 | One SMS encoding + gateway (receive-mostly) | 5 | PS-K5, EC-01 |
| 8 | Dashboard: map, 4 metrics, agency colour, **data age** | 6 | EC-02 |
| 9 | API + generated docs + GeoJSON export | 3 | EC-04 |
| 10 | Evidence pack + 4 rehearsed demo scripts | 4 | All four |
| | **Total** | **~38** | |

**What the spine deliberately omits:** polygon drawing, GPS precision, mock partner client, alert feed, timeline, dark mode, Hindi, basemap tiles, conflict-resolution UI, priority queueing, peer sync. None of these leaves a PS clause uncovered.

**The one addition I would fund from the recovered slack, in this order:** (1) the **mock partner client** (+2 days — converts EC-04 from claim to demonstration); (2) **basemap tile pack** (+2 days — disproportionate credibility for the field app); (3) **after-action summary** (+2 days — quantifies PS-B12/B13, the statement's own success outcomes).

### 6.5 Critical-path warning
L1-08 (element 1) blocks elements 4, 5, 6, 7 and 8. It is the longest pole and the least demonstrable in isolation, which makes it the item most likely to be deferred and the most damaging to defer. **It must start first and be exercised continuously against the loopback transport** — SP-05 shows what that exercise looks like.

---

## 7. Updated risk register (changes only)

| ID | Risk | Was | Now | Why changed |
|---|---|---|---|---|
| R-01 | Carrier drops binary SMS | Med × High | **Low × Medium** | SP-01a: text fallback costs ~11% more, not a blocker |
| R-02 | SMS throttle interrupts demo | Med × High | **Low × Medium** (uplink) / **Med × Med** (gateway downlink) | SP-01a: relocated to the downlink; mitigated by receive-mostly gateway |
| R-12 | *(new)* Merge policy proves insufficient, forcing CRDT work | — | **Low × High** | SP-05: 13/13 on the adversarial cases; policy validated pre-architecture |
| R-13 | *(new)* Spike code leaks into the build | — | **Med × Medium** | Mitigation: `spikes/` stays outside the repo build; rewrite, never copy |
| R-03 | Sync engine started late | Med × Critical | **unchanged — still the top risk** | §6.5 |
| R-05 | Evidence pack dropped under pressure | High × High | **unchanged** | §6.4 element 10 reserves the days |

---

## 8. Next gate — conditions for starting architecture

Architecture begins when **all** of these are true:

- [x] D-01 applied and validated (§1, §3.2)
- [x] Merge/convergence policy validated pre-architecture (§3.2)
- [x] Payload budget established (§3.1)
- [x] Scope risk reviewed and a Minimum Demonstrable Spine defined (§6)
- [ ] **SP-01b executed** — real-carrier SMS result recorded (§4.1)
- [ ] **SP-02 executed** — peer sync viability recorded (§4.2)
- [ ] **SP-03, SP-04 executed** — render load and offline persistence recorded (§4.3, §4.4)
- [ ] **D-02 finalized** on that evidence (§5.2)
- [ ] Scope tier confirmed by you: full Level 1 (67 d), simplified Level 1 (~45 d), or Minimum Demonstrable Spine (~38 d)

**Decisions requested now:**

| # | Decision | Recommendation |
|---|---|---|
| 1 | Confirm **AS-02** — are 2 Android handsets and 2 SMS-capable SIMs actually available? | Needed before SP-01b/SP-02 can be scheduled at all |
| 2 | Which scope tier to target | **Minimum Demonstrable Spine (~38 d)**, then spend recovered slack on the three additions in §6.4 |
| 3 | Who runs SP-01b–SP-04, and when | Time-boxed at 3 days total; they gate the architecture phase |
| 4 | Whether I should write the four throwaway spike apps as specified in §4 | Say the word — they are ~200 lines each and explicitly disposable |
