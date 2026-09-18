# RescueNet AI — Requirements Analysis (v1.0, for approval)

**Status:** Draft for approval · **Date:** 2026-08-22 · **Stage:** Requirements only (no architecture, no code)
**Primary source of truth:** the official problem statement (PS) as supplied. Anything not traceable to the PS is explicitly tagged.

---

## 0. Method & notation

### 0.1 Provenance tags (applied to every requirement)

| Tag | Meaning |
|---|---|
| **E** | **Explicit** — stated verbatim or near-verbatim in the problem statement. |
| **I** | **Implied** — not stated, but the explicit requirement cannot be fulfilled without it. Justification given. |
| **P** | **Proposed** — beyond the problem statement. An enhancement or a technical choice. Never to be presented as an official requirement. |

### 0.2 Priority

| Code | Meaning |
|---|---|
| **M** | Must — failure to deliver is failure against the PS. |
| **S** | Should — required for a credible, coherent solution; derived from an M. |
| **C** | Could — enhancement; deliver only after all M and S are complete. |

### 0.3 Verification method

`D` = Demonstration (scripted live scenario) · `T` = Automated/manual test · `I` = Inspection (code/doc/schema review) · `A` = Analysis (measurement, calculation, load model)

### 0.4 ID namespaces

| Prefix | Meaning |
|---|---|
| `PS-*` | Atomic clause extracted from the problem statement (the traceability anchors) |
| `FR-*` | Functional requirement |
| `NFR-*` | Non-functional requirement |
| `EC-*` | Evaluation criterion |
| `MC-*` | Mandatory constraint |
| `TC-*` | Proposed technical choice (P by definition) |
| `OF-*` | Optional / advanced feature (P by definition) |
| `AMB-*` | Ambiguity requiring a decision |
| `PI-*` | Prototype interpretation option set for a difficult requirement |

---

## 1. Source decomposition — atomic clauses of the problem statement

Every requirement below traces to one or more of these. This is the authoritative decomposition.

### 1.1 Header

| ID | Clause |
|---|---|
| PS-H1 | Problem title: RescueNet **AI** — Multi-Agency Coordination Platform for Search-and-Rescue Operations |
| PS-H2 | Theme/domain: Disaster Management |
| PS-H3 | Category: **Software** |

### 1.2 Background & problem framing

| ID | Clause |
|---|---|
| PS-B1 | Context is large-scale disasters such as **landslides** or **building collapses** |
| PS-B2 | **Multiple agencies** participate: NDRF, local police, fire services, volunteer groups |
| PS-B3 | These agencies operate with **fragmented communication** |
| PS-B4 | Consequence A: **duplicated search effort** in some zones |
| PS-B5 | Consequence B: **zones left uncovered** |
| PS-B6 | There is **no shared real-time operational picture** |
| PS-B7 | Commanders cannot see **which teams have searched which grid** |
| PS-B8 | Commanders cannot see **what resources remain** |
| PS-B9 | Commanders cannot see **where survivors have been reported** |
| PS-B10 | The platform must be designed for **chaotic, low-bandwidth conditions** of a disaster site |
| PS-B11 | The platform must be **usable by responders with minimal training** |
| PS-B12 | Success outcome: **cut search time** |
| PS-B13 | Success outcome: **prevent duplicated effort** |

### 1.3 Key technical requirements (expected solution)

| ID | Clause |
|---|---|
| PS-K1 | **Grid-based search area allocation** |
| PS-K2 | **Real-time status tracking** |
| PS-K3 | Accessible via **low-bandwidth mobile app** |
| PS-K4 | **Offline-capable data entry** |
| PS-K5 | **Mesh-network or SMS-based sync** where cellular data is unavailable |
| PS-K6 | **Incident commander web dashboard** |
| PS-K7 | Dashboard aggregates **team positions** |
| PS-K8 | Dashboard aggregates **search status** |
| PS-K9 | Dashboard aggregates **survivor reports** |
| PS-K10 | **Resource inventory tracking** (equipment, medical supplies) |
| PS-K11 | **Interoperability layer** for multiple agencies to join a **shared operational picture** |

### 1.4 Beneficiaries

| ID | Clause |
|---|---|
| PS-T1 | NDRF and SDRF teams |
| PS-T2 | Fire and police services |
| PS-T3 | Volunteer rescue organizations |
| PS-T4 | Disaster management authorities |

### 1.5 Evaluation criteria

| ID | Clause |
|---|---|
| PS-E1 | Robustness under **low-connectivity** conditions |
| PS-E2 | **Clarity of the shared operational picture** |
| PS-E3 | **Ease of use under high-stress field conditions** |
| PS-E4 | **Interoperability across agencies** |

---

## 2. Functional requirements

### FR-1xx — Agencies, teams, roles, access

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-101 | Represent **agencies** as first-class entities of distinct types (national force, state force, police, fire, volunteer organisation, authority). | PS-B2, PS-T1–T4 | E | M | I,D |
| FR-102 | Represent **teams/units** belonging to an agency, with a callsign, member roster and current operational state. | PS-K7, PS-B7 | I | M | D |
| FR-103 | Support distinct **roles**: field responder, team leader, incident commander, agency liaison, read-only observer. | PS-K6, PS-B2 | I | M | D |
| FR-104 | Permit **low-friction enrolment** of a team/responder into an incident (e.g. incident code or QR), without lengthy account creation, so untrained volunteers can join. | PS-B11, PS-T3 | I | M | D |
| FR-105 | Authenticate and authorise **without requiring connectivity at the moment of use** (credential/token cached on device after enrolment). | PS-B10, PS-K4 | I | M | T,D |
| FR-106 | Enforce **visibility and edit scopes** across agencies: all agencies see the shared picture; an agency edits only its own teams, assignments and inventory unless granted otherwise. | PS-K11 | I | M | T |
| FR-107 | Record which agency **authored** every piece of operational data (attribution is required for a multi-agency picture). | PS-B7, PS-K11 | I | M | T |

### FR-2xx — Incident definition and grid

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-201 | Create an **incident** with name, disaster type (landslide, building collapse, other), location, start time and status. | PS-B1 | I | M | D |
| FR-202 | Define the **operational area** of an incident geospatially (drawn polygon or bounding box), possibly multiple disjoint areas. | PS-K1 | I | M | D |
| FR-203 | **Generate a grid** of cells over the operational area with a configurable cell size appropriate to the disaster type (fine for a collapsed structure, coarse for a hillside). | PS-K1 | E | M | D,T |
| FR-204 | Give every cell a **short, human-speakable, unique identifier** (e.g. `B-14`) usable over radio and readable at a glance. | PS-B3, PS-B11 | I | M | I,D |
| FR-205 | Cell identifiers and geometry are **immutable once the grid is published** for an incident; grid changes are versioned, never silently re-labelled. | PS-B7 | I | M | T |
| FR-206 | Support **grouping cells into sectors/zones** assignable as a block to an agency. | PS-K1, PS-B2 | I | S | D |
| FR-207 | Hold per-cell **operational metadata**: priority, terrain/structure type, known hazards, access notes. | PS-B1, PS-K1 | I | S | D |
| FR-208 | Support **vertical subdivision** for building collapses (floor/level within a cell). | PS-B1 | I | S | D |

### FR-3xx — Search allocation and status tracking (the anti-duplication core)

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-301 | **Assign** one or more cells/sectors to a specific team. | PS-K1 | E | M | D |
| FR-302 | Maintain an explicit **cell status lifecycle**: `unassigned → assigned → in-progress → searched → cleared`, plus `needs re-search`, `inaccessible`, `hazard/no-entry`. | PS-K2, PS-B7 | E | M | T,D |
| FR-303 | **Detect and prevent (or explicitly flag) duplicate assignment** of the same cell to more than one team, including when the collision is created offline by two commanders. | PS-B4, PS-B13 | E | M | T,D |
| FR-304 | **Surface uncovered cells**: any cell never assigned or never searched must be visually and numerically distinguishable at all times. | PS-B5 | E | M | D |
| FR-305 | Record, for every status change: **which team, which responder, which agency, at what time**. | PS-B7 | E | M | T |
| FR-306 | Record a **search quality/type** marker (e.g. hasty/primary vs. thorough/secondary search) so commanders can decide whether a cell needs re-searching. | PS-B7, PS-B12 | I | S | D |
| FR-307 | Allow a commander to **reassign, revoke or re-open** a cell (e.g. after a structural shift or a new lead). | PS-K2 | I | M | D |
| FR-308 | Provide a **conflict queue** where contradictory offline updates to the same cell are presented for human resolution rather than silently discarded. | PS-K5, PS-B10 | I | M | T,D |
| FR-309 | Show a field responder their **current assignment** and its boundaries on-device, offline. | PS-K3, PS-K4 | I | M | D |

### FR-4xx — Field mobile application (low-bandwidth, offline-first)

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-401 | Provide a **mobile application** for field responders. | PS-K3 | E | M | D |
| FR-402 | **All core field actions work with zero connectivity**: view assignment, update cell status, file a survivor report, log a hazard, update inventory. | PS-K4 | E | M | T,D |
| FR-403 | **Persist all data locally** and durably; nothing is lost on app kill, crash, battery death or reboot. | PS-K4 | I | M | T |
| FR-404 | **Queue outbound changes** locally and transmit when any transport becomes available. | PS-K4, PS-K5 | I | M | T |
| FR-405 | Capture **team position** from GPS, including while offline (logged and forwarded later). | PS-K7 | E | M | T,D |
| FR-406 | Provide **manual position entry / cell-based position fallback** when GPS is unavailable (indoors, rubble, canopy). | PS-K7, PS-B10 | I | S | D |
| FR-407 | Every core action reachable in **≤3 taps** from app launch, with no free-text required. | PS-B11, PS-E3 | I | M | I,D |
| FR-408 | UI usable with **gloves, one hand, in sunlight and at night**: large targets, high contrast, colour-plus-shape encoding, dark mode. | PS-B10, PS-B11 | I | M | I,D |
| FR-409 | **Pre-cache offline map/basemap data** for the operational area, with a usable grid-only view when no basemap exists. | PS-K3, PS-K4 | I | M | D |
| FR-410 | Display, on every screen, an unambiguous **connectivity and data-freshness indicator** ("last synced 14 min ago", "3 updates queued"). | PS-B10, PS-E1 | I | M | D |
| FR-411 | Operate on **low-end Android handsets** typical of volunteer responders. | PS-T3, PS-K3 | I | M | T |
| FR-412 | Provide an explicit **SOS / responder-in-distress** signal with highest transmission priority. | PS-B10 | I | S | D |

### FR-5xx — Survivor reports and field findings

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-501 | File a **survivor report**: location (cell + coordinates), number of persons, status (trapped / accessible / extricated / deceased), triage category. | PS-B9, PS-K9 | E | M | D |
| FR-502 | Attach optional **photo or voice note**, degrading gracefully: the textual report syncs first and independently of the media. | PS-B10, PS-K9 | I | S | T,D |
| FR-503 | Report **hazards and obstacles** (gas, unstable structure, blocked route) visible to all agencies. | PS-B1, PS-B10 | I | S | D |
| FR-504 | Record **clues / signs of life** distinct from confirmed survivors (tapping, voice, canine alert). | PS-B9 | I | S | D |
| FR-505 | Raise a **medical / extrication assistance request** linked to a survivor record. | PS-K10, PS-B9 | I | S | D |
| FR-506 | **Detect probable duplicate survivor reports** (same location/time window from different teams) and present them for merge rather than auto-deleting. | PS-B4, PS-K11 | I | S | T |
| FR-507 | Maintain a **survivor record lifecycle**: reported → confirmed → extrication in progress → rescued → handed to medical. | PS-K9 | I | S | D |

### FR-6xx — Resource inventory

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-601 | Maintain an **inventory of resources** held by each team/agency/supply point. | PS-K10 | E | M | D |
| FR-602 | Support at minimum the categories **equipment** (cutters, lifting gear, search cameras, canines) and **medical supplies/consumables**. | PS-K10 | E | M | I |
| FR-603 | Track **quantity remaining** and record consumption in the field. | PS-B8, PS-K10 | E | M | D |
| FR-604 | Submit **resource requests** to the incident commander, and track request state. | PS-B8 | I | S | D |
| FR-605 | Record **transfer / allocation** of resources between teams or agencies. | PS-K10, PS-K11 | I | S | D |
| FR-606 | Inventory updates are **offline-capable** and sync like all other data. | PS-K4, PS-K10 | I | M | T |
| FR-607 | Flag **critical/depleted stock** to the commander automatically. | PS-B8 | I | S | D |

### FR-7xx — Incident commander web dashboard (the shared operational picture)

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-701 | Provide a **web dashboard** for incident commanders. | PS-K6 | E | M | D |
| FR-702 | Display a **live operational map** layering: grid cell status, team positions, survivor reports, hazards, resource points. | PS-K6–K9 | E | M | D |
| FR-703 | Show **aggregate operational metrics**: % of area searched, cells outstanding, cells needing re-search, teams active per agency, survivors reported/rescued, critical resources. | PS-K6, PS-B12 | I | M | D |
| FR-704 | **Filter and colour the picture by agency**, team, cell status and time window. | PS-K11, PS-B2 | I | M | D |
| FR-705 | Show **data age per team/cell** ("last heard from") so a commander never mistakes stale data for current truth. | PS-B10, PS-E1, PS-E2 | I | M | D |
| FR-706 | Provide an **allocation console** to assign/reassign cells and resolve the conflict queue (FR-308). | PS-K1, PS-B13 | I | M | D |
| FR-707 | Provide a **prioritised alert feed**: new survivor report, SOS, resource critical, cell overdue, team overdue. | PS-K9, PS-B12 | I | S | D |
| FR-708 | Provide a **timeline/replay** of search progress over the incident. | PS-B7, PS-B12 | I | S | D |
| FR-709 | **Export or print an operational snapshot** for shift handover and inter-agency briefings. | PS-B3, PS-K11 | I | S | D |
| FR-710 | Support **team check-in / overdue detection** for responder accountability. | PS-K7, PS-B10 | I | S | D |
| FR-711 | The dashboard must remain usable at a **forward command post with no internet**, against a local server/gateway. | PS-B10, PS-K5 | I | S | D |

### FR-8xx — Synchronisation and transport (low-connectivity core)

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-801 | Implement a **store-and-forward sync engine**: local write always succeeds, transmission is asynchronous, interrupted transfers resume. | PS-K4, PS-K5 | E | M | T |
| FR-802 | Sync payloads are **delta-based and compact** — send changes, never full state — and compressed. | PS-K3 | E | M | A,T |
| FR-803 | Provide an **SMS-based sync channel** encoding operational updates into a small number of SMS segments. | PS-K5 | E | M | D,T |
| FR-804 | Provide a **device-to-device mesh/peer sync** channel so co-located responders exchange updates with no infrastructure. | PS-K5 | E | M | D,T |
| FR-805 | **Automatically select and fall back** across transports: data → mesh/peer → SMS, transparently to the responder. | PS-K5, PS-B10 | I | M | T,D |
| FR-806 | Apply a **deterministic, documented conflict-resolution policy**; no acknowledged survivor report or search result may ever be lost by a merge. | PS-K5 | I | M | T |
| FR-807 | All sync messages are **idempotent and de-duplicated** on receipt (retries and multi-path delivery must not create duplicates). | PS-K5 | I | M | T |
| FR-808 | Apply a **transmission priority order**: SOS > survivor report > cell status > inventory > position telemetry, so scarce bandwidth carries life-critical data first. | PS-K3, PS-B10 | I | M | T,A |
| FR-809 | Allow any connected device to act as a **gateway**, relaying an offline cluster's data to the server and back. | PS-K5 | I | M | D |
| FR-810 | Expose **per-item sync state** (queued / in flight / acknowledged) to the user and to support diagnostics. | PS-E1, PS-B10 | I | M | D |
| FR-811 | Enforce **bounded local storage** with a documented retention/eviction policy that never evicts unsynced operational data. | PS-K4 | I | S | T |
| FR-812 | Tolerate and correct for **device clock skew** so ordering and "who searched first" remain sound without a network time source. | PS-K5, PS-B7 | I | M | T |

### FR-9xx — Interoperability layer

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-901 | Publish a **documented, versioned API** through which an external agency system can read and contribute to the shared operational picture. | PS-K11 | E | M | I,D |
| FR-902 | Define a **common information model** (incident, area, grid cell, agency, team, position, search status, survivor report, resource) as the shared contract. | PS-K11 | E | M | I |
| FR-903 | Support an **agency join flow**: a new agency onboards mid-incident with its own teams and immediately sees and contributes to the shared picture. | PS-K11, PS-B2 | E | M | D |
| FR-904 | Provide **per-agency sharing scopes** — what an agency publishes and what it consumes — so participation does not require surrendering all internal data. | PS-K11 | I | S | T |
| FR-905 | Support **import/export in neutral interchange formats** (GeoJSON/CSV at minimum) for agencies that cannot integrate live. | PS-K11, PS-B3 | I | M | D |
| FR-906 | Provide **terminology/type mapping** between agencies (resource types, role names, status vocabularies) so each agency keeps its own language over a shared model. | PS-K11, PS-B2 | I | S | I,D |
| FR-907 | Support **push notification/subscription (webhook or equivalent)** to partner systems for near-real-time propagation. | PS-K2, PS-K11 | I | S | D |
| FR-908 | Authenticate **machine/system clients** separately from human users. | PS-K11 | I | M | T |

### FR-10xx — Audit, accountability, after-action

| ID | Requirement | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|
| FR-1001 | Maintain an **append-only event log** of every operational action (the substrate for both sync and accountability). | PS-B7, PS-K5 | I | M | I,T |
| FR-1002 | Every event carries **actor, team, agency, device, timestamps (device and server)**. | PS-B7 | I | M | T |
| FR-1003 | Generate an **after-action report** for an incident (coverage achieved, timeline, resources consumed, survivors located). | PS-B12, PS-B13 | I | S | D |
| FR-1004 | Support **replay of the event log** for debugging and for demonstrating correctness of offline merges. | PS-K5 | I | S | T |

---

## 3. Non-functional requirements

| ID | Requirement | Target (proposed where marked) | Src | Tag | Pri | Ver |
|---|---|---|---|---|---|---|
| NFR-01 | **Low-bandwidth operation** — a typical operational update must fit a tiny payload budget. | ≤ 512 bytes/update over data; ≤ 2 SMS segments (≤ 280 bytes) for a cell-status or survivor update *(target proposed)* | PS-K3, PS-E1 | E | M | A,T |
| NFR-02 | **Offline endurance** — full field functionality with no connectivity of any kind. | ≥ 24 h continuous *(target proposed)* | PS-K4, PS-E1 | E | M | T |
| NFR-03 | **Propagation latency when connected** — "real-time" bound for the shared picture. | ≤ 5 s device→dashboard on data; ≤ 2 min via SMS path *(target proposed)* | PS-K2 | E | M | A,T |
| NFR-04 | **Learnability under stress** — an untrained responder completes core tasks without documentation. | ≥ 90% task completion after ≤ 10 min orientation, no manual *(target proposed)* | PS-B11, PS-E3 | E | M | T,D |
| NFR-05 | **Field ergonomics** — sunlight-readable contrast, glove-sized targets, night mode, no reliance on colour alone. | ≥ 48 dp targets; WCAG AA contrast *(target proposed)* | PS-B10, PS-E3 | I | M | I |
| NFR-06 | **Language support** — usable by local police, fire and volunteers, not only English speakers. | English + Hindi minimum; string-externalised for regional languages *(scope proposed — see AMB-15)* | PS-T2, PS-T3, PS-B11 | I | S | I |
| NFR-07 | **Durability** — no acknowledged data loss under power failure, crash or transport failure. | Zero loss of acknowledged writes | PS-K4, PS-E1 | I | M | T |
| NFR-08 | **Degraded-mode availability** — loss of the central server must not stop field operations or local coordination. | Field app fully functional; mesh coordination continues | PS-B10, PS-E1 | I | M | T,D |
| NFR-09 | **Scale** — concurrent participants in one incident. | ≥ 20 teams / 200 responders / 5,000 grid cells / 5 agencies *(target proposed — see AMB-05)* | PS-B2, PS-K1 | I | S | A,T |
| NFR-10 | **Battery economy** — survives a full operational shift on a mid-range handset. | ≥ 8 h of active use *(target proposed)* | PS-B10, PS-K3 | I | S | A,T |
| NFR-11 | **Device footprint** — installable and runnable on low-end hardware, over a weak link. | Android 8+, 2 GB RAM; small install size *(target proposed)* | PS-T3, PS-K3 | I | S | T |
| NFR-12 | **Security** — authenticated access, encryption in transit and at rest, without obstructing emergency use (no security control may block a life-critical action offline). | — | PS-K11 | I | M | I,T |
| NFR-13 | **Privacy of survivor and casualty data** — access-controlled, minimised, with a retention policy. | — | PS-B9 | I | M | I |
| NFR-14 | **Consistency model** — eventual consistency with causal ordering; the model and its guarantees are documented and visible to users as data-age. | — | PS-K5, PS-E2 | I | M | I,T |
| NFR-15 | **Partition tolerance** — correct behaviour under network splits, including two isolated clusters that later reunite. | Deterministic merge; no split-brain data loss | PS-K5 | I | M | T |
| NFR-16 | **Interoperability conformance** — the shared model and API are versioned, documented and backward-compatible within a major version. | — | PS-K11, PS-E4 | I | M | I |
| NFR-17 | **Deployability at the edge** — the server tier must be runnable on-site (laptop/edge box at the command post), not only in a cloud. | — | PS-B10, PS-K5 | I | S | D |
| NFR-18 | **Observability** — sync queues, transport selection and merge decisions are inspectable for field support. | — | PS-E1 | I | S | I |
| NFR-19 | **Auditability** — operational history is reconstructable and attributable after the fact. | — | PS-B7 | I | S | I,T |
| NFR-20 | **Cold-start speed** — app launch to actionable screen is fast on low-end devices. | ≤ 3 s *(target proposed)* | PS-E3, PS-B11 | I | S | T |

---

## 4. Evaluation criteria (judging axes) and how each is evidenced

| ID | Criterion (PS) | Requirements that carry it | How it will be evidenced |
|---|---|---|---|
| **EC-01** | Robustness under low-connectivity conditions (PS-E1) | FR-402, FR-404, FR-801–812, NFR-01, NFR-02, NFR-07, NFR-08, NFR-15 | Live scenario: aircraft-mode field devices continue full operation; updates propagate by mesh, then by SMS; server killed mid-demo and field work continues; two partitioned clusters reunited with deterministic merge; measured payload sizes shown against NFR-01. |
| **EC-02** | Clarity of the shared operational picture (PS-E2) | FR-702–FR-709, FR-304, FR-305, FR-705, NFR-14 | Commander answers, within seconds and unaided, three questions: *which cells are unsearched?*, *who searched cell B-14 and when?*, *where are survivors and how stale is that?* Stale data is visibly marked, never silently rendered as current. |
| **EC-03** | Ease of use under high-stress field conditions (PS-E3) | FR-104, FR-407, FR-408, FR-410, FR-412, NFR-04, NFR-05, NFR-20 | Timed task test with a first-time user, no instructions: mark a cell searched and file a survivor report in ≤3 taps each; tap-count and time-to-complete recorded; glove/sunlight/night modes shown. |
| **EC-04** | Interoperability across agencies (PS-E4) | FR-101, FR-106, FR-107, FR-901–908, FR-905, FR-906 | Live scenario: a second and third agency join a running incident by code, publish and consume data under distinct scopes; an external "legacy agency system" contributes via the documented API and via a GeoJSON/CSV import; the model and API docs are shown. |

**Rule:** every demo minute must be spent on EC-01…EC-04. Any feature that does not advance one of these is a candidate for cutting.

---

## 5. Mandatory constraints

| ID | Constraint | Src | Tag | Implication |
|---|---|---|---|---|
| MC-01 | The deliverable is **software** (category is Software). | PS-H3 | E | No custom hardware may be a *prerequisite*. Mesh must be achievable with stock smartphone radios; any LoRa/radio hardware is strictly optional (see AMB-07). |
| MC-02 | The domain is **disaster management / search-and-rescue**, specifically landslide and building-collapse type incidents. | PS-H2, PS-B1 | E | Grid granularity, vertical subdivision and hazard vocabulary must suit rubble and slope search, not generic field mapping. |
| MC-03 | The system is **multi-agency by construction**, including untrained volunteer organisations. | PS-B2, PS-T1–T4 | E | Single-agency or single-tenant designs fail the statement. Volunteer usability is not optional polish. |
| MC-04 | The system **must not assume cellular data availability**. | PS-B10, PS-K5 | E | Online-only features may exist only as enhancements over an offline-complete core. |
| MC-05 | The system **must not require specialist training**. | PS-B11 | E | No dense forms, no jargon-only UI, no multi-step wizards on the critical path. |
| MC-06 | The **form factors are fixed**: mobile app for the field, web dashboard for the incident commander. | PS-K3, PS-K6 | E | Both must exist; a single responsive web app that cannot do offline/mesh/SMS does not satisfy PS-K5. |
| MC-07 | Search allocation is **grid-based**. | PS-K1 | E | Free-form assignment alone does not satisfy the statement. |
| MC-08 | The picture must be **shared and real-time** (as bounded by NFR-03 and made honest by data-age display). | PS-B6, PS-K2, PS-K11 | E | Per-agency silos with periodic reconciliation do not satisfy the statement. |
| MC-09 | The system must show **who searched which grid, what resources remain, where survivors were reported** — these three questions are the acceptance heart of the statement. | PS-B7, PS-B8, PS-B9 | E | These three must be answerable in one screen. |
| MC-10 | Outcomes are **reduced search time and prevented duplication** — these must be demonstrable, not merely asserted. | PS-B12, PS-B13 | E | Requires the duplication-prevention and coverage-gap features to be measurable in the demo. |

---

## 6. Proposed technical choices *(P — not from the problem statement; for approval, all replaceable)*

| ID | Choice | Rationale | Risk / note |
|---|---|---|---|
| TC-01 | **Native Android** (Kotlin) or Flutter for the field app; not a pure PWA. | SMS send/receive and device-to-device mesh (Nearby/Wi-Fi Direct/BLE) are unavailable to web apps. | Locks the field app to Android for the prototype; iOS support becomes an enhancement (see AMB-13). |
| TC-02 | **SQLite (Room / equivalent)** as the on-device durable store with an outbox table. | Proven durability and query capability offline; supports NFR-07. | — |
| TC-03 | **Event-sourced append-only log with hybrid logical clocks**, plus per-entity merge rules (CRDT-style where fields commute). | Directly satisfies FR-1001, FR-806, FR-812; makes multi-path and out-of-order delivery safe. | More design work than last-writer-wins; worth it — it *is* the EC-01 story. |
| TC-04 | **Mesh via Google Nearby Connections / Wi-Fi Direct / BLE**, with LoRa only as an optional add-on. | Stock-hardware mesh keeps MC-01 intact. | Range is tens of metres, not kilometres — be honest about this in the pitch; positions it as intra-site relay + gateway, not a site-wide radio network. |
| TC-05 | **Compact binary codec over SMS** (bit-packed fields, GSM-7/Base64 framing), with an Android handset or GSM modem acting as the SMS gateway at the command post. | Fits NFR-01; avoids dependence on a commercial SMS provider. | Indian commercial SMS routes need DLT registration; a device-to-device SMS path avoids this (see AMB-08). |
| TC-06 | **PostgreSQL + PostGIS** server-side, with the event log as the source of truth. | Geospatial grid/cell queries and mature tooling. | — |
| TC-07 | **React + MapLibre GL** for the commander dashboard with vector tiles. | Open, self-hostable, works with offline tile packs at the command post (NFR-17). | — |
| TC-08 | **Pre-seeded offline basemap packs** (PMTiles/MBTiles) per operational area, with a basemap-free grid canvas fallback. | Satisfies FR-409 without network. | Basemap licensing must be checked (AMB-14). |
| TC-09 | **Local metric grid** generated over the drawn operational area with `Letter-Number` labels, displaying the MGRS reference alongside. | Local labels are speakable on radio (FR-204); MGRS keeps interoperability with services that already use it. | Confirm with any agency practice you can access. |
| TC-10 | **REST + JSON API** with an explicit versioned schema; optional CAP/EDXL-shaped export profile for authority-level exchange. | FR-901, FR-902, FR-905; standards alignment is a credible EC-04 differentiator. | Full EDXL conformance is out of scope for a prototype; do a documented subset. |
| TC-11 | **Incident join by QR/short code** issuing a device-scoped token; OIDC only for agency administrators. | Serves FR-104 and MC-05 without weakening FR-908. | — |
| TC-12 | **Containerised server, single-node deployable on a laptop** at the command post, syncing upward when a link exists. | NFR-17, FR-711, FR-809. | — |
| TC-13 | Any **"AI"** capability implemented first as transparent, rule-based scoring, with ML models introduced only where they can be evidenced. | Keeps the title honest (PS-H1) without unverifiable claims. | Depends on AMB-01. |

---

## 7. Optional / advanced features *(P — explicitly beyond the problem statement)*

Deliver **none** of these until every M and S requirement is complete. Each is tagged with the evaluation criterion it would strengthen.

| ID | Feature | Strengthens | Note |
|---|---|---|---|
| OF-01 | **Search prioritisation scoring** — rank unsearched cells by survivor likelihood (structure type, reported clues, void space, time since collapse, witness reports). | EC-02, PS-B12 | The most defensible reading of the "AI" in the title; start rule-based (TC-13). |
| OF-02 | **Voice-driven field reporting** (speech-to-structured-report), for hands-busy, gloved operation. | EC-03 | Must degrade to taps offline if models are server-side. |
| OF-03 | **Automated damage/void assessment from field photos**. | EC-02 | Bandwidth-hostile; only where a gateway exists. |
| OF-04 | **Drone or satellite imagery ingest** with change detection to seed grid priority. | EC-02 | Strong visual demo; heavy scope. |
| OF-05 | **Predictive resource depletion** and resupply lead-time alerts. | EC-02 | Natural extension of FR-607. |
| OF-06 | **Assignment optimisation** — suggest next-best cell per team by proximity, capability and priority. | PS-B12 | Suggest, never auto-assign; commanders must retain control. |
| OF-07 | **Missing-person intake and matching** — public/family reports matched against found survivors. | EC-02 | Significant privacy obligations (NFR-13). |
| OF-08 | **Cross-agency terminology auto-translation** and multilingual UI beyond NFR-06. | EC-04, EC-03 | — |
| OF-09 | **LoRa / radio bridge** for site-wide low-bandwidth mesh beyond smartphone radio range. | EC-01 | Hardware — must stay optional under MC-01. |
| OF-10 | **Responder safety monitoring** (heart-rate/motion via wearables, man-down detection). | EC-03 | — |
| OF-11 | **Public information / family liaison view** with sanitised status. | — | Reputational and privacy risk; late-stage only. |
| OF-12 | **Integration with NDMA/SDMA and emergency-number systems**. | EC-04 | High credibility, needs external cooperation. |
| OF-13 | **Automated after-action analytics** beyond FR-1003 (coverage rate curves, duplication avoided, time-to-locate). | PS-B12, PS-B13 | Quantifies the stated outcomes — a strong closing slide. |
| OF-14 | **Integrity heuristics** — flag implausible reports (a cell marked searched faster than physically possible). | EC-02 | — |

---

## 8. Ambiguities requiring a decision

Each carries a **recommended default** so that work is never blocked; the default holds unless overridden.

| ID | Ambiguity | Why it matters | Recommended default |
|---|---|---|---|
| **AMB-01** | The title says "RescueNet **AI**", but the body specifies **no AI capability whatsoever**. | Determines whether AI is scored, decorative, or a trap for scope creep. | Treat AI as **not required**; build the full non-AI core, then add OF-01 (rule-based prioritisation, upgradeable to ML) so the name is justified without risking the core. |
| **AMB-02** | "**Real-time**" is undefined, and is in direct tension with offline operation. | Defines the acceptance bound for PS-K2. | Define as NFR-03 (≤5 s connected, ≤2 min via SMS) **plus** mandatory data-age display (FR-705, FR-410): "real-time when connected, explicitly-aged when not". |
| **AMB-03** | "Mesh-network **or** SMS-based sync" — is either sufficient, or are both expected? | Doubles or halves the hardest engineering item. | Build **both**, because they solve different failures (mesh = no infrastructure, co-located; SMS = infrastructure but no data). Both are also the strongest EC-01 evidence. If time forces a cut, keep SMS (works at range) and demo mesh at reduced fidelity. |
| **AMB-04** | Grid **size, origin and labelling scheme** are unspecified. | Affects every screen and the interop model. | Configurable cell size per incident, default 100 m for landslide / 10 m (plus floor) for building collapse; local `Letter-Number` labels with MGRS shown alongside (TC-09). |
| **AMB-05** | **Scale targets** (responders, teams, agencies, area, incident duration) are unspecified. | Determines data model and sync-load design. | NFR-09 targets: 5 agencies, 20 teams, 200 responders, 5,000 cells, 72 h incident. |
| **AMB-06** | "**Interoperability layer**" — internal multi-agency tenancy, or integration with *external existing* agency systems? Are standards (EDXL/CAP) required? | Two very different builds; EC-04 is judged on this. | Deliver **both readings at proportionate depth**: full internal multi-agency tenancy (deep) + a documented open API with a GeoJSON/CSV and CAP-shaped export (demonstrated with a mock external system). |
| **AMB-07** | Category is "Software", yet mesh networking often implies **hardware**. | A hardware dependency could disqualify or complicate. | Stock-smartphone mesh only in the core (TC-04); LoRa strictly OF-09. |
| **AMB-08** | **SMS cost, regulation and delivery path** (who pays; Indian DLT registration for commercial routes; message limits). | Could block a live SMS demo. | Use **device-to-device SMS** between a field handset and a gateway handset — no commercial provider, no DLT. Document per-message byte budget and cost model. |
| **AMB-09** | **Survivor/casualty data handling** — legal basis, retention, who may view, next-of-kin implications. | Real-world deployability and judging credibility. | Adopt NFR-13: role-restricted access, minimised fields, documented retention, no public exposure by default. |
| **AMB-10** | How much **identity verification** for volunteers, given "minimal training" and chaotic onboarding? | Tension between MC-05 and NFR-12. | Commander-issued join codes with per-device tokens, plus commander-visible roster and revocation; verification of *organisation*, trust-on-first-use for the *individual*. |
| **AMB-11** | Is **multi-incident / authority-level rollup** (multiple simultaneous incidents in one state) in scope? | Data model and dashboard scope. | Model incidents as first-class from day one; build a single-incident UI, keep the rollup view as an enhancement. |
| **AMB-12** | Does the platform **replace radio/voice communication** ("fragmented communication") or complement it? | Big scope difference; also affects FR-204 labelling. | **Complement.** The platform is the shared data picture; voice stays on radio. All identifiers must be radio-speakable so the two reinforce each other. |
| **AMB-13** | **Device assumptions**: BYOD volunteer phones vs issued devices; is **iOS** required? | Affects TC-01 and the mesh/SMS strategy. | Android-first BYOD (dominant among Indian volunteer responders); iOS as a read-mostly enhancement. |
| **AMB-14** | **Offline map data source and licensing** for pre-cached basemaps. | Legal risk and demo feasibility. | OpenStreetMap-derived tiles with attribution; grid-only fallback if unavailable. |
| **AMB-15** | **Which languages** must the field UI support? | NFR-06 scope. | English + Hindi in the prototype, fully externalised strings; icon-and-colour-led UI so language matters less on the critical path. |
| **AMB-16** | Is resource tracking **team-level** or full **logistics/depot management**? | Order-of-magnitude scope difference. | Team-and-supply-point level (FR-601–607). Depot logistics is out of scope. |
| **AMB-17** | What exactly does "**searched**" mean — is a doctrine (e.g. INSARAG-style markings, hasty vs thorough search) required? | Determines FR-302/FR-306 fidelity and real-world credibility. | Two-level model (hasty/primary vs thorough/secondary) with a re-search flag; align labels to INSARAG vocabulary where it is freely available. |
| **AMB-18** | Must the **commander dashboard work fully offline** at a forward post? | Significant architecture consequence (edge server). | Yes — FR-711 + NFR-17 + TC-12. This is also a strong EC-01 demonstration. |
| **AMB-19** | **Demo/judging constraints** — can connectivity loss be staged? Is live SMS permitted at the venue? | Determines what EC-01 evidence is even showable. | Design every EC-01 scenario to be demonstrable **both** live (aircraft mode, two handsets, real SMS) and via a scripted network simulator, so a venue restriction cannot silence the strongest story. |
| **AMB-20** | **Data ownership and retention** after incident closure; who holds the record? | Institutional adoption question. | Incident data owned by the lead authority; per-agency export on closure; documented retention. |

---

## 9. Prototype interpretations for difficult requirements

For each hard requirement: the options, the recommendation, and what the recommendation costs. These are **interpretations, not designs** — the architecture phase follows approval.

### PI-01 — Mesh sync (PS-K5, FR-804)
| Option | Description | Fidelity | Effort | Risk |
|---|---|---|---|---|
| A | **Real device-to-device** via Nearby Connections / Wi-Fi Direct / BLE between handsets. | High | High | Range limited to tens of metres; Android API quirks. |
| B | **Local-Wi-Fi "mesh"** — one handset as hotspot, peers sync to it. | Medium | Low | Honest only if described as a local cluster, not a true mesh. |
| C | **LoRa / external radio** bridge. | High (range) | Very high | Hardware; tension with MC-01. |
| **Rec.** | **A as the real implementation**, with B retained as a guaranteed-working demo fallback, and C named as OF-09. Never present B as A. | | | |

### PI-02 — SMS sync (PS-K5, FR-803)
| Option | Description | Fidelity | Effort | Risk |
|---|---|---|---|---|
| A | **Real SMS** between a field handset and a gateway handset, compact binary codec. | High | Medium | Carrier variability; needs two SIMs. |
| B | **Simulated SMS channel** enforcing the same byte budget and latency, over a test harness. | Medium | Low | Must be labelled as simulated. |
| C | Commercial SMS gateway/API. | High | Medium | DLT registration, cost, network dependence at venue (AMB-08). |
| **Rec.** | **A for the live two-device demo, B for scaled/scripted scenarios.** Publish the measured bytes-per-update either way. | | | |

### PI-03 — "Real-time" under intermittent connectivity (PS-K2)
Reconcile by **redefining the deliverable as truthfulness, not immediacy**: the picture shows the freshest available state *plus its age*, everywhere. A commander is never shown an unqualified position or status. This converts a contradiction into a clarity feature that directly serves EC-02.

### PI-04 — Conflict resolution across partitions (FR-806, FR-308)
| Option | Description | Recommendation |
|---|---|---|
| A | Last-writer-wins per record. | Rejected — can erase a survivor report. |
| B | Last-writer-wins **per field**, with additive sets for reports and observations. | Baseline. |
| C | Event-sourced log + per-entity merge rules; all *additions* (survivor reports, hazards, search events) are union-merged and never lost; only *mutable state* (assignment owner, cell status) resolves by rule; genuine contradictions go to a human conflict queue. | **Recommended** (TC-03). |

### PI-05 — Interoperability layer (PS-K11, FR-901–908)
| Option | Description | Recommendation |
|---|---|---|
| A | **Single instance, multi-agency tenancy** with scoped visibility. | Core — fastest path to a genuinely shared picture. |
| B | **Federated instances** (each agency runs its own, they exchange). | Demonstrate via a second instance syncing over the public API. |
| C | **Standards adapter** (CAP/EDXL-shaped export, GeoJSON/CSV). | Include as a documented subset — high credibility, low cost. |
| **Rec.** | **A deep + B demonstrated + C documented subset.** This covers both readings of AMB-06. | |

### PI-06 — Grid model (PS-K1, FR-203)
| Option | Description | Recommendation |
|---|---|---|
| A | MGRS 1 km / 100 m squares. | Interoperable, but too coarse for a collapsed building and awkward to speak. |
| B | **Local metric grid over the drawn area**, `A1…N`, cell size per incident, with vertical subdivision for structures. | **Recommended** (TC-09) — matches both landslide and collapse scales. |
| C | H3 hexagons. | Elegant, poor fit for rectangular structures and radio speech. |
| **Rec.** | **B, displaying the MGRS reference alongside** so external agencies can cross-reference. | |

### PI-07 — High-stress usability (PS-B11, PS-E3)
Interpret as a hard **"three-tap doctrine"**: the three life-critical actions — *mark cell searched*, *report survivor*, *SOS* — are each reachable in ≤3 taps, never blocked by a spinner, never require typing, and always succeed locally regardless of connectivity. Everything else is secondary UI. This is a testable interpretation (NFR-04), not an aesthetic aspiration.

### PI-08 — Position reporting under scarce bandwidth (FR-405, FR-808)
Do **not** stream position. Report on **meaningful change**: cell entry/exit, status change, report filed, distance/time threshold exceeded, or explicit check-in. This preserves the commander's picture (PS-K7) at a fraction of the bytes, and makes NFR-01 achievable on the SMS path.

### PI-09 — Offline commander dashboard (FR-711)
Interpret as an **edge deployment**: a single-node server at the forward command post that is simultaneously the dashboard host, the mesh/SMS gateway (FR-809) and the upward-syncing client. This makes the whole system function with the outside world entirely absent — the strongest possible EC-01 statement.

### PI-10 — "AI" in the title (PS-H1, AMB-01)
Interpret as **decision support, evidenced not claimed**: rule-based cell prioritisation (OF-01) with a transparent scoring explanation, architected so an ML model can replace the scorer. Avoid presenting any capability the prototype cannot demonstrate.

---

## 10. Requirement traceability framework

### 10.1 Purpose
Every feature that reaches the build must be justifiable by pointing at a clause of the official problem statement — and every clause of the statement must be demonstrably covered. The framework runs in both directions.

### 10.2 The register (single artefact, maintained continuously)

Each row of the requirements register carries these columns:

| Column | Content |
|---|---|
| `Req ID` | FR/NFR/MC/EC/OF identifier |
| `Statement` | One testable sentence |
| `PS Source` | One or more `PS-*` clause IDs, or `NONE` |
| `Provenance` | `E` / `I` / `P` |
| `Justification` | Required whenever provenance is `I` (why the explicit requirement is unachievable without this) or `P` (why it is worth building anyway) |
| `Priority` | M / S / C |
| `Evaluation link` | EC-01…EC-04, or `—` |
| `Verification` | D / T / I / A |
| `Test/Demo ID` | `TST-*` or `DEMO-*` reference |
| `Module` | Owning component (assigned in the architecture phase) |
| `Status` | Proposed / Approved / Designed / Built / Verified / Deferred / Cut |

### 10.3 Governing rules

1. **No orphan features.** No item enters the backlog without at least one `Req ID`. No requirement exists without a `PS Source` or an explicit `NONE` + justification.
2. **No silent scope growth.** Anything with provenance `P` is labelled "enhancement" in every internal document, demo script and submission.
3. **Backward coverage gate.** Every `PS-*` clause in §1 must map to ≥1 requirement with priority M or S. A clause with zero coverage is a build blocker.
4. **Forward evaluation gate.** Every `EC-*` must map to ≥1 verification scenario, and every M requirement must have a verification method assigned before it is built.
5. **Ambiguity closure.** Every `AMB-*` is either answered by the user or recorded as "proceeding on recommended default", and the resulting decision is written into the affected requirement rows.
6. **Cut discipline.** Requirements may be cut only in priority order C → S; cutting an M requires an explicit, recorded decision, because it is a departure from the problem statement.

### 10.4 Backward coverage matrix (PS clause → requirements)

| PS clause | Covered by |
|---|---|
| PS-H1 (AI in title) | AMB-01, OF-01, TC-13 — *no explicit requirement in the statement body* |
| PS-H2 (disaster management) | MC-02, FR-201 |
| PS-H3 (software category) | MC-01, TC-04, OF-09 |
| PS-B1 (landslide / building collapse) | FR-201, FR-207, FR-208, MC-02, AMB-04 |
| PS-B2 (multiple agencies) | FR-101, FR-103, FR-206, FR-704, FR-903, MC-03 |
| PS-B3 (fragmented communication) | FR-204, FR-709, FR-905, AMB-12 |
| PS-B4 (duplicated effort) | FR-303, FR-506, MC-10 |
| PS-B5 (uncovered zones) | FR-304, FR-703 |
| PS-B6 (no shared picture) | FR-701, FR-702, MC-08 |
| PS-B7 (who searched which grid) | FR-305, FR-205, FR-708, FR-1001, FR-1002, MC-09 |
| PS-B8 (what resources remain) | FR-603, FR-604, FR-607, MC-09 |
| PS-B9 (where survivors reported) | FR-501, FR-504, FR-507, NFR-13, MC-09 |
| PS-B10 (chaotic, low-bandwidth site) | FR-408, FR-410, FR-412, FR-801–812, NFR-01, NFR-02, NFR-08, NFR-17, MC-04 |
| PS-B11 (minimal training) | FR-104, FR-407, FR-408, NFR-04, NFR-05, NFR-20, MC-05, PI-07 |
| PS-B12 (cut search time) | FR-306, FR-703, FR-707, FR-1003, OF-01, OF-06, OF-13, MC-10 |
| PS-B13 (prevent duplication) | FR-303, FR-706, FR-1003, MC-10 |
| PS-K1 (grid-based allocation) | FR-202, FR-203, FR-206, FR-301, MC-07, PI-06 |
| PS-K2 (real-time status tracking) | FR-302, FR-307, FR-907, NFR-03, AMB-02, PI-03 |
| PS-K3 (low-bandwidth mobile app) | FR-401, FR-409, FR-411, FR-802, FR-808, NFR-01, NFR-10, NFR-11 |
| PS-K4 (offline data entry) | FR-402, FR-403, FR-404, FR-606, FR-811, NFR-02, NFR-07 |
| PS-K5 (mesh or SMS sync) | FR-803, FR-804, FR-805, FR-806, FR-807, FR-809, FR-812, NFR-15, AMB-03, PI-01, PI-02 |
| PS-K6 (commander web dashboard) | FR-701, FR-703, FR-711, MC-06 |
| PS-K7 (team positions) | FR-405, FR-406, FR-702, FR-710, PI-08 |
| PS-K8 (search status aggregation) | FR-302, FR-702, FR-703, FR-705 |
| PS-K9 (survivor reports aggregation) | FR-501, FR-502, FR-507, FR-702, FR-707 |
| PS-K10 (resource inventory) | FR-601, FR-602, FR-603, FR-605, FR-606, AMB-16 |
| PS-K11 (interoperability layer) | FR-106, FR-107, FR-901–908, NFR-16, AMB-06, PI-05 |
| PS-T1–T4 (beneficiaries) | FR-101, FR-103, FR-104, NFR-06, NFR-11, MC-03 |
| PS-E1 | EC-01 |
| PS-E2 | EC-02 |
| PS-E3 | EC-03 |
| PS-E4 | EC-04 |

**Coverage result:** every PS clause has at least one M or S requirement, with the single exception of **PS-H1 ("AI")**, which the statement body never substantiates — tracked as AMB-01.

### 10.5 Forward matrix (requirement → evaluation criterion)
Maintained in the register's `Evaluation link` column. Any M requirement that maps to no `EC-*` is re-examined: either it is genuinely infrastructural (acceptable) or it is scope creep in disguise.

---

## 11. Deep dive on the four emphasised concerns

### 11.1 Low-connectivity robustness (PS-B10, PS-K3–K5, EC-01)
- **Governing principle:** the network is treated as an *optional accelerator*, never a dependency. Every field write commits locally first and is answered by the UI immediately (FR-402, FR-403).
- **Requirement cluster:** FR-402–404, FR-801–812, FR-711, NFR-01–02, NFR-07–08, NFR-14–15, NFR-17.
- **The three failure modes to survive explicitly:** (i) no data but SMS available; (ii) no infrastructure at all but responders co-located; (iii) central server unreachable while the site itself functions.
- **Principal risks:** mesh range far smaller than a disaster site (PI-01); SMS byte budget too small for rich reports (mitigated by FR-808 priority ordering and PI-08 event-driven positions); merge correctness after long partitions (PI-04).
- **Evidence to produce:** measured bytes per update type; a partition/reunite test with a deterministic, inspectable merge; a server-down live demo.

### 11.2 Shared operational picture (PS-B6–B9, PS-K11, EC-02)
- **Governing principle:** the picture is *shared* only if every agency both contributes to and reads from the same model (FR-902), and it is *operational* only if its staleness is always visible (FR-705).
- **Acceptance heart (MC-09):** one screen must answer — *which cells are unsearched?* · *who searched cell X and when?* · *what resources remain and where?* · *where are survivors and how fresh is that report?*
- **Requirement cluster:** FR-301–308, FR-501–507, FR-601–607, FR-701–709, FR-1001–1002.
- **Principal risks:** visual overload under many layers (mitigate with FR-704 filters and a deliberate default view); false confidence from stale data (FR-705 is a must, not a nicety).

### 11.3 High-stress usability (PS-B11, EC-03)
- **Governing principle:** design for a tired, gloved, frightened, possibly first-time user in poor light and noise — the three-tap doctrine (PI-07).
- **Requirement cluster:** FR-104, FR-309, FR-407, FR-408, FR-410, FR-412, NFR-04, NFR-05, NFR-06, NFR-20.
- **Testable rather than asserted:** tap counts, time-to-complete, and completion rate for a first-time user with no instruction (NFR-04) — plan to run this and report the numbers, since EC-03 is scored on it.
- **Principal risks:** feature richness eroding the critical path; forms creeping onto the survivor-report screen; connectivity errors intruding into the field UI (they must appear only as a passive freshness indicator, never as a blocking dialog).

### 11.4 Interoperability across agencies (PS-B2, PS-K11, EC-04)
- **Governing principle:** interoperability means an agency can join **without changing how it works internally** — shared model, own vocabulary (FR-906), own data scopes (FR-904).
- **Requirement cluster:** FR-101, FR-106, FR-107, FR-901–908, FR-905, NFR-16, plus the join flow FR-903 and FR-104.
- **Three demonstrable layers:** (1) human/organisational — a new agency joins a live incident in under a minute; (2) system — an external system reads and writes via the documented API; (3) archival — GeoJSON/CSV (and a CAP-shaped) export for agencies that cannot integrate at all.
- **Principal risks:** interoperability reduced to "multiple logins on one app" (insufficient for EC-04 — the API and an external-system demo are what make the claim real); over-investing in full EDXL conformance (do a documented subset instead).

---

## 12. Explicitly out of scope (unless you direct otherwise)

Recorded so scope decisions are deliberate, not accidental:
voice/radio communication replacement (AMB-12) · depot-level logistics and procurement (AMB-16) · public-facing information portals (OF-11) · medical records / hospital handover systems · financial or compensation workflows · long-term disaster recovery and rehabilitation phases · payroll, rostering or HR for responders · drone flight control (as opposed to imagery ingest, OF-04).

---

## 13. Decisions needed from you before the architecture phase

| # | Question | Ambiguity | Blocking? |
|---|---|---|---|
| 1 | Is **AI a scored expectation** despite being absent from the statement body, or is the non-AI core sufficient? | AMB-01 | No — default holds (build core, add OF-01) |
| 2 | **Mesh and SMS both**, or is one acceptable? And can we demo real SMS/two devices? | AMB-03, AMB-19 | No — default is both |
| 3 | Which reading of "**interoperability layer**": internal multi-agency, external system integration, or both? | AMB-06 | No — default is both at proportionate depth |
| 4 | Confirm **scale targets** and **grid defaults** (NFR-09, AMB-04). | AMB-04, AMB-05 | No |
| 5 | Confirm **Android-only field app**, and whether iOS is expected. | AMB-13 | No |
| 6 | Confirm **language scope** (English + Hindi baseline). | AMB-15 | No |
| 7 | Confirm the **offline commander dashboard / edge server** is in scope — it is a real architectural commitment. | AMB-18 | **Yes** — changes the architecture materially |

---

## 14. Approval

On approval of this document (with any corrections to §8 and §13), the next deliverable is the **architecture and data model**, followed by the **requirements register** in tracked form and the **demo scenario scripts** mapped to EC-01…EC-04.
