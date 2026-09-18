# RescueNet AI — Android Field Application

**Milestones:** M6–M9 (engine), M12 (UI). **Not implemented yet** — this is the M0 directory skeleton only.

## Status: build files are NOT present, deliberately

Android Studio, the Android SDK, Gradle and Kotlin are **not installed on this machine**
(blocker B-3 in docs/12 §7; TR-01 since docs/07). No Gradle project has been hand-written,
because build files that cannot be compiled or run would be unverified artefacts.

**The Gradle project is generated at M6**, once Android Studio is installed:
package `ai.rescuenet.field`, native Kotlin (T-01/T-02), Room (T-03).

## Package layout (created, empty)

| Package | Purpose | Milestone |
|---|---|---|
| `domain/` | Event model mirroring the backend's semantics | M6 |
| `store/` | Room — event log + outbox, single-transaction write (AD-10) | M6 |
| `sync/` | Outbox engine, transport interface, watermarks | M7 |
| `transport/` | `InternetTransport`, `SmsTransport` | M7/M8 |
| `codec/` | **ALL** wire and SMS knowledge lives here and nowhere else (AD-07) | M8 |
| `gateway/` | Gateway mode — same APK, relays without authoring (AP-16) | M9 |
| `ui/` | Field screens — **built LAST**, after the engine works | M12 |

## Standing constraints

- The app **must work fully offline** (FR-402). No network call on any critical path.
- **`(device_id, seq)`** is event identity (D-05), allocated locally inside the write transaction.
- **`REJECTED`** is an outbox delivery state — it never deletes the domain event (AP-14, DM-39).
- SMS knowledge must not leak above the transport interface (AD-07).

## SMS status — do not overstate

Programmatic Android SMS is **not validated** (spike SP-01b-A is open). The manual test
established only that generated GSM-7 payloads were transmitted unaltered between the two
tested handset/SIM routes in both directions, and that payloads up to 459 characters
arrived intact. **Segment counts were not observed. Carrier identities were not recorded.
The application does not send SMS.**
