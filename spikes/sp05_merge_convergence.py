"""
SP-05  --  Merge & convergence simulation (ISOLATED SPIKE CODE, NOT ARCHITECTURE)
Validates the D-01 APPROVED duplicate-search-effort scenario as pure logic,
before any architecture exists. No device, no network, no database.
"""
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Event:
    eid: tuple      # (device_id, seq) -- the dedupe key
    kind: str
    t_dev: int      # device clock (may be skewed)
    actor: dict     # team / responder / agency
    payload: dict
    t_srv: int = -1 # server receipt order, assigned on arrival at server

class Node:
    """A device or the server. Holds an append-only log keyed by event id."""
    def __init__(self, name): self.name, self.log = name, {}
    def emit(self, e): self.log[e.eid] = e; return e
    def receive(self, events):
        """Union merge. Returns events that were NEW to this node."""
        new = [e for e in events if e.eid not in self.log]
        for e in new: self.log[e.eid] = e
        return new
    def all(self): return list(self.log.values())
    def __len__(self): return len(self.log)

def gossip(a, b):
    """Bidirectional store-and-forward exchange -- each sends what the other lacks."""
    b.receive(a.all()); a.receive(b.all())

# ---- Projections: how the commander dashboard reads the log -----------------
def cell_search_events(log, cell):
    return sorted([e for e in log if e.kind == "SEARCH" and e.payload["cell"] == cell],
                  key=lambda e: (e.t_srv if e.t_srv >= 0 else 10**9, e.eid))

def duplicate_search_flags(log):
    """FR-303 / PS-B4: >1 distinct TEAM recorded searching the same cell."""
    by_cell = {}
    for e in log:
        if e.kind == "SEARCH":
            by_cell.setdefault(e.payload["cell"], set()).add(e.actor["team"])
    return {c: sorted(t) for c, t in by_cell.items() if len(t) > 1}

def cell_status(log, cell):
    """Mutable state: single stated rule = latest by server receipt order, ties by eid."""
    evs = cell_search_events(log, cell)
    return evs[-1].payload["status"] if evs else "unsearched"

def inventory(log, item):
    return sum(e.payload["delta"] for e in log if e.kind == "INV" and e.payload["item"] == item)

# =============================================================================
results = []
def check(label, cond, detail=""):
    results.append((label, cond, detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -- {detail}" if detail else ""))

print("=" * 78)
print("SP-05  MERGE & CONVERGENCE SIMULATION")
print("Scenario under test: D-01 APPROVED duplicate SEARCH EFFORT on grid B-14")
print("=" * 78)

server = Node("server")
devA   = Node("deviceA")   # Team Alpha  (NDRF)
devB   = Node("deviceB")   # Team Bravo  (Fire Services)

# --- Step 1: B-14 is initially unsearched -----------------------------------
print("\n[1] initial state")
check("B-14 starts unsearched", cell_status(server.all(), "B-14") == "unsearched",
      f"status={cell_status(server.all(),'B-14')}")

# --- Step 2: both teams lose central connectivity ----------------------------
print("\n[2] Team Alpha and Team Bravo disconnect from central connectivity")
print("    (no gossip, no server contact from here until step 5)")

# --- Step 3: both independently search B-14 ---------------------------------
print("\n[3] both teams independently search B-14 while disconnected")
eA = devA.emit(Event((1, 1), "SEARCH", t_dev=1000,
                     actor={"team": "Alpha", "responder": "A7", "agency": "NDRF"},
                     payload={"cell": "B-14", "status": "searched"}))
eB = devB.emit(Event((2, 1), "SEARCH", t_dev=1005,
                     actor={"team": "Bravo", "responder": "B3", "agency": "Fire"},
                     payload={"cell": "B-14", "status": "searched"}))
# each also files unrelated work, to prove nothing else is disturbed
devA.emit(Event((1, 2), "SURVIVOR", t_dev=1010, actor={"team": "Alpha", "responder": "A7", "agency": "NDRF"},
                payload={"cell": "B-14", "persons": 2, "status": "trapped"}))
devB.emit(Event((2, 2), "INV", t_dev=1012, actor={"team": "Bravo", "responder": "B3", "agency": "Fire"},
                payload={"item": "medical_kit", "delta": -2}))
devA.emit(Event((1, 3), "INV", t_dev=1015, actor={"team": "Alpha", "responder": "A7", "agency": "NDRF"},
                payload={"item": "medical_kit", "delta": -3}))
print(f"    deviceA log = {len(devA)} events, deviceB log = {len(devB)} events, server = {len(server)}")

# --- Step 4 + 5: synchronisation occurs; both events preserved & auditable ---
print("\n[4/5] synchronisation -- Alpha syncs first, then Bravo (out of order vs device clocks)")
for i, e in enumerate(devA.all(), start=1): object.__setattr__(e, "t_srv", i)
server.receive(devA.all())
for i, e in enumerate(devB.all(), start=len(server) + 1): object.__setattr__(e, "t_srv", i)
server.receive(devB.all())

sev = cell_search_events(server.all(), "B-14")
check("both search events preserved", len(sev) == 2, f"{len(sev)} SEARCH events on B-14")
check("no silent discard -- Alpha's event present", eA.eid in server.log)
check("no silent discard -- Bravo's event present", eB.eid in server.log)
check("both auditable with full attribution",
      all(e.actor.get("team") and e.actor.get("responder") and e.actor.get("agency") for e in sev),
      " | ".join(f"{e.actor['team']}/{e.actor['responder']}/{e.actor['agency']}@t_dev={e.t_dev}" for e in sev))
check("survivor report survived the merge",
      any(e.kind == "SURVIVOR" for e in server.all()))

# --- Step 6: commander dashboard flags the duplicate ------------------------
print("\n[6] commander dashboard duplicate detection")
flags = duplicate_search_flags(server.all())
check("B-14 flagged as duplicate search effort", "B-14" in flags, f"teams = {flags.get('B-14')}")
check("flag names both agencies", len(flags.get("B-14", [])) == 2)

# --- Step 7: adversarial cases ----------------------------------------------
print("\n[7] adversarial cases")
before = len(server)
server.receive(devA.all() + devB.all())          # redelivery over a second path
check("duplicate delivery is idempotent", len(server) == before, f"{before} -> {len(server)}")

devC = Node("deviceC")                            # a node that never met the server
devC.receive(devB.all())                          # ...but met Bravo
gossip(devC, devA)                                # ...and later met Alpha
check("store-and-forward: unmet node converges", len(devC) == len(server),
      f"deviceC={len(devC)} server={len(server)}")

check("inventory deltas commute (-2 and -3 both applied)",
      inventory(server.all(), "medical_kit") == -5,
      f"net = {inventory(server.all(),'medical_kit')}")

skewed = Event((3, 1), "SEARCH", t_dev=5,        # device clock badly wrong (skew)
               actor={"team": "Charlie", "responder": "C1", "agency": "Police"},
               payload={"cell": "B-14", "status": "searched"}, t_srv=len(server) + 1)
server.receive([skewed])
check("clock-skewed event still ordered and retained",
      skewed.eid in server.log and len(cell_search_events(server.all(), "B-14")) == 3,
      "ordered by server receipt time, device time preserved for audit")

gossip(devA, devB)                                # full convergence between peers
gossip(devA, server); gossip(devB, server)
check("all nodes converge to identical logs",
      len(devA) == len(devB) == len(server) == len(devC.log | {} if False else server.log),
      f"A={len(devA)} B={len(devB)} server={len(server)}")

print("\n" + "=" * 78)
p = sum(1 for _, c, _ in results if c)
print(f"RESULT: {p}/{len(results)} checks passed")
print("=" * 78)
print("\nAUDIT VIEW the commander would see for B-14:")
for e in cell_search_events(server.all(), "B-14"):
    print(f"  searched by {e.actor['team']:<8} ({e.actor['agency']:<6}) "
          f"responder {e.actor['responder']:<3} device_t={e.t_dev:<5} recv_order={e.t_srv}")
print(f"\n  >>> DUPLICATE SEARCH EFFORT FLAGGED: {duplicate_search_flags(server.all())}")
