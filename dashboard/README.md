# RescueNet AI — Commander Dashboard

**Milestone:** M11 (docs/12). **Not implemented yet** — this is the M0 skeleton only.

**Online-only by decision D-01.** No local store, no offline cache, no edge server.

| Directory | Purpose | Milestone |
|---|---|---|
| `src/api/` | REST client — snapshot, delta, assignments | M11 |
| `src/mqtt/` | `mqtt.js` subscriber + `server_seq` gap detection (AD-16/AD-17) | M11 |
| `src/map/` | MapLibre grid rendering, colour **plus** pattern (FR-304) | M11 |
| `src/views/` | Metrics strip, cell detail, duplicate-search view | M11 |

**Contract reminders (docs/09):**
- MQTT is **notification-only**. The dashboard credential is **subscribe-only** (AP-10) and cannot publish.
- On a `server_seq` gap → REST delta recovery (§4.5). MQTT loss costs latency, never correctness.
- `CoverageMetrics` comes from the server (AP-24). The dashboard **never** computes it.
- Broker down → show "live updates offline", never stale-as-fresh.

Dependencies are **not installed**. `npm install` runs at M11.
