# RescueNet AI — Technical Feasibility Analysis (v1.0, for approval)

**Status:** Draft for approval · **Date:** 2026-08-22 · **Stage:** Feasibility (no architecture, no code)
**Source of truth:** the official problem statement. **Companion documents:** [`01-requirements-analysis.md`](01-requirements-analysis.md) (requirement IDs, sources, provenance) · [`02-prototype-scope.md`](02-prototype-scope.md) (A/B/C/D classification, Level 1–3 scope, decisions D-01 and D-02).

> **D-02 is open in this document.** Per your instruction, SMS-based sync and phone-to-phone sync both remain candidate Level-1 implementations until §2 compares them. §2 closes with a single recommendation.

---

## 0. Scope, method and assumptions

### 0.1 What this document does
Assesses whether each approved Level-1 package (and the Level-2 packages that affect Level-1 decisions) can actually be built and — critically — **proven** in a prototype. Every package is analysed against the twelve questions you specified. Where a feature is hard, alternatives are compared before a recommendation is made.

### 0.2 What it deliberately does not do
No system architecture, no data model, no schemas, no code, no technology lock-in beyond what feasibility requires. Technology names appear only where the feasibility verdict depends on them.

### 0.3 Standing assumptions (state them, correct them if wrong)

| ID | Assumption | Consequence if wrong |
|---|---|---|
| AS-01 | Team of 3–4 developers over ~5–6 weeks; effort quoted in **developer-days**. | All estimates in §9 scale proportionally. |
| AS-02 | At least **2 physical Android phones** available throughout, plus **2 SIMs with active SMS**, ideally on different carriers. | The SMS path cannot be proven; §5 substitute applies. |
| AS-03 | Android 10–14 target range; sideloaded APK, not Play Store distribution. | Play Store distribution would require an SMS-permission declaration and review (§2.2). |
| AS-04 | Demo venue has unreliable Wi-Fi and congested 2.4 GHz, but working cellular voice/SMS. | Drives the transport recommendation in §2.6. |
| AS-05 | All demo data is synthetic. No real survivor or casualty data at any point. | NFR-13 obligations would change materially. |
| AS-06 | Judges see a live demo of 8–12 minutes, plus documentation. | Determines what "provable" means in practice. |

### 0.4 Ratings used

**Feasibility:** `High` (well-trodden, low unknowns) · `Medium` (achievable, known pitfalls) · `Low` (significant unknowns, needs a spike first)
**Risk:** `Low` / `Medium` / `High` — probability × impact on the demo
**Difficulty:** `S` (≤2 dev-days) · `M` (3–5) · `L` (6–10) · `XL` (>10)

---

## 1. Executive summary

### 1.1 Verdict per Level-1 package

| Package | Feasibility | Difficulty | Risk | Note |
|---|---|---|---|---|
| L1-01 Incident & grid | High | M | Low | Ordinary geospatial work. |
| L1-02 Agencies, teams, roles, joining | High | M | Low | Deliberately simple auth is an asset here. |
| L1-03 Allocation, status, duplication | High | L | Low | The statement's core; no technical unknowns. |
| L1-04 Offline-first field app | Medium | XL | **Medium** | The largest package. Offline correctness is where prototypes usually fail. |
| L1-05 Position reporting | High | S | Medium | GPS in rubble/indoors is genuinely poor — a limitation to state, not solve. |
| L1-06 Survivor reporting | High | S | Low | Rides on L1-04's offline machinery. |
| L1-07 Resource inventory | High | S | Low | Simplest package. |
| L1-08 Sync engine + fallback transport | **Medium** | XL | **High** | The differentiating package and the riskiest. See §2 and §3.8. |
| L1-09 Commander dashboard | High | L | Low | D-01 (online-only) removed the hard part. |
| L1-10 Interoperability layer | High | M | Low | Mostly discipline and documentation. |
| L1-11 Evidence & measurement | High | M | **Medium** | Risk is that it gets skipped under deadline pressure — which would cost three of four scored criteria. |

### 1.2 The three findings that should change your plan

1. **The transport decision goes to SMS, but not for the reason previously given** (§2). The decisive factors are venue RF conditions and testability, not elegance. Phone-to-phone sync covers a failure mode SMS cannot — total cellular absence — so it belongs at Level 2, and the sync engine must be built transport-agnostic from day one so it slots in without redesign.

2. **D-01 has quietly changed what FR-303 can demonstrate** (§5.3). With an online-only dashboard, two commanders cannot realistically create an offline duplicate *assignment*. The demonstrable — and more faithful — case is duplicate *search effort*: two offline teams both search cell B-14, both events survive the merge, and the commander sees the duplication. This maps to PS-B4 more directly than the original framing. It needs an explicit decision (§10).

3. **Android's outgoing-SMS throttle (~30 messages / 30 minutes, OEM-dependent) is a hard constraint on the demo**, not a scalability footnote (§2.2). It forces event batching into each SMS from the start. This is a design consequence discovered in feasibility, exactly where it should be.

### 1.3 Reliability claim discipline
Nothing in this plan proves disaster-grade reliability, and §6 states precisely what may and may not be claimed. The prototype can prove *mechanism* (data survives offline, merges deterministically, arrives over a degraded transport). It cannot prove *endurance, scale, or field survivability*, and no document, slide or demo script should imply otherwise.

---

## 2. THE TRANSPORT DECISION — comparing the PS-K5 candidates

**Requirement under test:** PS-K5 — *"offline-capable data entry with mesh-network **or** SMS-based sync where cellular data is unavailable."*

Three candidates, as instructed.

### 2.1 An analytical point that reframes the comparison

Options 1 and 2 are **transports** — physical ways to move bytes between two devices. Option 3, "reduced mesh / store-and-forward", is **not a third transport**: it is a *protocol layer* (delay-tolerant, epidemic/gossip exchange of an event log) that runs **on top of** whichever transport exists. It can even run over a transport as crude as a QR code on a screen.

This matters because the choice is not three-way. It is:
- **Which transport is mandatory at Level 1?** (a genuine either/or — §2.2–§2.5)
- **Is store-and-forward gossip built on top of it?** (a layering decision — §2.5)

Treating option 3 as a peer of the other two would produce a false comparison. Treated correctly, it turns out to be the cheapest of the three to add *provided the sync engine is event-log-based*, which L1-08 already requires for other reasons.

### 2.2 Option 1 — SMS-based synchronisation

**How it would work:** each operational change is an event; events are bit-packed into a compact binary schema, several batched per message, and sent by the field handset to a **gateway handset** at the command post, which forwards them to the server over its own data link. The reverse path carries assignments back.

| Dimension | Assessment |
|---|---|
| **PS compliance** | **Full and unambiguous.** SMS is named verbatim in PS-K5. No interpretation required. |
| **Development complexity** | Medium–high. The codec is the work: a compact schema, bit-packing, batching, segmentation, dedupe, acknowledgement and retry. Roughly 6–8 dev-days including the gateway. |
| **Android / platform constraints** | Several, all navigable: `SEND_SMS` and `RECEIVE_SMS` are runtime permissions; the app **does not** need to be the default SMS handler to send, or to receive the broadcast. **Port-addressed data SMS** (binary, invisible to the user's inbox) is the clean mechanism, but **carrier support for binary SMS in India is not guaranteed** — this is spike SP-01. Fallback is GSM-7 text SMS with a Base64-ish packing (~117 usable bytes per 160-character segment). **Critical constraint:** the Android framework throttles non-default apps at roughly **30 outgoing messages per 30 minutes** before showing a user-confirmation dialog (OEM-dependent). This forces batching and caps burst sync. Play Store distribution would additionally require an SMS-permission declaration — irrelevant for a sideloaded prototype (AS-03). |
| **External services / hardware** | **None.** No SMS gateway provider, no DLT registration, no cloud dependency — because it is device-to-device. Requires 2 SIMs with SMS credit and cellular coverage. |
| **Works when mobile data is unavailable** | **Yes.** This is precisely its niche, and precisely PS-K5's wording. |
| **Works when cellular service is entirely unavailable** | **No — total failure.** This is the option's real weakness and must be stated plainly wherever it is presented. |
| **Prototype reliability** | Medium. Delivery is usually seconds but occasionally minutes; ordering is not guaranteed; silent drops happen. All are handled by dedupe + retry, but latency is not controllable. |
| **Deterministic testing** | **Good.** Behind a transport interface, the entire sync engine tests in-process with a loopback transport, including partition/reunite scenarios, in CI. Real-SMS testing is a smaller, separate, manual matrix. |
| **Demo impact** | Medium. Less visually striking than phones talking to each other — but **immediately legible to every judge**: "mobile data off, the update travelled by SMS, here it is on the dashboard, and here are the 94 bytes it took." |
| **Ability to prove it works** | **Strong.** Byte counts per event type, carrier delivery timestamps, on-screen payload inspection, before/after dashboard state. Concrete, quotable evidence. |
| **Implementation time** | ~6–8 dev-days (codec 3, transport + permissions 2, gateway 2, hardening 1). |
| **Scalability limits** | **Severe, and honest to admit:** ~117–140 bytes per segment, per-message cost, the ~30/30min throttle, and one gateway handset as a chokepoint. Fine for tens of events per team per hour; unusable for continuous telemetry. This is why PI-08 (event-driven, not streamed, positions) exists. |

### 2.3 Option 2 — Nearby phone-to-phone synchronisation

**How it would work:** co-located handsets discover each other over BLE/Bluetooth/Wi-Fi and exchange events directly; any handset that later reaches connectivity uploads what it carries.

Three sub-variants, materially different in feasibility:

| Variant | Mechanism | Feasibility note |
|---|---|---|
| **2a** | **Google Nearby Connections API** (P2P_STAR/CLUSTER) | Highest-level API, handles discovery and transport switching. **Requires Google Play Services.** Permission surface changes significantly across Android 10/12/13 (location → `BLUETOOTH_SCAN/ADVERTISE/CONNECT` → `NEARBY_WIFI_DEVICES`). |
| **2b** | **Raw Wi-Fi Direct / BLE GATT** | No Play Services dependency, but discovery and pairing are notoriously flaky across OEMs; BLE throughput is very low. |
| **2c** | **Local-only hotspot + plain HTTP** — one phone hosts, peers sync over the local link | **Least impressive, most reliable, easiest to test.** No Play Services. Programmatic local-only hotspot is available on modern Android, though OEM behaviour varies. |

| Dimension | Assessment |
|---|---|
| **PS compliance** | **Partial, and must be described honestly.** Single-hop peer exchange is not a mesh network. It satisfies the *spirit* of PS-K5's mesh clause only if paired with the store-and-forward layer (option 3); on its own it is "peer-to-peer sync", and calling it "mesh" would be an overclaim a technical judge can catch. |
| **Development complexity** | Medium–high, and **front-loaded with platform debugging rather than logic**. 2a: ~5–8 dev-days, much of it permissions and device quirks. 2c: ~3–4 dev-days. |
| **Android / platform constraints** | The heaviest of the three options. Play Services dependency (2a); permission churn across API levels; aggressive OEM battery managers killing background discovery; **no emulator support** — every test needs two physical devices. |
| **External services / hardware** | No network services, but 2a depends on Google Play Services (an on-device external dependency). Requires ≥2 physical handsets for any testing at all. |
| **Works when mobile data is unavailable** | Yes. |
| **Works when cellular service is entirely unavailable** | **Yes — and it is the only option that does.** This is its unique and genuinely important strength: it is the answer to a disaster that has taken the cell towers down, which is the scenario the problem statement's background actually describes. |
| **Prototype reliability** | **Medium–low, and environment-dependent.** A judging venue is a hostile RF environment: saturated 2.4 GHz, hundreds of Bluetooth devices, competing hotspots. Discovery timeouts in that setting are common — and they happen live, in front of the judges, with no recovery narrative. |
| **Deterministic testing** | **Weak.** Cannot run in CI. Cannot run on emulators. Every regression check needs two charged physical devices in proximity. The sync *logic* is still testable behind the transport interface; the *transport* is not. |
| **Demo impact** | **High.** Two phones, both with everything off, data visibly hopping between them, then surfacing on the dashboard. The most visceral demonstration available — when it works. |
| **Ability to prove it works** | Good visually; harder to evidence rigorously. Connection logs and event traces help, but reliability claims would rest on a handful of successful runs. |
| **Implementation time** | 2a: ~5–8 dev-days · 2c: ~3–4 dev-days, plus recurring debugging time that is hard to bound. |
| **Scalability limits** | Range 10–100 m depending on radio; a Nearby cluster practically handles a handful of peers; no multi-hop without the option-3 layer. Range is far below the scale of a landslide site. |

### 2.4 Option 3 — Reduced mesh / store-and-forward (delay-tolerant gossip)

**How it would work:** every device holds the append-only event log (already required by L1-08 / FR-1001). When any two devices meet over *any* transport, they exchange the events the other lacks. When any device reaches the server, it uploads everything it carries — including events authored by teams it has never met. Multi-hop delivery is achieved through **responder mobility** rather than radio range: a runner returning to the command post is the network.

| Dimension | Assessment |
|---|---|
| **PS compliance** | **The closest of the three to "mesh-network" in substance** — genuine multi-hop, store-carry-forward delivery — while remaining honestly describable as "store-and-forward relay". |
| **Development complexity** | **Low *as an increment*, high *as a foundation*.** Given an event log with stable IDs and a transport interface, pairwise reconciliation is ~2–3 dev-days. Without that foundation it is a rewrite. |
| **Android / platform constraints** | Inherits entirely from whichever transport carries it. Adds none of its own. |
| **External services / hardware** | None beyond the underlying transport. |
| **Works when mobile data unavailable / cellular unavailable** | Inherits from the transport. Over option 2 it survives both; over option 1 it survives the first only. |
| **Prototype reliability** | Good at the protocol level — it is designed for intermittence — but bounded by transport reliability. |
| **Deterministic testing** | **Excellent.** The gossip protocol is pure logic over an event log: multi-node convergence, partition, reunion and out-of-order delivery all test in-process, in CI, with no devices at all. |
| **Demo impact** | High **if narrated well** ("this phone never met the server; its data arrived anyway, carried by another responder"). Weak if narrated as plumbing. |
| **Ability to prove it works** | **Strongest of the three**, because convergence is a property you can assert in an automated test and show as a log. |
| **Implementation time** | +2–3 dev-days on top of a transport, **provided** L1-08 is event-log-based. |
| **Scalability limits** | Log grows unbounded without compaction (out of prototype scope); pairwise reconciliation is fine at prototype scale. Delivery latency is governed by human movement — minutes to hours, which is honest for the domain. |

### 2.5 Comparison matrix

Scale: ●●● strong · ●● adequate · ● weak

| Criterion (as specified) | **1 · SMS** | **2 · Phone-to-phone** | **3 · Store-and-forward layer** |
|---|:--:|:--:|:--:|
| Compliance with the official statement | ●●● verbatim | ●● partial ("mesh" only with layer 3) | ●●● closest in substance |
| Development complexity (lower = better) | ●● medium–high | ● high, platform-bound | ●●● low as an increment |
| Android / platform constraints | ●● permissions, throttle | ● Play Services, permission churn, OEM quirks | ●●● none of its own |
| Need for external services | ●●● none (device-to-device) | ●● Play Services (2a) | ●●● none |
| Works with **no mobile data** | ●●● yes | ●●● yes | ●●● inherits |
| Works with **no cellular at all** | ● **no** | ●●● **yes — unique** | ●● inherits |
| Prototype reliability | ●● carrier-dependent | ● venue-RF-dependent | ●●● protocol-level |
| Deterministic testing | ●●● loopback + CI | ● devices only, no CI | ●●● pure logic, full CI |
| Demo impact for judges | ●● legible | ●●● visceral | ●● needs narration |
| Ability to prove it works | ●●● byte counts, delivery logs | ●● a few successful runs | ●●● automated convergence proofs |
| Implementation time | ●● 6–8 dev-days | ● 5–8 + unbounded debugging | ●●● +2–3 dev-days |
| Scalability limitations | ● severe (bytes, cost, throttle) | ● severe (range, peers) | ●● log growth, human-speed latency |

### 2.6 Recommendation — one mandatory Level-1 fallback

> ### **SMS-based synchronisation is the mandatory Level-1 prototype fallback.**
> **Phone-to-phone sync moves to Level 2** (reduced form, variant 2c or 2a).
> **The store-and-forward layer is built at Level 1** as part of the sync engine, because it is nearly free there and it is what makes the Level-2 promotion cheap.

**Why SMS wins on the combination you asked to optimise — reliable demonstration, requirement compliance, realistic implementation:**

1. **Compliance is unarguable.** PS-K5 names SMS. No judge can question whether the clause was met, and no honest framing gymnastics are required. Phone-to-phone sync only satisfies the "mesh" reading with the layer-3 addition, and even then "mesh" is a stretch for single-hop radio.
2. **It survives the demo environment.** This is decisive and it is not a technical-elegance argument (AS-04). A judging venue saturates 2.4 GHz and Bluetooth; peer discovery failures happen live, unrecoverably, in the eight minutes that matter. Cellular SMS is essentially unaffected by that congestion.
3. **It is testable without ceremony.** Behind a transport interface the whole engine runs in CI with a loopback transport. Phone-to-phone requires two physical devices for every check, which under deadline pressure means it stops being checked.
4. **It matches the operational geometry.** Teams on a landslide site are dispersed across hundreds of metres to kilometres. SMS spans that; smartphone radios span tens of metres. The option that reaches the actual responders is the more faithful answer to PS-K5's "where cellular data is unavailable".
5. **No external dependencies.** Device-to-device SMS needs no gateway provider, no DLT registration, no Play Services, no cloud. Fewer things that can be missing on demo day.
6. **The evidence is concrete.** "94 bytes, delivered in 6 seconds, mobile data off" is a provable claim. Peer-sync reliability would rest on anecdote.

**What this recommendation knowingly gives up, stated plainly:**

- **SMS cannot operate when cellular service itself is down** — which is a realistic disaster condition and arguably the harder one. The prototype does not solve it; Level 2 (L2-01) does, and §8/FE-04 documents the production answer. This limitation must appear in the demo narration and the submission, not be quietly omitted.
- **The more striking demo is the one not chosen.** That is the deliberate trade: a demonstration that works every time beats a demonstration that impresses when it works.

**The architectural condition that makes this decision safe** (a feasibility constraint, not an architecture): the sync engine must be built against a **transport-agnostic interface** — send(bytes) / receive(bytes), no SMS semantics leaking upward — and the reconciliation must be **event-log gossip, not point-to-point state push**. Meet those two conditions and promoting phone-to-phone from Level 2 costs the transport adapter alone (~3–4 dev-days), with no change to the engine. Miss them and the promotion is a rewrite. This is the single most consequential design constraint arising from the feasibility work.

**Status of D-02:** superseded by **D-02-REVISED** above, pending your approval (§10, decision 1).

---

## 3. Feasibility per Level-1 package

Each package is analysed against the twelve questions specified, plus an alternatives comparison where the choice is genuinely open.

---

### 3.1 · L1-01 — Incident setup and grid generation
*FR-201, FR-202, FR-203, FR-204 · Explicit: FR-203*

1. **Exact prototype capability.** Create an incident (name, type, location); draw a rectangle or polygon over a map; generate a rectangular grid at a configurable cell size (default 100 m landslide / 10 m collapse); cells labelled `A1…N`, short and speakable; grid frozen once published.
2. **Recommended approach.** Server-side generation from the drawn polygon into persisted cell records with geometry, stored in a spatial database. Labels assigned row/column from the polygon's local origin. Grid is generated once and never regenerated in-incident.
3. **Technical feasibility.** **High.** Ordinary geospatial work with mature libraries on both server and client. No unknowns.
4. **Dependencies.** A map component on the dashboard; a spatial store; nothing else. Blocks L1-03, L1-04, L1-05, L1-09 — so it must land first.
5. **Platform limitations.** Cell count grows quadratically as size shrinks: a 500 m × 500 m area at 10 m cells is 2,500 cells; at 5 m it is 10,000 — **which exceeds `MAX_CELLS` = 8,191 and would be refused** (point 8). Rendering thousands of polygons in a browser needs canvas/WebGL rather than DOM markers, and the mobile client must receive the grid as compact geometry rather than per-cell records.
6. **External services / hardware.** None. Basemap tiles are optional at Level 1 (grid renders without them).
7. **Difficulty / risk.** **M / Low.**
8. **Failure modes.** Cell counts exploding on a large drawn area (mitigate: hard cap at **`MAX_CELLS` = 8,191**, the Level-1 maximum derived from the 13-bit `cell_index` wire field — normative in `09` §10.5. The 5,000-cell figure elsewhere in this document is the NFR-09 evaluation *target*, not the maximum); labels becoming ambiguous at large grids (`AA1` beyond 26 columns); polygon self-intersection from sloppy drawing; grid regenerated mid-incident orphaning search history (mitigate: forbid it outright at Level 1).
9. **How tested.** Unit tests on the generator: cell counts, coverage of the polygon, label uniqueness and stability, idempotent regeneration for identical input. A fixed reference polygon with an expected cell set as a golden test.
10. **How demonstrated.** Commander draws the area on the dashboard in ~10 seconds; grid appears; a cell is tapped to show its label and geometry; the same grid then appears on the field handset.
11. **Evidence it works.** Golden-test output; a screenshot pair (dashboard grid ↔ handset grid) showing identical labels; the cell-count/area figures.
12. **Honest limitations.** Rectangular grid only — no terrain-following, no slope correction, no true vertical/floor subdivision (deferred to L2-12). Cell size is uniform across the whole area, whereas a real incident wants fine cells over the collapse and coarse cells over the approach.
13. **Production differences.** Variable-resolution grids, MGRS cross-referencing for radio interoperability, terrain-aware cell shaping, grid versioning with history migration, and per-structure 3-D subdivision for collapsed buildings.

---

### 3.2 · L1-02 — Agencies, teams, roles and joining
*FR-101–FR-107 · Explicit: FR-101*

1. **Exact prototype capability.** 3–4 seeded agencies of different types; teams with callsigns; three roles (field responder, incident commander, observer); join-an-incident by short code with no account creation; device token cached for offline use; every record stamped with responder, team and agency; read-all / write-own-team enforcement.
2. **Recommended approach.** Commander generates a join code per team; the handset exchanges it once for a long-lived device token held in secure local storage; the token is presented on every sync. Authorisation is a small ownership rule checked server-side, not a policy engine.
3. **Technical feasibility.** **High.** The deliberate simplicity — no passwords, no SSO, no reset flows — removes most of the usual cost.
4. **Dependencies.** Must exist before any attributed data (L1-03, L1-05, L1-06, L1-07). Feeds L1-10's join demonstration directly.
5. **Platform limitations.** Secure token storage on Android is straightforward; the real constraint is that a lost or reset device loses its identity and must re-enrol.
6. **External services / hardware.** None. QR scanning is optional polish over typing a 6-character code.
7. **Difficulty / risk.** **M / Low.**
8. **Failure modes.** Code reuse creating two devices claiming one team identity (acceptable at prototype scale, must be stated); no revocation path if a device is lost; clock-independent tokens never expiring; an offline device holding authorisation that a commander has since withdrawn.
9. **How tested.** Enrol/deny/scope unit tests server-side; an offline authorisation test (enrol, go offline, restart the app, confirm full function); an attribution test asserting every generated record carries actor, team and agency.
10. **How demonstrated.** A "new volunteer group arrives on site" moment: type a code, and within seconds their team appears on the commander's map and their reports flow into the shared picture — the single most persuasive EC-04 beat available.
11. **Evidence it works.** Screen recording of the join in under 30 seconds; the API response showing agency attribution on records; the scope test suite.
12. **Honest limitations.** **Trust-on-first-use with no identity verification.** Anyone with the code joins as that team. There is no revocation, no device binding, no audit of who physically holds a device. This is acceptable for a prototype and unacceptable for deployment, and must be said in exactly those terms.
13. **Production differences.** Agency-federated identity, verified organisational onboarding, device binding and remote revocation, role delegation, and an approval workflow for mid-incident joins.

---

### 3.3 · L1-03 — Cell allocation, status tracking and duplication prevention
*FR-301–305, FR-307, FR-309, FR-706 · Explicit: FR-301–305*

1. **Exact prototype capability.** Commander assigns cells to teams; five statuses (`unassigned → assigned → in progress → searched → needs re-search`); assigning a held cell is blocked with a warning naming the holder; offline-created collisions are flagged with both claims visible; unsearched cells visually and numerically unmistakable; every transition records team, responder, agency and time; reassign and re-open available; responders see their assignment offline.
2. **Recommended approach.** Status changes are events (L1-08), not field updates — this is what makes attribution and merge behaviour fall out for free. Duplicate prevention is a server-side check on assignment; duplicate *effort* is detected by two search events on one cell from different teams.
3. **Technical feasibility.** **High.** No technical unknowns; the difficulty is interaction design, not engineering.
4. **Dependencies.** L1-01 (grid), L1-02 (teams), L1-08 (event log and merge). Carries EC-02 almost single-handedly.
5. **Platform limitations.** Selecting many cells on a phone screen is awkward — keep multi-cell assignment on the dashboard and single-cell actions on the handset.
6. **External services / hardware.** None.
7. **Difficulty / risk.** **L / Low.**
8. **Failure modes.** Two offline devices reporting different terminal statuses for one cell (resolved by the stated merge rule, with the loser preserved and flagged); a stale assignment on a handset that has been offline for hours, sending a responder to a cell already reassigned (**cannot be fully prevented — it is the honest cost of offline operation**, and the freshness indicator is what makes it visible); status regression on late-arriving events.
9. **How tested.** State-machine unit tests over all transitions including invalid ones; a two-device scripted scenario (both offline, both act on one cell, both reconnect) asserting exact final state; an attribution test on every transition.
10. **How demonstrated.** The core narrative beat: commander sees 12 unsearched cells; two teams work offline; on sync the map fills in, one cell shows a duplication flag with both teams named, and the outstanding count drops. This is PS-B4, PS-B5, PS-B7 and PS-B13 in one thirty-second sequence.
11. **Evidence it works.** The scripted two-device test with recorded before/after state; the state-machine test suite; a screenshot of the cell history showing team, responder, agency and timestamps.
12. **Honest limitations.** Two search-quality levels are not in Level 1 (L2-02), so "searched" is binary and cannot express a hasty vs thorough sweep — a real operational distinction. The duplication flag reports; it does not arbitrate.
13. **Production differences.** INSARAG-aligned marking vocabulary, per-technique search records, canine/technical search differentiation, structured re-search triggers, and doctrine-conformant terminology per agency.

---

### 3.4 · L1-04 — Offline-first field application core
*FR-401–404, FR-407–410, NFR-02, NFR-04, NFR-05, NFR-07, NFR-08 · Explicit: FR-401, FR-402*

**This is the largest and second-riskiest package. Alternatives compared first.**

| Approach | Offline durability | SMS + future peer transport | Dev speed | Verdict |
|---|---|---|---|---|
| **Native Android (Kotlin)** | Excellent | Full platform access | Slower | **Recommended.** SMS send/receive and any future peer transport need native APIs; a prototype that fights its platform on the one differentiating feature is a bad trade. |
| **Flutter** | Excellent | Via plugins; SMS plugins are uneven | Faster UI | Viable second choice if the team's existing skill is Flutter — but validate the SMS plugin in spike SP-01 before committing. |
| **PWA / web app** | Good (IndexedDB) | **Cannot send or receive SMS; cannot do peer transport** | Fastest | **Rejected.** It structurally cannot satisfy PS-K5. |

1. **Exact prototype capability.** Android app in which every core action — view assignment, change cell status, file a survivor report, adjust inventory — completes locally and instantly with all radios off, survives force-kill and reboot, queues into an outbox, and shows a persistent connectivity/last-sync/queued-count header. The three life-critical actions are each ≤3 taps with no typing.
2. **Recommended approach.** Local-first: the UI reads and writes only the local store; sync is a background concern the UI never waits on. A transactional embedded database with an outbox table. **No spinners on the critical path, ever** — a write that appears to succeed has succeeded, locally.
3. **Technical feasibility.** **Medium.** Every individual piece is routine; the difficulty is the discipline of never letting a network call reach the UI thread of a user action. This is where offline-first prototypes usually fail — they work offline in demo but block on some incidental fetch.
4. **Dependencies.** L1-08 (outbox and sync engine) is its other half; L1-01 (grid) for the offline map view; L1-02 (cached token).
5. **Platform limitations.** Background execution limits and OEM battery managers will kill background sync — accept it, sync opportunistically on foreground and on explicit action. GPS is slow to first fix and poor indoors (see L1-05). Storage is bounded but irrelevant at prototype volumes.
6. **External services / hardware.** ≥2 physical Android handsets. No services.
7. **Difficulty / risk.** **XL / Medium.**
8. **Failure modes.** A hidden network dependency on a critical path (the classic failure — mitigate with an airplane-mode test in CI-adjacent manual checks on every build); local store corruption on abrupt power loss (mitigate with transactional writes); outbox growth without bound; unclear UI state where the user cannot tell whether their action was recorded; permission prompts appearing at the worst moment.
9. **How tested.** **The defining test: enable airplane mode, perform the full task set, force-kill the app, reboot the device, confirm every record survives and the outbox is intact.** Run this on every build, manually, on a real device — it is the single most valuable test in the project. Plus tap-count assertions on the three critical actions, and a cold-start timing check.
10. **How demonstrated.** Hold up the phone, show airplane mode enabled, complete a full search-and-report cycle at normal speed, kill the app, reopen it, show the data still there and the queue holding. No narration needed — the audience understands immediately.
11. **Evidence it works.** A recorded airplane-mode run; the offline test checklist with dates; tap counts per action; the outbox contents before and after restart.
12. **Honest limitations.** Tested for **hours, not the 24 h of NFR-02** (§5.1). No sunlight-readability testing possible indoors (§5.4). One or two device models only — no device-matrix coverage, so OEM-specific failures are unknown. No dark mode, no Hindi, at Level 1.
13. **Production differences.** Device-matrix certification, battery instrumentation, ruggedised-device support, dark/night modes, full localisation, accessibility conformance, crash telemetry, and managed device deployment.

---

### 3.5 · L1-05 — Team position reporting
*FR-405 · Explicit*

1. **Exact prototype capability.** GPS captured on meaningful events only — cell entry/exit, status change, report filed, or a distance/time threshold; logged offline; forwarded on sync; displayed on the dashboard as last-known position **with its age**.
2. **Recommended approach.** Event-driven capture (PI-08), never streaming. This is a bandwidth decision as much as a battery one: continuous telemetry is impossible over SMS (§2.2).
3. **Technical feasibility.** **High** technically — but see limitations; the constraint is physics, not software.
4. **Dependencies.** L1-04 (offline logging), L1-08 (transport), L1-09 (display).
5. **Platform limitations.** Location permission flow including background-location restrictions on modern Android; slow first fix; **GPS accuracy inside rubble, in a collapsed structure, under canopy, or on a steep slope ranges from poor to unavailable.** No software fixes this.
6. **External services / hardware.** Device GNSS only. No geocoding service required.
7. **Difficulty / risk.** **S / Medium** — low effort, but the accuracy limitation is a credibility risk if overclaimed.
8. **Failure modes.** No fix indoors (mitigate: fall back to the responder's current cell as coarse position and label it as such); stale positions read as current (mitigate: FR-705 data age, non-negotiable); permission denied leaving teams invisible; battery drain from over-frequent capture.
9. **How tested.** Simulated location injection for repeatable route tests; a real walk test across several cells recording capture frequency and payload count; an offline capture-then-sync test.
10. **How demonstrated.** Walk a handset between two cells during the demo; the marker moves on the dashboard on sync, with its age shown.
11. **Evidence it works.** The walk-test log (fixes, accuracy figures, events emitted, bytes sent); a screenshot showing position age.
12. **Honest limitations.** **Positions are last-known, not live**, and inside a collapsed structure they may be absent or wrong by tens of metres. Cell-level position is the realistic granularity indoors. Say this explicitly rather than letting a moving dot imply live tracking.
13. **Production differences.** Fusion with inertial/dead-reckoning, indoor positioning, radio-based ranging, responder-safety geofencing, and breadcrumb trails for accountability.

---

### 3.6 · L1-06 — Survivor reporting
*FR-501 · Explicit*

1. **Exact prototype capability.** From a cell, a report in ≤3 taps: number of persons, status (trapped / accessible / extricated / deceased), optional triage category. Fully offline. Appears on the dashboard, attributed and timestamped. **Never lost in a merge.**
2. **Recommended approach.** Model as an additive event — union-merged, never overwritten. This is the single most important merge rule in the system and it should be stated as a product guarantee, not an implementation note.
3. **Technical feasibility.** **High.** Rides entirely on L1-04 and L1-08.
4. **Dependencies.** L1-04, L1-08, L1-01 (cell reference), L1-09 (display).
5. **Platform limitations.** None beyond L1-04's.
6. **External services / hardware.** None (no media at Level 1).
7. **Difficulty / risk.** **S / Low.**
8. **Failure modes.** Duplicate reports from two teams for the same survivors (**not merged at Level 1** — both shown, deduplication is L2; must be stated); a report filed against the wrong cell; over-simplified triage that a real responder would find inadequate.
9. **How tested.** Offline-file-then-sync test; a merge test asserting that two offline reports on one cell both survive reunion; a tap-count assertion.
10. **How demonstrated.** Offline handset files a survivor report; on reconnect it appears on the commander's map within seconds, with team attribution and timestamp.
11. **Evidence it works.** The merge test output showing both reports preserved; the recorded offline-to-dashboard sequence with timings.
12. **Honest limitations.** No photos, no voice notes, no medical detail, no duplicate merging, no lifecycle beyond the initial status. Triage categories are simplified and have not been reviewed by a medical or SAR professional — **this must not be presented as a clinically validated triage tool.**
13. **Production differences.** Clinically reviewed triage vocabulary, media capture with bandwidth-aware upload, hospital and ambulance handover integration, next-of-kin workflows, and legally compliant retention and access control.

---

### 3.7 · L1-07 — Resource inventory
*FR-601, FR-602, FR-603, FR-606 · Explicit: FR-601–603*

1. **Exact prototype capability.** Each team holds a short list of items with quantities in two categories (equipment; medical supplies); a responder decrements a quantity offline in two taps; the dashboard shows per-team remaining and an incident total.
2. **Recommended approach.** Model consumption as **delta events** (`−2 units`), not absolute quantity writes. Deltas commute, so two offline decrements from different responders sum correctly instead of overwriting each other — a small decision that removes the entire class of inventory merge conflicts.
3. **Technical feasibility.** **High.** The simplest Level-1 package.
4. **Dependencies.** L1-02, L1-04, L1-08.
5. **Platform limitations.** None.
6. **External services / hardware.** None. No barcode or RFID.
7. **Difficulty / risk.** **S / Low.**
8. **Failure modes.** Quantities drifting negative from concurrent decrements (allow it, flag it — a negative reading is information, not a bug to hide); items missing from a fixed catalogue; nobody updating inventory under stress, which is a behavioural failure no software prevents.
9. **How tested.** A commutativity test: two offline devices each decrement the same item, reunite, assert the arithmetic. Plus an offline update-and-sync test.
10. **How demonstrated.** Two offline responders each consume from one stock; on sync the dashboard shows the correct combined remainder — a quiet but genuinely convincing merge demonstration.
11. **Evidence it works.** The commutativity test output; the dashboard before/after figures.
12. **Honest limitations.** A fixed item catalogue, no requests, no transfers, no low-stock alerts, no supply points as entities, no reconciliation against physical stock. Accuracy depends entirely on responders remembering to record consumption — **the prototype tracks what is reported, not what is real.**
13. **Production differences.** Barcode/RFID capture, depot and logistics integration, procurement and resupply workflows, consumption forecasting, and audited stock reconciliation.

---

### 3.8 · L1-08 — Sync engine, SMS transport and merge policy
*FR-801, FR-802 (deltas), FR-803, FR-806, FR-807, FR-1001, FR-1002, NFR-01, NFR-03, NFR-14, NFR-15 · Explicit: FR-801–803*

**The differentiating package and the highest-risk one.** Transport choice is settled in §2; this section covers the engine.

**Merge policy alternatives compared:**

| Approach | Correctness | Complexity | Verdict |
|---|---|---|---|
| Last-writer-wins per record | Poor — can erase a survivor report | Trivial | **Rejected.** Fails the domain outright. |
| **Event log + additive union for reports/observations, single stated rule for mutable state, flag residual conflicts** | Good, and explainable in one page | Moderate | **Recommended.** Correct where correctness matters, simple where it does not. |
| Full CRDT semantics | Excellent | High | **Rejected for prototype** — weeks of work for correctness the demo cannot show. Level 3. |

1. **Exact prototype capability.** Local writes always succeed; transmission is asynchronous, resumable and de-duplicated. Events carry id, actor, team, agency, device time and server receipt time. SMS path: events bit-packed, batched, segmented, sent handset → gateway handset → server, with acknowledgement and retry. Merge: additive records union-merge and can never be lost; mutable state resolves by one stated rule with contradictions flagged. Store-and-forward gossip so any device can carry another's events (§2.4). Bytes-per-update measured and published.
2. **Recommended approach.** Event-log-first, transport-agnostic interface, as required by §2.6. Build the loopback transport before the SMS transport so the engine is fully testable before any radio is involved.
3. **Technical feasibility.** **Medium.** The engine logic is well-understood; the SMS codec and carrier behaviour carry the unknowns (spike SP-01).
4. **Dependencies.** Everything downstream of it. **It must start in week 1** despite not being demonstrable until other packages exist — the most common way this project could fail is leaving sync until the features are "done".
5. **Platform limitations.** As §2.2: SMS permissions, the ~30/30 min outgoing throttle forcing batching, uncertain binary-SMS carrier support, ~117–140 usable bytes per segment, no ordering guarantee, and delivery latency outside our control.
6. **External services / hardware.** 2 SIMs with SMS credit; a gateway handset with a data connection at the "command post". No provider, no DLT registration, no cloud dependency.
7. **Difficulty / risk.** **XL / High.**
8. **Failure modes.** Carrier silently dropping binary SMS (→ SP-01, fallback to GSM-7 text); the outgoing throttle interrupting a burst mid-demo (→ batching plus a pre-demo queue drain); segment loss producing partial batches (→ per-batch integrity check and retry); clock skew misordering events (→ order by server receipt time at Level 1, and **state the limitation**); duplicate delivery (→ event-id dedupe); an unbounded outbox after a long offline period; the gateway handset dying or losing data mid-demo (→ a spare, charged, pre-paired).
9. **How tested.** The engine's value is that it is *provably* testable: in-process multi-node convergence tests over the loopback transport — partition two nodes, diverge them, reunite, assert identical converged state; out-of-order and duplicate delivery tests; a dropped-message test; codec round-trip and size-budget tests asserting every event type fits the byte budget (NFR-01). Separately, a manual real-SMS matrix: send/receive, batch, retry, throttle behaviour.
10. **How demonstrated.** The EC-01 centrepiece, in three beats: (a) mobile data **off** on the field handset; (b) a responder marks a cell searched and files a survivor report; (c) the update lands on the dashboard, with the SMS payload and its byte count shown on screen. Then the harder beat: kill the server, show the field app still fully working, restart it, watch the queue drain.
11. **Evidence it works.** Convergence test suite output; measured bytes per event type against NFR-01; carrier delivery timestamps; a recorded partition/reunite run; the one-page merge policy note (NFR-14).
12. **Honest limitations.** **Ordering depends on server receipt time, not true causality** — two events created offline in a known order may be recorded out of order, and clock-skew correction is Level 2. No compression tuning. No priority queueing at Level 1. No storage eviction. Real-SMS testing covers one or two carriers, a handful of runs — **enough to prove the mechanism works, nowhere near enough to characterise reliability** (§6).
13. **Production differences.** Hybrid logical clocks for true causal ordering, CRDT merge semantics, log compaction and snapshotting, priority queueing, multi-transport fallback, per-item telemetry, carrier-diverse testing, and formal delivery-guarantee characterisation.

---

### 3.9 · L1-09 — Commander dashboard (shared operational picture)
*FR-701–FR-705 · Explicit: FR-701, FR-702*

1. **Exact prototype capability.** Online, server-backed web dashboard (per D-01). One map layering grid-status colour, team markers and survivor markers; a metrics strip (% searched, cells outstanding, teams active, survivors reported, critical resources); filter/colour by agency; **data age visible on every team marker and cell**; assignment performed here.
2. **Recommended approach.** A web map library with canvas/WebGL rendering for thousands of cells, fed by a simple polling or streaming update from the server. Polling at a few seconds satisfies NFR-03 and removes a whole class of connection-management work — **choose polling unless streaming proves necessary.**
3. **Technical feasibility.** **High.** D-01 removed the genuinely hard version of this package.
4. **Dependencies.** L1-01, L1-02, L1-03, L1-05, L1-06, L1-07, L1-08. It is the last package to become fully meaningful, which makes it a scheduling risk.
5. **Platform limitations.** Rendering several thousand cell polygons plus markers needs WebGL-backed rendering; naive DOM markers will stutter and a stuttering dashboard reads as a broken product in a demo.
6. **External services / hardware.** Basemap tiles (a hosted open source is fine for an online dashboard); a projector-friendly display. Verify the venue projector's resolution and colour rendering beforehand — status colours that separate on a laptop can collapse on a dim projector.
7. **Difficulty / risk.** **L / Low.**
8. **Failure modes.** Visual overload once every layer is on (mitigate: a deliberate default view with layers off); colour choices that fail for colour-blind judges (mitigate: colour **plus** pattern/shape, per FR-408's principle); stale data rendered as current (mitigate: FR-705 — the single most important element on the screen); performance collapse at high cell counts.
9. **How tested.** A synthetic-load render test at 5,000 cells / 200 teams (this is also the NFR-09 substitute, §5.5); a data-age display test with artificially aged records; a cross-browser check; a colour-blind simulation pass.
10. **How demonstrated.** The EC-02 set piece: the commander answers MC-09's three questions out loud in under thirty seconds — *which cells are unsearched?* · *who searched B-14 and when?* · *what remains and where are the survivors?* — while pointing at one screen.
11. **Evidence it works.** The 30-second three-question run, recorded; the synthetic-load render timings; screenshots showing data age on every marker.
12. **Honest limitations.** **Requires connectivity — it does not work offline (D-01).** No alert feed, no timeline/replay, no export, no multi-incident view. Tested with synthetic data at a single incident scale, on a desktop browser, by people who built it — not by an incident commander under stress.
13. **Production differences.** Offline/edge deployment (FE-01), alerting and escalation, timeline reconstruction and after-action analytics, multi-incident and authority-level rollup, role-tailored views, and validation with real incident commanders.

---

### 3.10 · L1-10 — Interoperability layer
*FR-901, FR-902, FR-903, FR-905 (export), NFR-16 (reduced) · Explicit: FR-901–903*

1. **Exact prototype capability.** A written common information model; a documented REST API under a version prefix, authenticated by a static API key, allowing an external system to read the operational picture and contribute to it; a live demonstration of a second and third agency joining a running incident; GeoJSON/CSV export of grid status and survivor reports.
2. **Recommended approach.** Write the information model **before** the API, and generate the documentation from the served schema so the two cannot drift. Build a small mock "partner agency client" as a demo artefact — this is what converts an API claim into visible evidence.
3. **Technical feasibility.** **High.** The work is discipline and documentation more than engineering.
4. **Dependencies.** L1-02 (agencies, join flow), and the data model everything else uses.
5. **Platform limitations.** None.
6. **External services / hardware.** None. The "external agency system" is a mock client we write.
7. **Difficulty / risk.** **M / Low.**
8. **Failure modes.** Documentation drifting from the implementation (mitigate: generate from schema); interoperability shown only as multiple logins, which does **not** evidence EC-04; an API shaped around our UI rather than around the domain, which a knowledgeable judge will notice.
9. **How tested.** Contract tests against the published schema; a round-trip test (external client writes a survivor report → it appears in the dashboard → it exports to GeoJSON); an export-format validation.
10. **How demonstrated.** Two beats: a volunteer agency joining by code in under a minute (human interoperability), then the mock partner system pushing a survivor report from outside the platform and it appearing in the shared picture (system interoperability). Then hand over a GeoJSON export.
11. **Evidence it works.** The API documentation; the mock-client round-trip recording; a valid GeoJSON export opened in third-party GIS software — that last one is disproportionately convincing.
12. **Honest limitations.** **No real external agency system has been integrated** — the partner is a mock we control (§5.6). No CAP/EDXL conformance, no federation, no per-agency scoping, no terminology mapping, no versioning guarantees. A static API key is not credential management.
13. **Production differences.** Standards conformance (FE-03), federated multi-instance operation (FE-02), per-agency data-sharing agreements enforced technically, credential lifecycle management, rate limiting, and conformance testing with actual agency systems.

---

### 3.11 · L1-11 — Evidence and measurement
*NFR-01, NFR-03, NFR-04, NFR-14 · serves EC-01–EC-04*

1. **Exact prototype capability.** Recorded bytes-per-update per event type per transport; measured propagation latency when connected; an informal usability run with 3–5 first-time users (tap counts, time-to-complete, completion rate) with raw numbers written down; a one-page consistency-and-merge note; four demo scripts, one per evaluation criterion, each runnable live **and** in simulated-network form.
2. **Recommended approach.** Instrument as you build, not at the end. Keep an `docs/evidence/` folder that accumulates measurements with dates — it doubles as the submission appendix.
3. **Technical feasibility.** **High.** Nothing here is technically hard.
4. **Dependencies.** All other packages. Usability runs need people outside the team — recruit them in week 3, not week 6.
5. **Platform limitations.** None.
6. **External services / hardware.** 3–5 people who have never seen the app; a stopwatch; screen recording.
7. **Difficulty / risk.** **M / Medium** — the risk is purely organisational: this is the first thing dropped under deadline pressure, and dropping it forfeits the evidence for three of four scored criteria.
8. **Failure modes.** Measurements taken once, late, and unrepeatably; usability run conducted on teammates (worthless — they know the app); demo scripts written the night before and never rehearsed under failure conditions.
9. **How tested.** The measurements *are* the tests. Each demo script is rehearsed at least twice, including once with the network deliberately broken.
10. **How demonstrated.** Numbers on slides, and the four rehearsed scenarios.
11. **Evidence it works.** The evidence folder itself: byte tables, latency figures, usability results with raw per-participant data, the merge note, and rehearsal recordings.
12. **Honest limitations.** 3–5 participants is an indication, not a study. Measurements come from one or two devices, one or two carriers, one venue. **Report the numbers with their sample size attached, every time** (§6).
13. **Production differences.** Formal usability studies with real responders, load and soak testing, carrier-diverse field trials, and independent verification.

---

## 4. Relevant Level-2 packages

Only the ones that affect Level-1 decisions or carry disproportionate evaluation value.

### 4.1 · L2-01 — Phone-to-phone sync *(the promotion candidate)*
- **Capability.** Two co-located handsets, both with no connectivity of any kind, exchange events directly; one later relays to the server.
- **Approach.** Prefer variant **2c** (local-only hotspot + plain HTTP) for reliability and testability, or **2a** (Nearby Connections) for a better story. Decide only after spike SP-02 on the actual demo devices.
- **Feasibility.** Medium (2c) / Medium–Low (2a). **Only if §2.6's transport-agnostic condition was honoured** — then it is an adapter, ~3–4 dev-days. Otherwise it is a rewrite.
- **Dependencies / platform.** Play Services (2a); permission churn across Android versions; no emulator support; OEM battery managers.
- **Risk.** Medium–High, concentrated on demo day in a congested RF venue (§2.3).
- **Failure modes.** Discovery timeout in front of judges — with **no recovery narrative** unless SMS is already the primary path, which is exactly why §2.6 recommends what it does.
- **Testing / demo / evidence.** Two-device manual matrix; the visceral both-phones-offline demo; connection and convergence logs.
- **Honest limitations.** Single-hop; tens of metres; a handful of peers; not a mesh network and must not be called one.
- **Production differences.** True multi-hop mesh, radio bridging for range (FE-04), and routing under mobility.

### 4.2 · L2-06 — Sync robustness refinements
- **Capability.** Two-tier priority (life-critical before routine); per-item queued/sent/acked badge; clock-skew handling.
- **Why it matters to Level 1.** Priority ordering becomes materially important the moment the SMS throttle bites (§2.2) — if the queue is full of position updates when a survivor report is filed, the demo tells the wrong story. **Consider promoting the two-tier priority alone into Level 1**; it is ~1 dev-day and directly protects the EC-01 narrative. Flagged as decision 3 in §10.
- **Feasibility.** High. **Difficulty.** S–M.

### 4.3 · L2-07 — Conflict presentation
- **Capability.** A filtered list of flagged cells showing both claims with a one-click resolution.
- **Feasibility.** High, ~2 dev-days, given the Level-1 flagging already exists. Meaningfully strengthens EC-02 by turning a flag into a resolution workflow.

### 4.4 · L2-08 — Field app polish
- **Capability.** Dark mode, SOS, Hindi strings, one pre-cached basemap tile pack.
- **Note.** The **basemap tile pack** is the highest-value item here for EC-03: a schematic grid is functional but a real map under the grid changes how credible the field app looks. ~2 dev-days with a pre-generated tile pack for the demo area.

### 4.5 · L2-10 — After-action summary
- **Capability.** End-of-incident summary: coverage %, timeline, survivors located, resources consumed.
- **Note.** This is the artefact that **quantifies PS-B12 and PS-B13** — the statement's two success outcomes. Roughly 2 dev-days for a strong closing slide. The highest evaluation-value item on the Level-2 list after L2-01.

---

## 5. Requirements that cannot realistically be demonstrated

Stated openly, each with the minimum credible substitute. **The substitute is what we claim; the original requirement is not claimed as proven.**

### 5.1 NFR-02 — 24-hour offline endurance
- **Why not demonstrable.** A 24-hour test cannot be run repeatedly inside a 5–6 week build, and cannot be shown in an 8-minute demo.
- **Minimum credible substitute.** One recorded **60–90 minute continuous offline session** with a realistic action volume, plus an inspection-based argument: there is no time-based expiry, no TTL and no session timeout anywhere in the offline path, and the outbox is bounded only by storage. Plus one **overnight offline soak** run once, unattended, with the result reported as a single observation.
- **What we may claim.** "Offline operation demonstrated for 90 minutes and soaked overnight once; no time-based limit exists by design." **Not** "24-hour offline endurance verified."

### 5.2 Disaster-grade reliability (any claim of field survivability)
- **Why not demonstrable.** No disaster site, no dust, no heat, no dropped phones, no panicking users, no real casualties, no multi-day operation. No prototype test produces this evidence.
- **Minimum credible substitute.** None. **This claim is simply not made** — see §6.

### 5.3 FR-303 — offline duplicate *assignment* collision
- **Why not demonstrable.** D-01 made the dashboard online-only, so two commanders cannot realistically create conflicting assignments offline. The scenario is now largely prevented by construction rather than resolved by merging.
- **Minimum credible substitute — and a better one.** Demonstrate **duplicate search effort**, which is what PS-B4 actually describes: two offline teams both search cell B-14; on reunion both search events survive, the cell shows two searching teams from two agencies, and the commander sees the duplication flagged. This is more faithful to the problem statement than the original framing and is fully demonstrable. **Requires your decision** (§10, decision 2).

### 5.4 NFR-05 — sunlight readability and glove operation
- **Why not demonstrable.** No sunlight indoors; no meaningful way to test readability at a venue.
- **Minimum credible substitute.** A measured contrast-ratio audit against WCAG AA, a touch-target size audit against 48 dp, and **one recorded run of the three critical actions performed wearing actual work gloves**. Claim the audit and the glove run; do not claim sunlight readability.

### 5.5 NFR-09 — scale (200 responders / 5,000 cells / 20 teams)
- **Why not demonstrable.** No 200 real devices, no 200 people.
- **Minimum credible substitute.** A **synthetic load**: 5,000 cells generated and rendered with measured frame timings, and 200 simulated teams driven through the API producing realistic event volume. This tests the dashboard and server under volume; it does **not** test 200 concurrent real devices, real radios or real humans. State both halves.

### 5.6 EC-04 — interoperability with a real external agency system
- **Why not demonstrable.** No NDRF, fire-service or police system is available to integrate with.
- **Minimum credible substitute.** A **mock partner client** we write against the published API, performing a genuine round trip, plus a GeoJSON export opened in third-party GIS software. Claim "an external system can integrate against a documented, working API, demonstrated with a mock partner." Do **not** claim integration with any named agency.

### 5.7 NFR-10 — 8-hour battery endurance
- **Why not demonstrable.** Repeated 8-hour drain tests do not fit the schedule.
- **Minimum credible substitute.** A 60-minute measured drain under representative use, reported **as an extrapolation with the measurement window stated**. Never quote the extrapolated figure alone.

### 5.8 NFR-03 — latency over the SMS path across carriers
- **Why not demonstrable.** One or two SIMs, one or two carriers, one geography, a handful of runs.
- **Minimum credible substitute.** Report the **observed range and sample size** ("6–40 s across 20 sends on two carriers"), never a single headline figure and never an SLA-shaped claim.

### 5.9 NFR-04 — 90% task completion by untrained responders
- **Why not demonstrable.** 3–5 participants cannot establish a 90% figure.
- **Minimum credible substitute.** Report **raw per-participant results** with the sample size attached: "4 of 5 first-time users completed all three critical actions unaided; median time 22 s." No percentages generalised from five people.

---

## 6. Reliability claim discipline

Per your instruction, no disaster-grade reliability is promised. The prototype can prove **mechanism**; it cannot prove **endurance, scale or field survivability**.

| We may say | We may not say |
|---|---|
| "Field data entry works with all radios disabled — demonstrated, recorded, and re-verified on every build." | "Works reliably in disaster conditions." |
| "Updates propagated over SMS with mobile data disabled; 94 bytes, 6–40 s across 20 sends on two carriers." | "Guaranteed delivery" / any SLA-shaped claim. |
| "Two devices diverged offline and converged deterministically; proven by automated convergence tests." | "Consistent under all network partitions." |
| "No survivor report was lost in any merge test we ran." | "Survivor reports can never be lost." |
| "Offline operation demonstrated for 90 minutes, soaked overnight once; no time-based limit by design." | "24-hour offline endurance." |
| "4 of 5 first-time users completed the critical actions unaided." | "90% task completion for untrained responders." |
| "An external system integrated against the documented API (mock partner)." | "Interoperable with NDRF/fire/police systems." |
| "Rendered 5,000 cells and 200 simulated teams within X ms." | "Scales to 200 responders." |

**Standing rule:** every quantitative claim carries its sample size and its conditions in the same sentence. A judge who finds one overclaim discounts everything else — including the parts that are genuinely strong.

---

## 7. Risk register

| ID | Risk | P × I | Mitigation | Owner decision needed |
|---|---|---|---|---|
| R-01 | Carrier drops binary/port-addressed SMS | Med × High | **Spike SP-01 in week 1**; fallback to GSM-7 text packing (~117 B/segment) | No |
| R-02 | Android outgoing-SMS throttle interrupts the demo | Med × High | Batch events per message; drain the queue before the demo; keep demo event volume low | No |
| R-03 | Sync engine started late and never becomes demonstrable | Med × **Critical** | Start L1-08 in week 1 with the loopback transport, before any UI feature is "finished" | No |
| R-04 | A hidden network dependency breaks the offline demo | Med × High | Airplane-mode test on **every build**, on a real device, as a standing checklist item | No |
| R-05 | Evidence and measurement (L1-11) dropped under deadline pressure | **High** × High | Instrument as you build; book usability participants in week 3 | No |
| R-06 | Dashboard becomes meaningful only in the final week, leaving no time to fix its clarity | Med × Med | Build it against synthetic data from week 2, before real data flows | No |
| R-07 | Gateway handset fails on demo day (battery, SIM, data) | Low × **Critical** | A second charged, pre-paired gateway handset; a rehearsed simulated-transport fallback | No |
| R-08 | Venue forbids or blocks live SMS | Low × High | Pre-record the live SMS run **with the byte counts visible**, and keep the simulated transport as the live fallback (AMB-19) | No |
| R-09 | Peer sync (L2-01) attempted and fails publicly | Med × Med | Keep it Level 2; demo it only if it passes rehearsal twice in the venue | Decision 4 |
| R-10 | GPS unusable in the demo location, making positions look broken | Med × Med | Cell-level position fallback, labelled as such; rehearse indoors | No |
| R-11 | Triage/SAR vocabulary criticised as unrealistic by a domain-expert judge | Med × Med | State plainly that vocabulary is unvalidated and cite INSARAG alignment as future work | No |

---

## 8. De-risking spikes (do these first, before committing)

| ID | Spike | Question it answers | Time-box | Blocks |
|---|---|---|---|---|
| **SP-01** | Send a port-addressed binary SMS between two handsets on the target carriers; measure delivery, latency and usable payload; probe the outgoing throttle | Is binary SMS viable, or is GSM-7 text packing required? What is the real throttle behaviour? | 1 day | L1-08 codec design; **the whole D-02 decision rests on this** |
| **SP-02** | Nearby Connections / local-only hotspot between the two actual demo devices, in a congested RF setting | Which peer-sync variant is realistic, and is L2-01 promotable? | 1 day | L2-01 |
| **SP-03** | Render 5,000 cell polygons + 200 markers in the chosen web map library | Does the dashboard survive the NFR-09 synthetic load? | 0.5 day | L1-09 rendering approach |
| **SP-04** | Offline write → force-kill → reboot → verify, on the chosen mobile stack | Does the local store survive abrupt termination? | 0.5 day | L1-04 stack choice |

**SP-01 should run before anything else is committed.** If binary SMS is unavailable *and* the throttle proves tighter than expected, the transport recommendation in §2.6 must be revisited — that is precisely what a spike is for.

---

## 9. Effort estimate and build order

Developer-days, per AS-01. Estimates carry normal prototype uncertainty (±30%).

| Order | Package | Dev-days | Why this position |
|---|---|---|---|
| 0 | SP-01…SP-04 spikes | 3 | Answers the questions that could invalidate the plan |
| 1 | L1-08 engine (loopback transport, event log, merge) | 8 | Everything depends on it; must not be deferred |
| 2 | L1-01 grid + L1-02 agencies/teams/joining | 7 | Foundation for all data |
| 3 | L1-04 field app core | 12 | Largest package; start early, iterate |
| 4 | L1-03 allocation and status | 6 | The statement's core, on top of the foundation |
| 5 | L1-06 survivor + L1-07 inventory + L1-05 position | 5 | Cheap once L1-04 and L1-08 exist |
| 6 | L1-08 SMS transport + gateway | 7 | After SP-01; engine already proven on loopback |
| 7 | L1-09 dashboard | 9 | Start against synthetic data in parallel from week 2 |
| 8 | L1-10 interoperability + mock partner | 5 | Mostly discipline and documentation |
| 9 | L1-11 evidence, measurement, demo rehearsal | 5 | Continuous, not final — but reserve the days |
| | **Level 1 total** | **~67 dev-days** | ≈ 4.5 weeks at 3.5 developers, with no slack |
| | Level 2 candidates (L2-06 priority 1, L2-07 2, L2-08 2, L2-10 2, L2-01 4) | ~11 | Only after Level 1 is verified |

**The schedule has no slack.** If it compresses, cut in this order: L2 items → L1-05 richness → L1-10's mock partner (keep the API and docs) → **never** L1-08, L1-04 or L1-11.

---

## 10. Decisions requested

| # | Decision | Recommendation | Consequence |
|---|---|---|---|
| 1 | **D-02-REVISED** — SMS is the mandatory Level-1 fallback; phone-to-phone moves to Level 2; store-and-forward gossip is built at Level 1 (§2.6). | **Approve**, conditional on spike SP-01. | Settles PS-K5. If SP-01 fails, §2.6 is revisited on evidence. |
| 2 | **Reframe the FR-303 demonstration** from duplicate *assignment* to duplicate *search effort* (§5.3). | **Approve** — it is more faithful to PS-B4 and it is demonstrable. | Changes one demo script; no scope change. |
| 3 | **Promote two-tier transmission priority** (part of L2-06) into Level 1, ~1 dev-day (§4.2). | **Approve** — it protects the EC-01 narrative once the SMS throttle bites. | +1 dev-day. |
| 4 | Whether to attempt **L2-01 peer sync in the live demo** if it is built. | **Only if it passes rehearsal twice in the venue**; otherwise show it recorded. | Avoids R-09. |
| 5 | Confirm **AS-02** — 2 physical Android handsets and 2 SMS-capable SIMs are actually available. | Confirm now. | Without them the entire PS-K5 demonstration falls back to simulation (§5, AMB-19). |

On approval, the next deliverable is the **system architecture and data model for the Level-1 scope only**, incorporating the transport-agnostic constraint from §2.6 as a first-class design input.
