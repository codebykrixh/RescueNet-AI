# RescueNet AI — Requirements Validation & Prototype Scope Review (v1.0, for approval)

**Status:** Draft for approval · **Date:** 2026-08-22 · **Stage:** Scope definition (no architecture, no code)
**Primary source of truth:** the official problem statement. **Companion document:** [`01-requirements-analysis.md`](01-requirements-analysis.md) — all requirement IDs, sources and provenance tags defined there remain valid and unchanged. This document **classifies and levels** them; it does not restate or replace them.

---

## 0. Decision log

| ID | Decision | Date | Effect |
|---|---|---|---|
| **D-01** | The commander web dashboard **does not need to operate fully offline** in this prototype. Offline and low-connectivity architecture serves **field responders and field data synchronisation** only. No on-site edge server, no offline command-centre architecture in prototype scope. | 2026-08-22 | Closes AMB-18 (the one blocking question). Moves **FR-711**, **NFR-17** and **PI-09** out of prototype scope to §8 Future production extensions. Restates **NFR-08** to field-side only. Traceability for all three is preserved, not deleted. |
| **D-02** | Prototype satisfies **PS-K5** with **one** degraded-path transport at Level 1 (SMS), because the statement says "mesh-network **or** SMS-based sync". Mesh/peer sync moves to Level 2. | 2026-08-22 (proposed) | See §4.3. Reverses the "build both" default recommended in `01`, on anti-overengineering grounds. Requires your confirmation. |

---

## 1. How to read this document

### 1.1 The classification question (applied to every Must)

| Class | Meaning | How it must be described in any submission or pitch |
|---|---|---|
| **A — Directly required** | Stated in the problem statement. | "Required by the problem statement." |
| **B — Necessary implied behaviour** | Not stated, but a class-A requirement does not actually work without it. | "Required to make [PS clause] work." |
| **C — Engineering implementation detail** | *How* we intend to satisfy an A or B requirement. A different mechanism could satisfy the same requirement. | "Our chosen mechanism for [requirement]." **Never** "a requirement of the problem statement." |
| **D — Proposed enhancement** | Beyond the statement altogether. | "Enhancement beyond the stated scope." |

Class is **independent of level**. A class-C item can still be Level 1 (a store must exist for the app to work offline), and a class-A item can still be Level 2 where the statement's own wording gives a choice (PS-K5's "or").

### 1.2 The three levels

| Level | Definition | Test for membership |
|---|---|---|
| **LEVEL 1 — MUST BUILD** | Required for a convincing working prototype **and** direct fulfilment of the problem statement. | If this is missing, either a PS clause is uncovered, or the demo does not convince. |
| **LEVEL 2 — SHOULD BUILD** | Materially strengthens performance against EC-01…EC-04, but can be **simplified** for the prototype. | Improves a scored criterion; a reduced version is honest and sufficient. |
| **LEVEL 3 — OPTIONAL / ADVANCED** | Beyond prototype necessity. | Nothing in the statement is left uncovered by its absence. |

### 1.3 Governing anti-overengineering rules

1. **No class-C item is ever presented as a mandatory requirement.** (§9)
2. **No Level 1 item exists without a PS clause behind it** — directly (A) or through a chain (B → A).
3. **Level 2 items are built in reduced form by default.** Full form only after all of Level 1 is verified.
4. **Level 3 is not started** until Levels 1 and 2 are complete and demonstrable.
5. **Traceability is never deleted.** Deferred requirements keep their IDs, sources and provenance, and are marked *Deferred — D-01* rather than removed.

---

## 2. Classification of every Must requirement

All 71 requirements previously classified **Must** in `01-requirements-analysis.md`. `Src` and `Prov` (E/I/P) are carried over unchanged.

### 2.1 Agencies, teams, roles, access (FR-1xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-101 | Agencies as first-class entities | PS-B2, PS-T1–T4 | E | **A** | 1 | The statement names four agency types and demands multi-agency operation. |
| FR-102 | Teams/units with callsign and roster | PS-K7, PS-B7 | I | **B** | 1 | "Which teams have searched which grid" (PS-B7) and "team positions" (PS-K7) are unimplementable without a team entity. |
| FR-103 | Distinct roles | PS-K6, PS-B2 | I | **B** | 1 | The statement distinguishes field responders (PS-K3) from incident commanders (PS-K6); the role split is inherent. |
| FR-104 | Low-friction enrolment (code/QR) | PS-B11, PS-T3 | I | **B** | 1 | "Minimal training" + volunteer organisations makes account-creation friction a direct failure of PS-B11. |
| FR-105 | Auth works without connectivity at time of use | PS-B10, PS-K4 | I | **C** | 1 | The *requirement* is that field actions work offline (FR-402/PS-K4). Cached device tokens are one mechanism among several. |
| FR-106 | Cross-agency visibility/edit scopes | PS-K11 | I | **B** | 1 (minimal) | A shared picture that any agency can overwrite is not usable by multiple agencies; some ownership rule is required. |
| FR-107 | Agency attribution on all data | PS-B7, PS-K11 | I | **B** | 1 | PS-B7 asks *which teams* searched *which grid* — attribution is the answer to the question, not an extra. |

### 2.2 Incident and grid (FR-2xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-201 | Create incident | PS-B1 | I | **B** | 1 | Everything in the statement is scoped to a disaster event; without an incident entity nothing has a container. |
| FR-202 | Define operational area | PS-K1 | I | **B** | 1 | A grid (PS-K1) must be generated over something. |
| FR-203 | Generate grid with configurable cell size | PS-K1 | E | **A** | 1 | "Grid-based search area allocation" verbatim. |
| FR-204 | Short human-speakable cell IDs | PS-B3, PS-B11 | I | **B** | 1 | Fragmented communication (PS-B3) is partly radio-based; unspeakable IDs make the grid unusable in the field. |
| FR-205 | Immutable/versioned grid labels | PS-B7 | I | **C** | 2 | The *requirement* is that search history stays attributable. Immutability is one mechanism; the prototype can simply forbid regeneration mid-incident. |

### 2.3 Allocation and status tracking (FR-3xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-301 | Assign cells to a team | PS-K1 | E | **A** | 1 | "Search area **allocation**" verbatim. |
| FR-302 | Cell status lifecycle | PS-K2, PS-B7 | E | **A** | 1 | "Real-time **status tracking**" verbatim. |
| FR-303 | Duplicate-assignment prevention/flagging | PS-B4, PS-B13 | E | **A** | 1 | "Prevent duplicated effort" (PS-B13) is one of two stated success outcomes. |
| FR-304 | Surface uncovered cells | PS-B5 | E | **A** | 1 | "Leaving others uncovered" is the second stated failure the platform exists to fix. |
| FR-305 | Attribution + timestamp on status change | PS-B7 | E | **A** | 1 | Directly answers "which teams have searched which grid". |
| FR-307 | Reassign / revoke / re-open a cell | PS-K2 | I | **B** | 1 | Status tracking that cannot be corrected is not operationally usable; also the recovery path for FR-303 collisions. |
| FR-308 | Human conflict queue | PS-K5, PS-B10 | I | **C** | 2 | The requirement is no-loss merging (FR-806). A resolution *UI* is one way to expose residual conflicts; a flag on the cell is sufficient for the prototype. |
| FR-309 | Show current assignment offline on device | PS-K3, PS-K4 | I | **B** | 1 | An allocation the assignee cannot see offline does not deliver PS-K1 under PS-K4 conditions. |

### 2.4 Field mobile application (FR-4xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-401 | Mobile app for field responders | PS-K3 | E | **A** | 1 | "Low-bandwidth mobile app" verbatim. |
| FR-402 | All core field actions work with zero connectivity | PS-K4 | E | **A** | 1 | "Offline-capable data entry" verbatim. |
| FR-403 | Durable local persistence | PS-K4 | I | **C** | 1 | *How* offline entry survives (a local transactional store). The requirement is PS-K4; the store is our mechanism. Level 1 because FR-402 cannot exist without some store. |
| FR-404 | Outbox queue for pending changes | PS-K4, PS-K5 | I | **C** | 1 | Store-and-forward mechanism for PS-K4/K5. Same reasoning as FR-403. |
| FR-405 | Capture GPS position incl. offline | PS-K7 | E | **A** | 1 | "Dashboard aggregating **team positions**" verbatim. |
| FR-407 | Core action in ≤3 taps, no free text | PS-B11, PS-E3 | I | **B** | 1 | The operational reading of "usable by responders with minimal training" and the only testable form of EC-03. |
| FR-408 | Gloves / sunlight / night ergonomics | PS-B10, PS-B11 | I | **B** | 1 (reduced) | "Chaotic disaster site" + "minimal training" imply the physical conditions of use. Reduced form at Level 1: large targets + high contrast. |
| FR-409 | Offline map/basemap for the area | PS-K3, PS-K4 | I | **B/C** | 1 (grid-only) / 2 (tiles) | *Seeing your assigned area offline* is class B. *Pre-cached raster/vector basemap tiles* is class C — a schematic grid satisfies the need at Level 1. |
| FR-410 | Connectivity + data-freshness indicator | PS-B10, PS-E1 | I | **B** | 1 | Under intermittent connectivity, an unlabelled screen misleads the responder; this is what makes PS-K2 honest (PI-03). |
| FR-411 | Runs on low-end Android | PS-T3, PS-K3 | I | **C** | 2 | A constraint on technology choice, not a feature. Level 2 as "avoid heavyweight dependencies", not as an optimisation programme. |

### 2.5 Survivor reports (FR-5xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-501 | File a survivor report | PS-B9, PS-K9 | E | **A** | 1 | "Where survivors have been reported" (PS-B9) and "survivor reports" (PS-K9), both verbatim. |

### 2.6 Resource inventory (FR-6xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-601 | Inventory per team/agency/supply point | PS-K10 | E | **A** | 1 | "Resource inventory tracking" verbatim. |
| FR-602 | Equipment + medical supply categories | PS-K10 | E | **A** | 1 | Both categories named verbatim in the statement. |
| FR-603 | Quantity remaining + consumption | PS-B8, PS-K10 | E | **A** | 1 | "What resources remain" verbatim. |
| FR-606 | Inventory updates offline-capable | PS-K4, PS-K10 | I | **B** | 1 | PS-K4 says "offline-capable data entry" without carve-outs; inventory is data entry. Near-free once FR-402 exists. |

### 2.7 Commander dashboard (FR-7xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-701 | Web dashboard for commanders | PS-K6 | E | **A** | 1 | "Incident commander web dashboard" verbatim. |
| FR-702 | Live operational map with layers | PS-K6–K9 | E | **A** | 1 | The statement enumerates exactly what it aggregates: positions, search status, survivor reports. |
| FR-703 | Aggregate operational metrics | PS-K6, PS-B12 | I | **B** | 1 | "Aggregating" (PS-K6) means more than plotting; coverage % is how "cut search time" becomes visible. |
| FR-704 | Filter/colour by agency, team, status | PS-K11, PS-B2 | I | **B** | 1 (simple) | With several agencies on one map, an unfilterable picture stops being a *shared operational picture* (EC-02). |
| FR-705 | Data age per team/cell | PS-B10, PS-E1, PS-E2 | I | **B** | 1 | Under PS-B10 conditions, undated data is misinformation. This is the honest reading of "real-time" (PI-03). |
| FR-706 | Allocation console | PS-K1, PS-B13 | I | **B** | 1 | PS-K1 allocation must be performed by someone somewhere; the commander (PS-K6) is that someone. |

### 2.8 Sync and transport (FR-8xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-801 | Store-and-forward sync engine | PS-K4, PS-K5 | E | **A** | 1 | The statement requires offline entry *and* later sync; this is that requirement. |
| FR-802 | Delta-based, compact, compressed payloads | PS-K3 | E/C | **A** (low-bandwidth outcome) / **C** (delta + compression) | 1 (deltas) / 2 (compression) | *Low bandwidth* is class A (NFR-01). *Delta encoding and compression* are mechanisms — event-shaped deltas fall out of the design anyway; compression tuning does not. |
| FR-803 | SMS sync channel | PS-K5 | E | **A** | 1 | Named verbatim in PS-K5, and chosen as the prototype's PS-K5 satisfier (D-02). |
| FR-804 | Device-to-device mesh/peer sync | PS-K5 | E | **A** | 2 | Also named verbatim — but PS-K5 says "mesh-network **or** SMS". Delivering one satisfies the clause; the second is prototype enhancement. See §4.3. |
| FR-805 | Automatic transport selection/fallback | PS-K5, PS-B10 | I | **C** | 2 | A convenience mechanism over the transports. With one transport at Level 1 it is nearly vacuous; it becomes meaningful only alongside FR-804. |
| FR-806 | Deterministic no-loss merge policy | PS-K5 | I | **B** | 1 | Sync across partitions without a merge rule silently destroys search results and survivor reports — the exact harms the statement exists to prevent. |
| FR-807 | Idempotent, de-duplicated messages | PS-K5 | I | **C** | 1 | Mechanism (message UUID + dedupe on receipt). Level 1 because SMS retries make duplicates immediately real, and it is cheap. |
| FR-808 | Transmission priority ordering | PS-K3, PS-B10 | I | **C** | 2 | Queue-scheduling mechanism. Level 2 in reduced form (two tiers: life-critical vs routine). |
| FR-809 | Any connected device acts as gateway | PS-K5 | I | **C** | 2 | Topology mechanism, meaningful only once peer sync (FR-804) exists. |
| FR-810 | Per-item sync state exposed | PS-E1, PS-B10 | I | **C** | 2 | The user-facing need is met at Level 1 by the aggregate indicator (FR-410); per-item detail is a diagnostic refinement. |
| FR-812 | Clock-skew tolerance | PS-K5, PS-B7 | I | **C** | 2 | Mechanism for correct ordering. Prototype substitute: record device time, order by server receipt time, and document the limitation. |

### 2.9 Interoperability (FR-9xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-901 | Documented, versioned API | PS-K11 | E | **A** | 1 | "Interoperability layer" is precisely this; without it EC-04 has no evidence. |
| FR-902 | Common information model | PS-K11 | E | **A** | 1 | "A shared operational picture" requires a shared model — this is the contract itself. |
| FR-903 | Agency join flow | PS-K11, PS-B2 | E | **A** | 1 | "Multiple agencies to **join** a shared operational picture" verbatim. |
| FR-905 | GeoJSON/CSV interchange | PS-K11, PS-B3 | I | **B** | 1 (export) / 2 (import) | The fallback path for agencies that cannot integrate live; export is cheap and is direct EC-04 evidence. |
| FR-908 | Machine/system client authentication | PS-K11 | I | **C** | 2 | Mechanism. Level 1 substitute: a static API key on the documented API, with the limitation stated. |

### 2.10 Audit and accountability (FR-10xx)

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| FR-1001 | Append-only event log | PS-B7, PS-K5 | I | **C** | 1 | **Frequently mistaken for a requirement — it is not.** The requirement is PS-B7 (who searched what, when) plus reliable sync. Event-sourcing is our chosen mechanism (TC-03). Level 1 because the sync and merge design depends on it. |
| FR-1002 | Actor/team/agency/device/timestamps on events | PS-B7 | I | **B** | 1 | The content of PS-B7's question. |

### 2.11 Non-functional Musts

| ID | Requirement (short) | Src | Prov | **Class** | **Level** | Justification for class |
|---|---|---|---|---|---|---|
| NFR-01 | Low-bandwidth payload budget | PS-K3, PS-E1 | E | **A** | 1 | "Low-bandwidth mobile app" verbatim; EC-01 is scored on it. Level 1 = **measure and report**, not optimise. |
| NFR-02 | Offline endurance | PS-K4, PS-E1 | E | **A** | 1 | PS-K4 verbatim. Level 1 = no artificial time limit and a demonstrated multi-hour offline session; the 24 h figure remains a proposed target. |
| NFR-03 | Propagation latency when connected | PS-K2 | E | **A** | 1 | "Real-time" (PS-K2), bounded per PI-03. Level 1 = best-effort with measured figures. |
| NFR-04 | Learnability without documentation | PS-B11, PS-E3 | E | **A** | 1 | PS-B11 verbatim; EC-03 is scored on it. Level 1 = an informal test with 2–3 first-time users, numbers reported. |
| NFR-05 | Field ergonomics | PS-B10, PS-E3 | I | **B** | 1 (reduced) | Reduced form: contrast and target size. A full WCAG audit is not prototype work. |
| NFR-07 | Durability of acknowledged writes | PS-K4, PS-E1 | I | **C** | 1 | Property obtained from the transactional local store (FR-403); not a separate build item. |
| NFR-08 | Degraded-mode availability | PS-B10, PS-E1 | I | **B** | 1 | **Restated under D-01:** *loss of the central server must not stop **field** operations.* The dashboard may require the server. |
| NFR-12 | Security | PS-K11 | I | **B** | 2 | Necessary for a real deployment, not for demonstrating the statement. Level 2 reduced: transport encryption + tokens; no at-rest encryption, no hardening programme. |
| NFR-13 | Survivor-data privacy | PS-B9 | I | **B** | 2 | Reduced: role-gated survivor detail, synthetic data only in demos, written retention policy. |
| NFR-14 | Documented consistency model | PS-K5, PS-E2 | I | **C** | 1 | A documentation deliverable describing our chosen mechanism, not a feature. Cheap, and it is what makes EC-01 credible to a technical judge. |
| NFR-15 | Partition tolerance | PS-K5 | I | **B** | 1 (two-device) / 3 (full) | Two devices diverging offline and reuniting is the core EC-01 proof. Multi-cluster split-brain is Level 3. |
| NFR-16 | API versioning / back-compat | PS-K11, PS-E4 | I | **C** | 2 | Mechanism. Level 1 substitute: a version prefix and a written schema; no compatibility guarantees to maintain yet. |

### 2.12 Deferred by D-01 (traceability preserved)

| ID | Requirement | Src | Prov | Original Pri | New status |
|---|---|---|---|---|---|
| FR-711 | Dashboard usable at a forward command post with no internet | PS-B10, PS-K5 | I | S | **Deferred — D-01** → §8 |
| NFR-17 | Server tier runnable on-site (edge box) | PS-B10, PS-K5 | I | S | **Deferred — D-01** → §8 |
| PI-09 | Edge deployment interpretation | — | — | — | **Withdrawn from prototype — D-01** → §8 |
| NFR-08 | Degraded-mode availability | PS-B10, PS-E1 | I | M | **Restated — D-01**: field-side only (see §2.11) |

---

## 3. Classification summary

| Class | Count (of 71 Musts) | Meaning for the submission |
|---|---|---|
| **A — Directly required** | 27 | Quote the problem statement when presenting these. |
| **B — Necessary implied** | 23 | Present with the "required to make X work" justification. |
| **C — Implementation detail** | 21 | Present as engineering choices. **Never** as mandates. |
| **D — Proposed enhancement** | 0 among Musts | Correct — no enhancement had been mis-promoted to Must. |

| Level | Requirement count | Note |
|---|---|---|
| **Level 1** | 48 | The buildable prototype core. |
| **Level 2** | 21 (+ all previously-Should items) | Reduced forms by default. |
| **Level 3** | OF-01…OF-14 + deferrals | Untouched until 1 and 2 are done. |

---

## 4. Validation findings

### 4.1 No enhancement had been smuggled into Must
Zero of the 71 Musts classify as **D**. The Must set is not inflated with wishlist features — the overengineering risk in this project is a different one, described next.

### 4.2 The real risk: 21 implementation details carrying the authority of requirements
Nearly a third of the Must set is class **C** — mechanisms, not obligations. Left unmarked, these distort scope in two ways: they make the build look larger than the statement demands, and in a submission they invite a judge to ask "where does the problem statement say you need an append-only event log?" — a question with no good answer. The most important cases:

| Item | What it actually is | The requirement it serves |
|---|---|---|
| FR-1001 append-only event log | Our chosen storage/sync mechanism (TC-03) | PS-B7 attribution + PS-K5 sync |
| FR-812 clock-skew tolerance | Mechanism for correct ordering | PS-B7 "who searched first" |
| FR-807 idempotency | Mechanism for safe retries | PS-K5 |
| FR-802 delta + compression | Mechanism for low bandwidth | PS-K3 / NFR-01 |
| FR-403 / FR-404 local store + outbox | Mechanism for offline entry | PS-K4 |
| FR-308 conflict-resolution UI | Mechanism for exposing merge conflicts | PS-K5 no-loss merging |
| FR-105 cached auth token | Mechanism for offline authorisation | PS-K4 |
| FR-205 immutable grid labels | Mechanism for stable attribution | PS-B7 |
| NFR-07 durability | Property of the chosen store | PS-K4 |
| NFR-14 consistency model | Documentation of the mechanism | PS-K5 / EC-02 |

§9 gives the language discipline that keeps these honest.

### 4.3 PS-K5 says "or" — and the prototype should take that seriously (D-02)
`01-requirements-analysis.md` recommended building **both** mesh and SMS. On re-reading the clause — *"mesh-network **or** SMS-based sync where cellular data is unavailable"* — the statement itself offers a choice, and delivering one fully satisfies PS-K5.

Recommendation: **SMS at Level 1, mesh/peer at Level 2.** Reasons:
- SMS works at range and over real infrastructure; smartphone mesh reaches tens of metres (PI-01), so SMS is the more honest answer to "cellular data unavailable" across a disaster site.
- SMS is deterministically demonstrable with two handsets; mesh demos are fragile on unfamiliar venue hardware.
- One well-built transport with a correct merge story scores EC-01 better than two half-built ones.

**Trade-off to accept knowingly:** mesh is the more striking demo, and "mesh" is the more evocative word in the statement. If demo impact outweighs engineering risk for you, the alternative is to build **peer sync in reduced form** (single-hop, one device relaying to a nearby device over a local link) at Level 1 alongside SMS — this is the single highest-value Level 2 promotion available. Flagging it as your call.

### 4.4 Effect of D-01
Removing the offline command centre is the largest single scope reduction available, and it costs nothing against the statement: PS-K6 asks for a *web dashboard*, and PS-B10's low-bandwidth conditions describe the **disaster site**, where responders are — not the command post, which realistically has a satellite terminal or vehicle uplink. The prototype's low-connectivity story stays intact because it lives entirely on the field side (FR-402, FR-801, FR-803, FR-806, NFR-02, NFR-15).

### 4.5 What Level 1 deliberately does not include
Multi-hop mesh routing · CRDT-grade merge semantics · compression tuning · clock-skew correction · per-item sync telemetry · conflict-resolution UI · offline basemap tile packs · dark mode · Hindi localisation · security hardening · low-end device optimisation · API version negotiation · any AI. None of these leave a PS clause uncovered (verified in §7).

---

## 5. LEVEL 1 — MUST BUILD

Eleven packages. Every one traces to the statement; none can be dropped without leaving a clause uncovered or the demo unconvincing.

---

### L1-01 · Incident setup and grid generation
- **Requirement IDs:** FR-201, FR-202, FR-203, FR-204 · supports MC-07
- **Provenance:** FR-203 **Explicit**; FR-201, FR-202, FR-204 **Implied**
- **Why Level 1:** PS-K1 ("grid-based search area allocation") is unimplementable without it, and every other feature hangs off the grid.
- **Minimum prototype behaviour:** Create an incident (name, type: landslide / building collapse, location). Draw a rectangle or polygon on a map. Generate a rectangular grid with a configurable cell size (default 100 m landslide / 10 m collapse). Label cells `A1…N` — short and speakable.
- **Not needed yet:** MGRS cross-reference display · multiple disjoint operational areas · sector grouping (FR-206) · vertical/floor subdivision (FR-208) · per-cell terrain and hazard metadata (FR-207) · grid versioning (FR-205) · re-gridding mid-incident (simply disallow it).

### L1-02 · Agencies, teams, roles and joining
- **Requirement IDs:** FR-101, FR-102, FR-103, FR-104, FR-105, FR-106, FR-107 · supports MC-03
- **Provenance:** FR-101 **Explicit**; FR-102, FR-103, FR-104, FR-106, FR-107 **Implied**; FR-105 **Implied (mechanism)**
- **Why Level 1:** Multi-agency operation is the premise of the whole statement (PS-B2, PS-T1–T4), and EC-04 is scored on it. Attribution (FR-107) is the literal answer to PS-B7.
- **Minimum prototype behaviour:** Seed 3–4 agencies of different types (NDRF, fire, police, volunteer). Teams belong to an agency and have a callsign. Three roles only: **field responder**, **incident commander**, **observer**. A responder joins an incident by entering a short code — no email, no password ceremony — and receives a device token cached locally so the app works offline afterwards. Every record stores its authoring responder, team and agency. Visibility rule: everyone reads everything; a team writes only its own assignments, reports and inventory.
- **Not needed yet:** Team-leader and agency-liaison roles · organisation self-registration · SSO/OIDC · password reset · per-agency granular sharing scopes (FR-904) · revocation workflows · roster management beyond a name list.

### L1-03 · Cell allocation, status tracking and duplication prevention
- **Requirement IDs:** FR-301, FR-302, FR-303, FR-304, FR-305, FR-307, FR-309, FR-706
- **Provenance:** FR-301–305 **Explicit**; FR-307, FR-309, FR-706 **Implied**
- **Why Level 1:** This package *is* the problem statement's core. PS-B4 (duplication), PS-B5 (uncovered zones), PS-B7 (who searched what), PS-B13 (prevent duplication) all land here, and it carries EC-02.
- **Minimum prototype behaviour:** Commander assigns a cell (or drag-selects several) to a team. Five statuses: `unassigned → assigned → in progress → searched → needs re-search`. Assigning a cell that another team already holds is **blocked with a clear warning naming the holding team**; when the collision arrives from an offline device, the cell is flagged and both claims are visible. Unsearched cells are visually unmistakable and counted numerically. Every transition records team, responder, agency and timestamp, visible on cell tap. Commander can reassign or re-open. Responders see their assignment on-device with no connectivity.
- **Not needed yet:** Search quality levels — hasty vs thorough (FR-306) · `inaccessible` / `hazard-no-entry` statuses · sector-level block assignment · a dedicated conflict-resolution console (FR-308 — a flag on the cell suffices) · assignment optimisation or suggestions (OF-06).

### L1-04 · Offline-first field application core
- **Requirement IDs:** FR-401, FR-402, FR-403, FR-404, FR-407, FR-408, FR-409 (grid-only), FR-410 · NFR-02, NFR-04, NFR-05 (reduced), NFR-07, NFR-08 (field-side, per D-01)
- **Provenance:** FR-401, FR-402 **Explicit**; FR-407, FR-408, FR-410 **Implied**; FR-403, FR-404 **Implied (mechanism)**
- **Why Level 1:** PS-K3 and PS-K4 verbatim, and this package alone carries EC-01 and EC-03 — the two criteria most easily lost.
- **Minimum prototype behaviour:** Android app. Every core action — view my assignment, change cell status, file a survivor report, adjust inventory — **completes locally and instantly with the device in aircraft mode**, and survives force-kill and reboot. Changes accumulate in a local outbox. The **three life-critical actions are each ≤3 taps** with no typing required (PI-07 three-tap doctrine). Large targets, high contrast. The assigned area renders offline as a schematic grid with no basemap. A persistent header shows connectivity, last-sync time and queued-item count.
- **Not needed yet:** Pre-cached basemap tiles (FR-409 full) · dark mode · Hindi localisation (NFR-06) · manual position fallback (FR-406) · SOS (FR-412) · battery optimisation (NFR-10) · low-end device tuning (NFR-11) · cold-start budget (NFR-20) · iOS · per-item sync state (FR-810).

### L1-05 · Team position reporting
- **Requirement IDs:** FR-405 · supports FR-702
- **Provenance:** **Explicit** (PS-K7)
- **Why Level 1:** "Dashboard aggregating **team positions**" is named in PS-K5's expected solution.
- **Minimum prototype behaviour:** Capture GPS on meaningful events only — cell entry/exit, status change, report filed, or a distance/time threshold (PI-08). Positions log offline and forward on sync. Dashboard shows each team's last known position **with its age**.
- **Not needed yet:** Continuous position streaming · breadcrumb trails · manual position entry (FR-406) · geofence alerts · overdue/check-in detection (FR-710).

### L1-06 · Survivor reporting
- **Requirement IDs:** FR-501 · supports FR-702, NFR-13 (Level 2)
- **Provenance:** **Explicit** (PS-B9, PS-K9)
- **Why Level 1:** PS-B9 names it as one of the three questions a commander cannot currently answer (MC-09).
- **Minimum prototype behaviour:** From a cell, a responder files a report in ≤3 taps: number of persons, status (trapped / accessible / extricated / deceased), optional triage category. Works fully offline. Appears on the dashboard map and in a list, attributed and time-stamped. Survivor reports are **never lost in a merge** — they are additive (see L1-08).
- **Not needed yet:** Photo/voice attachments (FR-502) · hazard and clue reporting (FR-503, FR-504) · medical/extrication requests (FR-505) · duplicate-report merging (FR-506) · full survivor lifecycle to hospital handover (FR-507) · missing-person matching (OF-07).

### L1-07 · Resource inventory
- **Requirement IDs:** FR-601, FR-602, FR-603, FR-606
- **Provenance:** FR-601, FR-602, FR-603 **Explicit**; FR-606 **Implied**
- **Why Level 1:** PS-K10 names it, and PS-B8 ("what resources remain") is the third of the statement's three commander questions (MC-09).
- **Minimum prototype behaviour:** Each team holds a short list of resource items with quantities, in the two categories the statement names (equipment; medical supplies). A responder decrements a quantity offline in two taps. The dashboard shows remaining quantities per team and an incident total.
- **Not needed yet:** Resource requests and fulfilment workflow (FR-604) · transfers between teams (FR-605) · automatic low-stock alerts (FR-607) · supply points as separate entities · barcode/RFID · depot logistics (out of scope, AMB-16) · predictive depletion (OF-05).

### L1-08 · Sync engine, SMS transport and merge policy
- **Requirement IDs:** FR-801, FR-802 (deltas), FR-803, FR-806, FR-807, FR-1001, FR-1002 · NFR-01, NFR-03, NFR-14, NFR-15 (two-device)
- **Provenance:** FR-801, FR-802, FR-803 **Explicit**; FR-806, FR-1002 **Implied**; FR-807, FR-1001 **Implied (mechanism)**
- **Why Level 1:** PS-K5 verbatim, and it is the engineering substance behind EC-01. Nothing else in the build differentiates this project as strongly.
- **Minimum prototype behaviour:** Local write always succeeds; transmission is asynchronous and resumable. Each change is a small self-contained event carrying id, actor, team, agency, device time and server receipt time. **SMS path:** events encode into a compact format and travel between a field handset and a gateway handset; the receiver de-duplicates by event id, so retries and multi-path delivery are safe. **Merge policy, documented in one page:** additive records (survivor reports, search events, position logs) are union-merged and can never be lost; mutable state (cell status, assignment owner, quantity) resolves by a single stated rule, with contradictions flagged on the cell. Measure and publish bytes-per-update.
- **Not needed yet:** Mesh/peer transport (FR-804 — Level 2) · automatic transport fallback (FR-805) · priority queueing (FR-808) · gateway relay topology (FR-809) · per-item sync telemetry (FR-810) · storage eviction policy (FR-811) · clock-skew correction (FR-812 — use server receipt time and state the limitation) · compression tuning · CRDT semantics · multi-cluster split-brain handling.

### L1-09 · Commander dashboard — the shared operational picture
- **Requirement IDs:** FR-701, FR-702, FR-703, FR-704, FR-705
- **Provenance:** FR-701, FR-702 **Explicit**; FR-703, FR-704, FR-705 **Implied**
- **Why Level 1:** PS-K6–K9 verbatim, and EC-02 is scored entirely here. MC-09's three questions must be answerable on one screen.
- **Minimum prototype behaviour:** Web dashboard, **online, server-backed** (per D-01). One map: grid cells coloured by status, team markers, survivor markers. A metrics strip: % searched, cells outstanding, teams active, survivors reported, critical resources. Filter/colour by agency. **Every team marker and cell carries its data age** ("14 min ago") — no undated data anywhere. Assignment is performed here (L1-03).
- **Not needed yet:** Offline dashboard or edge server (**FR-711, NFR-17 — deferred by D-01**) · alert feed (FR-707) · timeline/replay (FR-708) · snapshot export or print (FR-709) · team overdue detection (FR-710) · multi-incident rollup · time-window filtering · after-action reporting (FR-1003).

### L1-10 · Interoperability layer
- **Requirement IDs:** FR-901, FR-902, FR-903, FR-905 (export) · NFR-16 (reduced)
- **Provenance:** FR-901, FR-902, FR-903 **Explicit**; FR-905 **Implied**
- **Why Level 1:** PS-K11 verbatim, and EC-04 is a scored criterion that cannot be evidenced by a shared login screen alone — it needs a real contract and a real second party.
- **Minimum prototype behaviour:** A written **common information model** (incident, area, cell, agency, team, position, search status, survivor report, resource). A documented REST API under a version prefix, authenticated by a static API key, that lets an external system **read the operational picture and contribute to it**. Demonstrate a second and third agency joining a running incident by code and immediately appearing in the shared picture. Export grid status and survivor reports as GeoJSON/CSV.
- **Not needed yet:** Per-agency sharing scopes (FR-904) · terminology mapping (FR-906) · webhooks/subscriptions (FR-907) · per-client credentials and rotation (FR-908) · CAP/EDXL profiles · federation between instances · backward-compatibility guarantees · data import (FR-905 import half).

### L1-11 · Evidence and measurement (demo-critical, non-feature)
- **Requirement IDs:** NFR-01, NFR-03, NFR-04, NFR-14 · serves EC-01…EC-04
- **Provenance:** NFR-01, NFR-03, NFR-04 **Explicit**; NFR-14 **Implied (documentation)**
- **Why Level 1:** Three of the four evaluation criteria are judged on evidence rather than on the presence of a feature. Unmeasured robustness and unmeasured usability score as assertions.
- **Minimum prototype behaviour:** Recorded bytes-per-update for each event type on both transports. Measured propagation latency when connected. An informal usability run with 2–3 first-time users (tap counts, time-to-complete, completion rate) with the numbers written down. A one-page consistency-and-merge note. Four scripted demo scenarios, one per evaluation criterion, each runnable in both live and simulated-network form (AMB-19).
- **Not needed yet:** Formal usability study · load testing to NFR-09 targets · benchmark suites · battery instrumentation.

---

## 6. LEVEL 2 — SHOULD BUILD (reduced forms by default)

Ordered by value against the evaluation criteria. Each is genuinely useful; none is required to cover a PS clause.

### L2-01 · Mesh / peer-to-peer sync — *highest-value item on this list*
- **IDs:** FR-804 (Explicit), FR-805, FR-809 (Implied, mechanism) · **Serves:** EC-01
- **Why here:** PS-K5's "or" is satisfied by SMS (D-02), so this is enhancement in the strict sense — but it is the most vivid EC-01 demonstration available and the closest to the statement's own vocabulary.
- **Reduced form:** single-hop peer sync between two co-located handsets over a local link, with one acting as the relay to the server. **Full form not needed:** multi-hop routing, mesh topology management, automatic peer discovery at scale, LoRa.

### L2-02 · Search quality levels and re-search
- **IDs:** FR-306 (Implied), plus `inaccessible` / `hazard` statuses from FR-302 · **Serves:** EC-02, PS-B12
- **Reduced form:** a two-value marker (hasty / thorough) on the searched status, with a re-search flag the commander can set. **Not needed:** INSARAG marking conformance, per-technique records.

### L2-03 · Hazards, clues and richer field reports
- **IDs:** FR-503, FR-504, FR-505, FR-502 (all Implied) · **Serves:** EC-02
- **Reduced form:** hazard and clue pins with a type and a note, syncing like any other event; photo attachment deferred until a data connection exists. **Not needed:** voice notes, media compression pipelines, attachment sync over SMS.

### L2-04 · Commander alert feed and operational snapshot
- **IDs:** FR-707, FR-709 (Implied) · **Serves:** EC-02, EC-03
- **Reduced form:** a chronological panel of new survivor reports and critical events; snapshot export as a printable page. **Not needed:** alert routing rules, acknowledgement workflows, escalation.

### L2-05 · Resource requests and depletion flags
- **IDs:** FR-604, FR-605, FR-607 (Implied) · **Serves:** EC-02, PS-B8
- **Reduced form:** a request record with three states, and a colour flag under a threshold. **Not needed:** fulfilment workflow, transfer approvals, forecasting.

### L2-06 · Sync robustness refinements
- **IDs:** FR-805, FR-808, FR-810, FR-812, FR-811, FR-802 (compression) — all **Implied, class C** · **Serves:** EC-01
- **Reduced form:** two-tier priority (life-critical before routine); per-item queued/sent/acked badge; ordering by server receipt time with device time retained. **Not needed:** hybrid logical clocks, adaptive transport heuristics, storage eviction policy.

### L2-07 · Conflict presentation
- **IDs:** FR-308 (Implied, class C) · **Serves:** EC-01, EC-02
- **Reduced form:** a filtered list of flagged cells with both claims shown and a one-click "keep this one". **Not needed:** a full merge-resolution workbench, field-level diffing.

### L2-08 · Field app polish for real conditions
- **IDs:** FR-406, FR-412, FR-409 (tiles), FR-411, NFR-06, NFR-10, NFR-11, NFR-20 — Implied · **Serves:** EC-03
- **Reduced form:** dark mode; SOS button; Hindi strings; one pre-cached basemap tile pack for the demo area. **Not needed:** full localisation programme, battery instrumentation, device-matrix testing, iOS.

### L2-09 · Interoperability depth
- **IDs:** FR-904, FR-906, FR-907, FR-908, FR-905 (import), NFR-16 — Implied · **Serves:** EC-04
- **Reduced form:** per-agency read/write scope flags; a small resource-type alias table; one webhook; GeoJSON/CSV import. **Not needed:** CAP/EDXL conformance, federation between instances, credential rotation, negotiated API versions.

### L2-10 · Accountability, safety and after-action
- **IDs:** FR-710, FR-1003, FR-1004, NFR-18, NFR-19 — Implied · **Serves:** EC-02, PS-B12/B13
- **Reduced form:** team check-in with an overdue highlight; an end-of-incident summary (coverage %, timeline, survivors, resources consumed) — this is the slide that quantifies the statement's two success outcomes. **Not needed:** replay debugger, observability stack.

### L2-11 · Security and privacy for a credible deployment story
- **IDs:** NFR-12, NFR-13 — Implied · **Serves:** deployability, not a scored criterion
- **Reduced form:** HTTPS, tokens with expiry, role-gated survivor detail, synthetic data in all demos, a written retention paragraph. **Not needed:** at-rest encryption, threat modelling, penetration testing, audit certification.

### L2-12 · Grid and incident refinements
- **IDs:** FR-205, FR-206, FR-207, FR-208 — Implied · **Serves:** EC-02, MC-02
- **Reduced form:** sector grouping for block assignment; a floor field on cells for collapse incidents; per-cell priority. **Not needed:** grid versioning, terrain modelling, 3-D structure representation.

---

## 7. LEVEL 3 — OPTIONAL / ADVANCED

All **Proposed** provenance. Nothing here is needed to cover any PS clause; none should start before Levels 1 and 2 are demonstrable.

| IDs | Item | Note |
|---|---|---|
| OF-01, TC-13 | Rule-based search prioritisation ("the AI") | The one Level 3 item with a strategic argument for early promotion — it answers AMB-01 and justifies the product name. Start rule-based and transparent; never claim an ML capability the prototype cannot show. |
| OF-13 | After-action analytics beyond L2-10 | Quantifies PS-B12/B13 — the strongest closing evidence if time allows. |
| OF-06 | Assignment suggestion/optimisation | Suggest only; commanders keep control. |
| OF-02, OF-08 | Voice-driven reporting; auto-translation | Strong EC-03/EC-04 stories, heavy build. |
| OF-03, OF-04 | Photo damage assessment; drone/satellite ingest | Bandwidth-hostile; contradicts the low-bandwidth premise unless gated on connectivity. |
| OF-05, OF-14 | Predictive depletion; integrity heuristics | Natural once L2-05 and the event log exist. |
| OF-07, OF-11 | Missing-person matching; public/family portal | Significant privacy obligations (NFR-13); reputational risk. |
| OF-09 | LoRa / radio bridge | Hardware — must remain optional under MC-01. |
| OF-10, OF-12 | Responder biometrics; NDMA/SDMA integration | Require external cooperation. |
| NFR-15 (full) | Multi-cluster split-brain handling | Two-device partition/reunite at Level 1 is sufficient proof. |
| NFR-09 | Load testing to scale targets | Design for the targets; do not test to them in the prototype. |
| — | iOS field app, multi-incident rollup, full EDXL conformance, CRDT merge semantics | Named here so their absence is a decision, not an oversight. |

---

## 8. Future production extensions (documented, explicitly out of prototype scope)

Recorded per **D-01** so the design does not foreclose them and the submission can show a credible production path.

| ID | Extension | Original IDs | Rationale for production, and why not now |
|---|---|---|---|
| **FE-01** | **Offline command centre / on-site edge server** — a single-node deployment at the forward command post hosting the dashboard, acting as the SMS/mesh gateway and syncing upward when a link exists. | FR-711, NFR-17, PI-09, TC-12 | In a real deployment a command post can lose connectivity with the outside world, and coordination must continue. Excluded from the prototype because it roughly doubles deployment complexity while the statement's low-bandwidth premise (PS-B10) describes the **disaster site**, where the responders are — and the field-side offline story (L1-04, L1-08) is what EC-01 actually scores. |
| **FE-02** | Federated multi-instance operation between agencies running their own servers. | PI-05 option B | Real inter-agency politics favour federation; the prototype demonstrates the same contract through the public API instead. |
| **FE-03** | Standards conformance (CAP / EDXL profiles) for authority-level exchange. | FR-905, TC-10 | Needed for institutional adoption; a documented subset at Level 2 is sufficient evidence of intent. |
| **FE-04** | LoRa or radio-bridge mesh for site-wide range beyond smartphone radios. | OF-09 | Removes the tens-of-metres limitation of PI-01; introduces hardware, in tension with MC-01. |
| **FE-05** | Multi-incident, state-level rollup for disaster management authorities. | AMB-11, PS-T4 | PS-T4 names authorities as beneficiaries; the incident entity is modelled from day one so this stays open. |

---

## 9. Traceability integrity check

**Rule 2 verification — every PS clause retains Level 1 coverage:**

| PS clause | Level 1 coverage | PS clause | Level 1 coverage |
|---|---|---|---|
| PS-H2 | L1-01 | PS-B13 | L1-03 |
| PS-H3 | L1-08 (stock-hardware transports; MC-01 intact) | PS-K1 | L1-01, L1-03 |
| PS-B1 | L1-01 | PS-K2 | L1-03, L1-08 |
| PS-B2 | L1-02, L1-09, L1-10 | PS-K3 | L1-04, L1-08 (NFR-01) |
| PS-B3 | L1-01 (speakable IDs), L1-10 (export) | PS-K4 | L1-04 |
| PS-B4 | L1-03 | PS-K5 | L1-08 (SMS — satisfies the clause's "or") |
| PS-B5 | L1-03, L1-09 | PS-K6 | L1-09 |
| PS-B6 | L1-09, L1-10 | PS-K7 | L1-05, L1-09 |
| PS-B7 | L1-03, L1-08 (FR-1002), L1-09 | PS-K8 | L1-03, L1-09 |
| PS-B8 | L1-07, L1-09 | PS-K9 | L1-06, L1-09 |
| PS-B9 | L1-06, L1-09 | PS-K10 | L1-07 |
| PS-B10 | L1-04, L1-08 | PS-K11 | L1-02, L1-10 |
| PS-B11 | L1-02, L1-04 | PS-T1–T4 | L1-02 |
| PS-B12 | L1-03, L1-09 (metrics) | PS-E1–E4 | L1-11 (evidence per criterion) |

**Result:** all PS clauses retain Level 1 coverage. The sole exception remains **PS-H1** — the "AI" in the title, which the statement body never substantiates (AMB-01); it is answered at Level 3 by OF-01.

**Rule 5 verification — nothing deleted:** FR-711, NFR-17 and PI-09 retain their IDs, sources and provenance in §2.12 and §8. NFR-08 is restated, not removed. No requirement from `01-requirements-analysis.md` has been dropped from the register.

---

## 10. Language discipline (how these must be described)

The point of the A/B/C/D classification is to survive a judge, a reviewer or a teammate asking *"who says you need that?"*

| Say this | Not this |
|---|---|
| "Grid-based allocation, **required by the problem statement**." (A) | — |
| "Attribution on every status change — **this is what answers 'which teams have searched which grid'**." (B) | "The problem statement requires an audit trail." |
| "We use an **append-only event log** as our mechanism for attribution and reliable sync." (C) | "An append-only event log is a mandatory requirement." |
| "Offline entry is required (PS-K4); a **local transactional store with an outbox** is how we implement it." (C) | "The statement requires a local database and outbox pattern." |
| "PS-K5 asks for mesh **or** SMS; we deliver SMS fully, and peer sync as an enhancement." | "We only did half of the sync requirement." |
| "Cell prioritisation is an **enhancement beyond the stated scope**." (D) | "The AI features are core requirements." |

Two standing cautions:
1. **Never present a mechanism as a mandate.** Twenty-one Level-1 and Level-2 items are mechanisms (§4.2). Each has a defensible *why*, but the why traces to a PS clause, not to the mechanism itself.
2. **Never present a reduced form as a full one.** If peer sync is single-hop, say single-hop. If the SMS demo is simulated, say simulated. The evaluation criteria reward robustness that is real; an overclaim that a judge catches costs more than the feature was worth.

---

## 11. Decisions requested with this document

| # | Decision | Default if you do not object |
|---|---|---|
| 1 | **D-02** — SMS at Level 1, mesh/peer at Level 2 (§4.3). | Proceed as stated. |
| 2 | Whether to **promote reduced peer sync (L2-01) into Level 1** for demo impact, accepting the engineering risk. | Leave at Level 2. |
| 3 | Whether to **promote rule-based cell prioritisation (OF-01) into Level 2** to justify the "AI" in the product name (AMB-01). | Leave at Level 3; revisit once Level 1 is verified. |
| 4 | Confirm the Level 1 package list (§5) is the buildable scope — 11 packages, 48 requirements. | Proceed as stated. |

On approval, the next deliverable is **feasibility and architecture** for the Level 1 scope only, followed by the tracked requirements register and the four demo scenario scripts (EC-01…EC-04).
