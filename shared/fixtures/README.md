# Canonical Test Fixtures — single source, no drift

**This directory is the ONLY home for canonical event fixtures.**

Per docs/12 §3, these files are consumed by **all three** test suites:

| Suite | Consumes from | Milestone |
|---|---|---|
| pytest (backend) | `shared/fixtures/` | M2+ |
| JUnit5 (Android) | `shared/fixtures/` | M6+ |
| Vitest (dashboard) | `shared/fixtures/` | M11+ |

## The rule

**Do not create independent copies.** Three separately-written fixture sets would drift;
one cannot. This directly mitigates audit finding F-13 (docs/10 §10).

If a fixture needs to change, it changes **here**, and every suite sees the change at once.
A suite that needs a variant derives it from a canonical fixture at runtime — it does not
fork the file.

## Contents

**Currently empty.** Population is **M2** (canonical event model), not M0.

At M2 this directory receives the approved examples from **docs/08 Part 16**, verbatim:
search effort · team status · assignment · survivor report · resource update ·
duplicate-search scenario · offline event becoming synced · SMS-batched representation.

Every fixture must conform exactly to the canonical event schema in **docs/08 Part 1**.
No fixture may introduce a field that schema does not define.
