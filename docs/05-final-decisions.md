# RescueNet AI — Final Decisions (v1.0)

**Date:** 2026-08-22 · **Stage:** Decisions locked — architecture still deferred
**Source of truth:** the official problem statement. **Companions:** [`01`](01-requirements-analysis.md) · [`02`](02-prototype-scope.md) · [`03`](03-feasibility-analysis.md) · [`04`](04-feasibility-validation.md)

---

## 0. Status of this document

Five of the seven items you asked to finalize are **final** and binding. Two depend on evidence that does not exist yet.

| # | Item | Status |
|---|---|---|
| 1 | Fallback transport | ✅ **FINAL** — closed 2026-08-22 on SP-01b-M hardware evidence |
| 2 | Transport limitations | **PARTIALLY FINAL** — §2.1 final; §2.2 reduced but not empty (encoding, segments, latency, throttle still open) |
| 3 | Minimum demonstrable prototype scope | **FINAL** |
| 4 | Required Level-1 packages | **FINAL** |
| 5 | Deferred packages | **FINAL** |
| 6 | Accepted prototype limitations | **FINAL** |
| 7 | Conditions for claiming a feature works | **FINAL** |

**Item 1 closed 2026-08-22.** SP-01b-M was executed on real handsets: 10 sends, 10 received, **10 EXACT MATCH, 0 corrupted, 0 lost**, bidirectional (`04` §4.0.1). The pre-committed decision table was applied mechanically — see §1.2. No judgement was added beyond the rule agreed in advance.

**Item 2 is narrower but not closed.** SP-01b-M validated payload *integrity*; it did not validate segment economy, latency, delivery rate, or any programmatic API behaviour, because segment counts were not visible in the stock SMS app and timings were not recorded. Those remain open (§2.2).

---

## 1. Fallback transport — ✅ FINAL (closed 2026-08-22)

### 1.1 Standing recommendation
**SMS-based synchronisation is the intended Level-1 mandatory fallback**, on the reasoning in `03` §2.6 (unambiguous PS-K5 compliance, survives a congested demo venue, testable in CI behind a loopback transport, matches the dispersed geometry of a disaster site, no external dependencies), now strengthened by executed evidence in `04` §3.1.

### 1.2 The pre-committed decision rule — APPLIED

**Evidence in:** SP-01b-M, executed on real handsets 2026-08-22. T1 (160) and T5 (120) both **EXACT MATCH in both directions**; T2, T3, T4 also EXACT MATCH. 10/10 sends received uncorrupted (`04` §4.0.1).

**Mechanical application:**
- The condition *"T1 & T5 EXACT MATCH both directions"* is **satisfied**.
- Rows 3, 4 and 5 all require *"Corruption or loss on T1/T5"*. That condition is **false**, so all three are **eliminated**.
- Rows 1 and 2 both conclude **"SMS confirmed"**. They differ *only* in which encoding is used.
- **Therefore the transport decision is determined by SP-01b-M alone.** The outstanding Q1 binary result can no longer change *whether* SMS is the fallback — only *how it is encoded*.

> ### **D-02 FINAL: SMS-based synchronisation is the Level-1 mandatory fallback transport.**
> **Peer sync (L2-01) is confirmed at Level 2.** PS-K5 is satisfied by the SMS branch.
> **Encoding is now CLOSED — GSM-7 text (D-02a, 2026-08-24).** SP-01b-A Q1 was executed and **failed**: 10/10 `sendDataMessage` calls returned `GENERIC_FAILURE` and 0/10 were received. The pre-committed rule *binary if Q1 passes, GSM-7 text otherwise* therefore selects **text**, which the hardware had already proven viable. See §1.2a.

### §1.2a SP-01b-A — executed 2026-08-24, D-02a closed

SP-01b-A ran on two physical handsets with two SMS-capable SIMs on two different carriers.
This is the spike that D-02a, T-23 and blocker **B-4** were all waiting on.

| | Handset A | Handset B |
|---|---|---|
| Model | vivo **V2151** | OPPO **CPH2859** |
| Android | 14 (API 34) | 16 (API 36) |
| Carrier (MCC-MNC) | **405855** — Jio | **40556** — Airtel |
| Network at test | LTE | LTE |

**Q1 — port-addressed binary, 134 B × 10. FAILED.**

| Direction | Sent | Delivered | Errors |
|---|---|---|---|
| A→B | 10 | **0** | **10 × `GENERIC_FAILURE`** from `SmsManager.sendDataMessage` |
| B→A | **not captured** | — | OEM/UI-drive limitation — **not tested, and not claimed** |

The failure is at the send API on the handset: the messages never reached the air, and no
SMS-provider evidence of delivery exists. Pass criterion was ≥9/10 received at 134 B.

**Q2 — GSM-7 text, nominal 120 chars × 10. Mixed, and the shortfall is recorded.**

| Direction | Delivered | Segments | Median latency | Max latency |
|---|---|---|---|---|
| A→B | **10/10** | **1** | **1.6 s** | 6.4 s |
| B→A | **8/10** | **1** | ~2 s early, then a carrier-side stall | ~63 s |

B→A is **below the ≥9/10 pass bar**: two messages never arrived, and three were held and
burst-delivered together. **The nominal "120 chars" setting produced 115–116 actual payload
characters** — the spike generator's own framing accounts for the difference. That distinction
matters when reading the byte budget: the 120 B figure is the *budget*, not an observed payload.

**Q3 — throttle, 40 rapid sends on Airtel. Threshold NOT located.**

35 distinct messages were observed delivered, every captured `SEND-RESULT` was `OK`, and **no
confirmation dialog appeared**. This establishes a **lower bound only**: *throttle not observed
through 40 sends; threshold remains unlocated.* No threshold may be inferred from this run.

**What this closes, and what it does not.** D-02a and T-23 are closed. **TL-10 is not** —
segment economy still rests on `segments=1` observations at ~116 chars, not on a carrier-side
segment count, and the throttle remains unmeasured. Both stay **non-blocking** for M8: the
codec packs to a declared `max_batch_bytes`, and the retry policy is fixed by DM-56
independently of where the throttle actually sits.

The original table, retained for audit:

| SP-01b-M (manual text) | SP-01b-A Q1 (binary) | Decision — automatic |
|---|---|---|
| T1 & T5 EXACT MATCH both directions | ≥9/10 delivered | **SMS confirmed. Use binary encoding.** Peer sync → Level 2 |
| T1 & T5 EXACT MATCH both directions | <9/10 or dropped | **SMS confirmed. Use GSM-7 text encoding.** Costs ~11% more messages (`04` §3.1) — no other consequence |
| Corruption or loss on T1/T5 | ≥9/10 delivered | **SMS confirmed, binary only.** Text path documented as unreliable on tested carriers |
| Corruption or loss on T1/T5 | <9/10 | **SMS rejected.** Escalate to SP-02 peer sync as Level-1 fallback |
| Both fail, and SP-02 also fails | | **PS-K5 not satisfiable on available hardware.** Fall back to a simulated degraded transport, labelled "simulated" in every claim, slide and demo (`03` §5, AMB-19) |

**Rows eliminated by evidence:** 3, 4, 5 (all require corruption/loss that did not occur). **Rows still live:** 1 and 2 — identical in transport, differing only in encoding.

### 1.3 Binding regardless of outcome
These hold under every branch above and are **final now**:
- The sync engine is built against a **transport-agnostic `send(bytes)` / `receive(bytes)` interface**. No SMS semantics leak upward.
- Reconciliation is **event-log gossip**, not point-to-point state push. Validated 13/13 in `04` §3.2 before any architecture exists.
- Event identity is **`(device_id, seq)` = 4 bytes**. UUIDs are prohibited on the wire — 16 B/event is unaffordable (`04` §3.1 finding 4).
- The gateway is **receive-mostly**. Assignments go out over data where available; SMS downlink is used only for the demo's two teams (`04` §3.1 finding 3).
- Position capture is **event-driven, never streamed** (PI-08, confirmed by `04` §3.1 finding 6).

---

## 2. Transport limitations

### 2.1 Established by executed evidence — FINAL

| # | Limitation | Source |
|---|---|---|
| TL-1 | A field batch of 19 events is **168 bytes = 2 SMS**. Individual events cost 8–13 B batched. | `04` §3.1 |
| TL-2 | **Text SMS carries 120 B vs binary's 134 B** — an ~11% efficiency penalty, not a functional difference. | `04` §3.1 |
| TL-3 | **Field uplink is not throttle-constrained** at any realistic volume: 11 SMS/device across a full 8-hour shift. | `04` §3.1 |
| TL-4 | **Gateway downlink is throttle-constrained.** SMS has no broadcast; one gateway sending to 20 teams over 3 assignment cycles reaches ~60 messages and exceeds the ~30/30 min limit. | `04` §3.1 |
| TL-5 | **Continuous position telemetry is impossible over SMS.** Event-driven capture is mandatory, not an optimisation. | `04` §3.1 |
| TL-6 | **SMS cannot operate when cellular service itself is down** — a realistic disaster condition this prototype does not solve. Peer sync (Level 2) is the only candidate that survives it. | `03` §2.6 |
| TL-7 | Delivery **ordering is not guaranteed**; latency is outside our control. Handled by dedupe, retry and server-receipt ordering. | `03` §3.8 |
| TL-8 | **The GSM-7 base64url payload transits both test carriers byte-identically**, bidirectionally — no transcoding, substitution or truncation. Hardware-validated. | `04` §4.0.1 |
| TL-9 | **Multi-segment payloads reassemble losslessly** up to at least 459 characters, so batches spanning several segments survive intact. Hardware-validated. | `04` §4.0.1 |
| TL-10 | **Segment economy is unvalidated.** An EXACT MATCH proves the payload survived, not that it used the expected number of segments — so the message-count arithmetic behind TL-1, TL-3 and TL-4 **remains theoretical**. | `04` §4.0.1 |

### 2.2 Still pending — cannot be stated yet

Narrowed by SP-01b-M, but not empty:

| Open question | Spike that closes it |
|---|---|
| ~~Carrier acceptance of port-addressed **binary** SMS~~ | **CLOSED 2026-08-24 — Q1 failed, binary rejected (§1.2a)** |
| **Segments consumed** per payload size (gates TL-1/3/4 message arithmetic) | SP-01b-A Q1/Q2 logging, or a carrier-side check |
| **Latency** distribution on the SMS path (NFR-03) | **Partially closed** — Q2 median 1.6 s / max 6.4 s A→B, max ~63 s B→A (§1.2a). Small sample |
| **Delivery rate** over a statistically meaningful run | SP-01b-A (20-send protocol) |
| Programmatic `SmsManager` send/receive behaviour and permission model | SP-01b-A |
| Real **throttle** threshold | **Still open** — Q3 saw no throttle through 40 sends; threshold unlocated (§1.2a). No confirmation dialog appeared |
| ~~Handset models, Android versions, carrier names~~ | **CLOSED — recorded in §1.2a** |

**Until recorded, none of these may appear in any claim, slide or document.**

---

## 3. Minimum demonstrable prototype scope — FINAL

**The Minimum Demonstrable Spine, ~38 developer-days** (`04` §6.4). This is the committed scope. It covers every problem-statement clause and all four evaluation criteria.

| # | Element | Days | Serves |
|---|---|---|---|
| 0 | Spikes SP-01b, SP-02, SP-03, SP-04 | 3 | De-risks everything |
| 1 | Event log + merge + gossip over loopback transport | 7 | EC-01 |
| 2 | Bounding-box grid, two preset cell sizes | 2 | PS-K1 |
| 3 | Seeded agencies/teams + join-by-code + attribution | 3 | EC-04, PS-B7 |
| 4 | Field app: offline core, 3-tap actions, freshness header | 9 | EC-01, EC-03 |
| 5 | Cell allocation, 5 statuses, duplicate-effort detection | 5 | EC-02 |
| 6 | Survivor report + 3-item inventory | 3 | PS-K9, PS-K10 |
| 7 | One SMS encoding + receive-mostly gateway | 5 | PS-K5, EC-01 |
| 8 | Dashboard: map, 4 metrics, agency colour, **data age** | 6 | EC-02 |
| 9 | API + generated docs + GeoJSON export | 3 | EC-04 |
| 10 | Evidence pack + 4 rehearsed demo scripts | 4 | All four |
| | **Total** | **~38** | |

**Recovered slack (~29 days against the original 67) is spent in this order, and only in this order:** mock partner client (+2) → basemap tile pack (+2) → after-action summary (+2) → remainder held for device debugging and rehearsal.

**Critical path.** Element 1 blocks elements 4, 5, 6, 7 and 8. It starts first and is exercised continuously against the loopback transport. Deferring it is the single most damaging schedule decision available.

---

## 4. Required Level-1 packages — FINAL

Cutting any of these leaves a problem-statement clause uncovered or forfeits a scored criterion.

| Package | Requirement IDs | Why non-negotiable | PS clauses |
|---|---|---|---|
| **L1-08** Sync engine + one degraded transport | FR-801, 802, 803, 806, 807, 1001, 1002; NFR-01, 03, 14, 15 | The entire differentiator; EC-01 rests on it alone | PS-K4, PS-K5 |
| **L1-04** Offline-first field app | FR-401–404, 407–410; NFR-02, 04, 05, 07, 08 | No offline story and no usability story without it | PS-K3, PS-K4, PS-B11 |
| **L1-03** Allocation, status, duplicate-effort detection | FR-301–305, 307, 309, 706 | *Is* the problem statement | PS-K1, K2, B4, B5, B7, B13 |
| **L1-09** Commander dashboard | FR-701–705 | The shared operational picture; EC-02 | PS-B6, PS-K6–K9 |
| **L1-01** Grid *(simplified: bounding box, preset sizes)* | FR-201–204 | Everything hangs off the grid | PS-K1 |
| **L1-02** Agencies, teams, attribution, join-by-code | FR-101–107 | Multi-agency is the premise; EC-04's best beat | PS-B2, PS-K11, PS-T1–T4 |
| **L1-06 + L1-07** Survivor report + inventory *(minimal)* | FR-501, 601–603, 606 | Two of MC-09's three commander questions | PS-B8, PS-B9, PS-K9, PS-K10 |
| **L1-10** API + docs + GeoJSON export | FR-901, 902, 903, 905 | EC-04 needs a real contract | PS-K11 |
| **L1-11** Evidence and measurement | NFR-01, 03, 04, 14 | Three of four criteria are judged on evidence, not features | PS-E1–E4 |

**L1-05 (position)** is retained in reduced form only: **cell-level position**, GPS as a bonus. PS-K7 says "team positions", not "GPS coordinates".

---

## 5. Deferred packages — FINAL

### 5.1 Deferred to Level 2 (build only after Level 1 verifies)
L2-01 peer sync *(promotion candidate — see §1.2)* · L2-02 search quality levels · L2-03 hazards, clues, media · L2-04 alert feed and snapshot export · L2-05 resource requests and depletion flags · L2-06 sync refinements *(except two-tier priority, promoted to Level 1 at +1 day)* · L2-07 conflict-resolution UI · L2-08 dark mode, SOS, Hindi, basemap tiles · L2-09 interoperability depth · L2-10 after-action summary · L2-11 security and privacy hardening · L2-12 grid refinements.

### 5.2 Deferred to Level 3
All of OF-01…OF-14, including **all AI capability**. Rule-based cell prioritisation (OF-01) remains the answer to AMB-01 and the justification for the product name, and is the first Level-3 item to promote if Levels 1 and 2 complete early. Also: full CRDT semantics · multi-cluster split-brain handling · NFR-09 load testing · iOS · multi-incident rollup · full EDXL conformance.

### 5.3 Deferred to production (documented, never claimed as built)
FE-01 offline command centre / edge server *(closed by D-01)* · FE-02 federated multi-instance operation · FE-03 CAP/EDXL standards conformance · FE-04 LoRa or radio-bridge mesh · FE-05 multi-incident authority rollup.

**Traceability preserved.** Every deferred item keeps its ID, source clause and provenance tag in `01`–`03`. Nothing has been deleted from the register.

---

## 6. Accepted prototype limitations — FINAL

These are accepted, not defects. Each must be stated openly in the submission and demo.

| # | Limitation |
|---|---|
| AL-01 | **No disaster-grade reliability is established.** No dust, heat, drops, panic, multi-day operation or real casualties. No planned test produces this evidence. |
| AL-02 | **Commander dashboard requires connectivity** (D-01). It does not work offline; the offline story is field-side only. |
| AL-03 | **SMS fails entirely when cellular service is down** (TL-6). The prototype does not solve the hardest connectivity case. |
| AL-04 | **Trust-on-first-use identity.** Anyone with a join code joins as that team. No verification, no revocation, no device binding. |
| AL-05 | **Ordering uses server receipt time, not true causality.** Two events created offline in a known order may be recorded out of order. |
| AL-06 | **Offline endurance demonstrated in hours, not the 24 h of NFR-02.** |
| AL-07 | **Positions are last-known, not live**, and may be absent or wrong by tens of metres inside rubble. Cell-level granularity is the realistic indoor limit. |
| AL-08 | **Survivor triage vocabulary is unvalidated** — not reviewed by any medical or SAR professional. Not a clinical tool. |
| AL-09 | **Inventory tracks what is reported, not what is real.** No physical reconciliation. |
| AL-10 | **No real external agency system integrated.** The interoperability partner is a mock client we wrote. |
| AL-11 | **Duplicate survivor reports are not merged** at Level 1 — both are shown. |
| AL-12 | **One or two device models, one or two carriers, one geography, one venue.** OEM-specific and carrier-specific failures are unknown. |
| AL-13 | **All demo data is synthetic.** No real survivor or casualty data at any point. |
| AL-14 | **Spike results prove rules and budgets, not implementations.** `04` §3.1 is arithmetic over a proposed schema; §3.2 is in-memory logic with perfect delivery. |

---

## 7. Conditions for claiming a feature works — FINAL

**The governing rule:** a feature may be claimed to work only when the evidence in the middle column exists and has been recorded with its date and conditions. **No evidence, no claim.** Every quantitative claim carries its sample size and conditions in the same sentence.

| Claim | Required evidence before it may be made | Status |
|---|---|---|
| "Field data entry works offline" | Recorded airplane-mode run: full task set, force-kill, reboot, all records survive — repeated on every build | ⏳ pending build |
| "A GSM-7 payload crosses these carriers byte-identically, both directions" | SP-01b-M decode results | ✅ **`04` §4.0.1 — claimable now**, as "10/10 sends, 5 payload sizes, 2 directions, 2 handsets, integrity only" |
| "Multi-segment payloads reassemble losslessly up to 459 chars" | SP-01b-M T2/T3/T4 results | ✅ **claimable now**, with the same sample-size qualifier |
| "The RescueNet app syncs over SMS with mobile data off" | SP-01b-A recorded programmatic delivery + the built app | ⏳ pending — SP-01b-M used the **stock SMS app**, not our code |
| "A 160-character payload costs one SMS" | Observed segment counts | 🚫 **not claimable** — segments were not visible (`04` §4.0.1) |
| "SMS latency is under N seconds" | Recorded timings | 🚫 **not claimable** — not measured |
| "SMS delivery is reliable at X%" | 20-send protocol results | 🚫 **not claimable** — 10 sends is integrity, not a reliability statistic |
| "Payloads fit a low-bandwidth budget" | Measured bytes per event type | ✅ **`04` §3.1 — may be claimed now** |
| "Duplicate search effort is detected and nothing is discarded" | The D-01 seven-step scenario passing end-to-end on real devices | 🟡 rules validated (`04` §3.2, 13/13); **end-to-end pending** |
| "Offline devices converge deterministically" | Automated convergence tests over the loopback transport, plus a two-device partition/reunite run | 🟡 simulation passes; **device run pending** |
| "Untrained responders can use it" | Raw per-participant results from 3–5 first-time users, sample size attached | ⏳ pending |
| "An external system can integrate" | Mock partner round-trip recording + GeoJSON opened in third-party GIS | ⏳ pending |
| "Handles 5,000 cells / 200 teams" | SP-03 synthetic-load render timings — stated as synthetic, not concurrent real devices | ⏳ pending |
| "Works reliably in disaster conditions" | **No evidence can exist.** | 🚫 **never claimable** |
| "24-hour offline endurance" | Not obtainable in this schedule. Substitute: 90-minute recorded session + one overnight soak + a no-TTL-by-design argument | 🚫 claim only the substitute |
| "Interoperable with NDRF / fire / police systems" | No such integration is planned | 🚫 **never claimable** |
| Binary SMS **does not work** on the tested handset/carrier | SP-01b-A Q1 (§1.2a) | ✅ **claimable** as "0/10 delivered, 10/10 `GENERIC_FAILURE`, one direction tested" |
| Anything about the **throttle threshold** | SP-01b-A Q3 (§1.2a) | 🚫 **not claimable** — not located. Only "not observed through 40 sends" |

**Legend:** ✅ claimable now · 🟡 partially evidenced, claim must be qualified · ⏳ evidence pending · 🚫 not claimable

**Standing rule on simulated results.** Anything produced by simulation, loopback or synthetic load is labelled as such in the same breath. `04` separates executed from pending results structurally, and that separation must survive into the slides.

---

## 8. What must happen to close items 1 and 2

| # | Action | Owner | Blocks |
|---|---|---|---|
| ~~1~~ | ~~Run **SP-01b-M**~~ | You | ✅ **DONE 2026-08-22 — closed D-02** |
| 2 | Install Android Studio + SDK | You | SP-01b-A, SP-02, SP-04 |
| 3 | Build and run **SP-01b-A** — `spikes/android-sms-spike/`, Q1/Q2/Q3 | You | §1.2 fully |
| 4 | Record every field into `04` §4.0.1 and §4.1 result tables | You | §2.2 |
| 5 | ~~Apply §1.2 mechanically; mark D-02 final~~ | Me | ✅ **DONE — §1.2** |
| 6 | Record segment counts by another means (carrier bill, operator tool, or SP-01b-A logging) | You | TL-10, message arithmetic |

**D-02 is closed.** What remains is *encoding and economy*, not *whether SMS is the transport*. Architecture can proceed on the SMS branch: the transport-agnostic interface (§1.3) makes the encoding choice a codec detail, not a structural one.

---

## 10. Cell label rule — FINAL (2026-08-23)

Resolved during M2 implementation, which found the label formula **unspecified**:
docs/01 FR-204 gives `B-14`; docs/01 TC-09 / AMB-04 say "Letter-Number"; docs/02 §5 and
docs/03 §3.1 say `A1…N` and warn of `AA1` beyond 26 columns. None of these establishes
orientation, base or separator. The implementation refused to guess and left
`Grid.cell_label()` unimplemented until this decision.

### 10.1 The rule

```
label = <COLUMN LETTERS> "-" <ROW NUMBER>
```

| Element | Rule |
|---|---|
| **Columns** | Alphabetic, Excel-style bijective base-26: `A…Z, AA, AB… ZZ, AAA` |
| **Rows** | Decimal, unpadded |
| **Display base** | **1-based** — the first cell is `A-1` |
| **Internal base** | **0-based** — `cell_index`, `row` and `col` are unchanged |
| **Separator** | Hyphen, following FR-204's `B-14` |
| **Derivation** | `row, col = divmod(cell_index, cols)` → `f"{letters(col)}-{row + 1}"` |
| **Status** | **Derived presentation only.** Never transmitted (DM-10), never stored as canonical event data, never part of the event schema |

### 10.2 Why this and not the alternative

Letters index **columns**, not rows, because docs/03 §3.1 warns of "`AA1` beyond 26
columns" — that warning only makes sense if letters run along the column axis. Bijective
base-26 is what makes `Z → AA` correct rather than ambiguous, answering that warning
directly. 1-based display matches `B-14`, `A1…N` and ordinary radio speech; 0-based
internals are untouched, so the 13-bit wire field, `MAX_CELLS = 8191` and the event
format are all unaffected.

### 10.3 Worked examples (grid `rows=25, cols=200`)

| `cell_index` | row | col | label |
|---|---|---|---|
| 0 | 0 | 0 | `A-1` |
| 1 | 0 | 1 | `B-1` |
| 13 | 0 | 13 | `N-1` |
| 199 | 0 | 199 | `GR-1` |
| 200 | 1 | 0 | `A-2` |
| 213 | 1 | 13 | `N-2` |
| 214 | 1 | 14 | `O-2` |

Column boundaries: `col 25 → Z`, `col 26 → AA`, `col 701 → ZZ`, `col 702 → AAA`.
Largest grid (`8191×1`): `cell_index 8190 → A-8191`.

### 10.4 Correction: `B-14` was never `cell_index 214`

docs/08 §16.6 previously showed `"cell_index": 214, "label": "B-14"` in one projection
example. **That pairing is arithmetically impossible under any integer grid width.**
`B-14` means column 1, display row 14, so `cell_index = 13 × cols + 1`; solving
`13 × cols + 1 = 214` gives `cols = 16.3846…`, which is not an integer.

The inconsistency was in the *example*, not in any decision. Corrected by keeping
`cell_index 214` — which appears as structured data in 13 shared fixtures and roughly
thirty JSON examples across docs/08 and docs/09 — and fixing the label to `O-2`, the
value the rule actually produces for the documented grid. **No wire format, schema,
identity or architecture decision changed.**

`B-14` remains a perfectly valid label; at `cols=200` it is `cell_index 2601`.

**What was aligned, and what was deliberately left alone.** Three places bound a label to
a numeric index and are now consistent: docs/08 §16.6 (the projection example), docs/08
§13.2 (the audit narrative over the same events) and docs/09 §1.3 (the audit query on
`entity_id=214`). All three now read `O-2`.

Everywhere else "B-14" is a **free-standing illustrative label** with no index attached —
docs/01 FR-204 and EC-02, docs/03, docs/06 §5.2, docs/11 TR-32 — and is left unchanged; a
label example does not need to name a particular cell.

**docs/04 is not edited under any circumstances.** Its "B-14" strings are the recorded
output of spike SP-05, which used the label as an opaque cell identifier. That document
holds executed evidence, and evidence is never retrofitted to match a later decision.

---

## 9. Decision log

| ID | Decision | Date | Status |
|---|---|---|---|
| D-01 | Dashboard need not operate offline; offline architecture is field-side only | 2026-08-22 | **Final** |
| D-01b | Duplicate **search effort** replaces duplicate **assignment** as the demonstration scenario | 2026-08-22 | **Final** — validated 13/13 (`04` §3.2) |
| D-02 | **Level-1 fallback transport = SMS**; peer sync at Level 2 | 2026-08-22 | ✅ **Final** — closed on SP-01b-M hardware evidence (`04` §4.0.1) |
| D-02a | SMS **encoding** = **GSM-7 text**; `max_batch_bytes` = **120 B** | 2026-08-24 | ✅ **Final** — SP-01b-A Q1 **failed** (0/10 binary delivered, 10/10 `GENERIC_FAILURE`). Binary/134 B path **rejected on evidence**, not merely unvalidated. §1.2a |
| D-03 | Committed scope = Minimum Demonstrable Spine (~38 dev-days) | 2026-08-22 | **Final** (§3) |
| D-04 | Two-tier transmission priority promoted from L2-06 into Level 1 (+1 day) | 2026-08-22 | **Final** |
| D-05 | Event identity on the wire is `(device_id, seq)`; UUIDs prohibited | 2026-08-22 | **Final** (`04` §3.1) |
| D-06 | Gateway is receive-mostly | 2026-08-22 | **Final** (`04` §3.1) |

**D-02 has closed, and as of 2026-08-24 so has D-02a.** Every decision the SMS branch depends on is now locked: the transport (D-02, SMS) and the encoding (D-02a, **GSM-7 text**, `max_batch_bytes` **120 B**). What remains open — segment economy (TL-10) and the throttle threshold — is measurement detail behind the transport interface, not a decision, and neither blocks M8. See §1.2a.
