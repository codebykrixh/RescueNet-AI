"""
SP-01a  --  SMS payload budget experiment (ISOLATED SPIKE CODE, NOT ARCHITECTURE)
Question: do RescueNet operational events fit inside an SMS payload, and how many
SMS does a realistic demo scenario need against Android's outgoing throttle?
Pure computation -- no device, no carrier, no network involved.
"""
import math

# ---- Field widths in BITS, derived from NFR-09 prototype scale targets -------
# (5,000 cells / 20 teams / 200 responders / 5 agencies / 72h incident)
F = {
    "device_id":      12,   # 4096 devices
    "seq":            20,   # 1M events per device  -> (device,seq) = event id
    "t_offset":       20,   # seconds since incident start = 12.1 days
    "cell_id":        13,   # addresses 0..8191 -> MAX_CELLS = 8191 (see docs/09 S10.5)
    "cell_status":     3,   # 5 statuses + headroom
    "team_id":         8,   # 256 teams
    "responder_id":   10,   # 1024 responders
    "agency_id":       4,   # 16 agencies
    "rel_lat":        16,   # +/-32km @ 1m from incident origin
    "rel_lon":        16,
    "person_count":    6,   # 0-63
    "surv_status":     3,   # trapped/accessible/extricated/deceased
    "triage":          3,
    "item_id":         8,   # 256 catalogue items
    "qty_delta":       8,   # signed -128..127
    "evt_type":        3,   # 8 event types
}

def bits(*names): return sum(F[n] for n in names)

# ---- Event schemas ----------------------------------------------------------
# Two variants per event: STANDALONE (self-contained) and BATCHED (shared header
# supplies device_id + base timestamp + team/agency; delta-encoded time).
EVENTS = {
    "CELL_STATUS": {
        "standalone": bits("evt_type","device_id","seq","t_offset","cell_id",
                           "cell_status","team_id","responder_id","agency_id"),
        "batched":    bits("evt_type","seq","cell_id","cell_status","responder_id") + 12,  # 12b time delta
    },
    "SURVIVOR_REPORT": {
        "standalone": bits("evt_type","device_id","seq","t_offset","cell_id","rel_lat",
                           "rel_lon","person_count","surv_status","triage","team_id",
                           "responder_id","agency_id"),
        "batched":    bits("evt_type","seq","cell_id","rel_lat","rel_lon","person_count",
                           "surv_status","triage","responder_id") + 12,
    },
    "POSITION": {
        "standalone": bits("evt_type","device_id","seq","t_offset","rel_lat","rel_lon",
                           "team_id","agency_id"),
        "batched":    bits("evt_type","seq","rel_lat","rel_lon") + 12,
    },
    "INVENTORY_DELTA": {
        "standalone": bits("evt_type","device_id","seq","t_offset","item_id","qty_delta",
                           "team_id","responder_id","agency_id"),
        "batched":    bits("evt_type","seq","item_id","qty_delta","responder_id") + 12,
    },
}
BATCH_HEADER_BITS = bits("device_id","t_offset","team_id","agency_id") + 4 + 5  # +proto ver +count

# ---- Transport envelopes ----------------------------------------------------
# Text SMS: 160 GSM-7 chars single / 153 concatenated. base64url is GSM-7 safe,
#           so 1 char carries 6 bits of payload -> 160*6/8 = 120 bytes.
# Data SMS: 140-byte binary payload; port addressing consumes ~6 bytes of UDH.
ENV = {
    "Text SMS (single, base64url in GSM-7)":      120,
    "Text SMS (concatenated segment, base64url)": 114,   # 153 chars * 6 / 8
    "Data SMS (binary, port-addressed)":          134,
}

def b2B(b): return math.ceil(b / 8)

print("=" * 78)
print("SP-01a  SMS PAYLOAD BUDGET  --  computed result, no hardware involved")
print("=" * 78)

print("\n[1] SINGLE-EVENT SIZE (bits -> bytes)\n")
print(f"{'event type':<18}{'standalone':>22}{'batched (in-batch)':>24}")
print("-" * 64)
for name, v in EVENTS.items():
    print(f"{name:<18}{v['standalone']:>4}b = {b2B(v['standalone']):>3}B{'':>8}"
          f"{v['batched']:>4}b = {b2B(v['batched']):>3}B")
print(f"\nbatch header: {BATCH_HEADER_BITS}b = {b2B(BATCH_HEADER_BITS)}B "
      f"(carries device_id, base time, team, agency for the whole batch)")

print("\n[2] EVENTS PER SMS, BY ENVELOPE\n")
print(f"{'envelope':<44}{'bytes':>7}", end="")
for n in EVENTS: print(f"{n.split('_')[0][:6]:>8}", end="")
print()
print("-" * 78)
for env_name, cap_B in ENV.items():
    print(f"{env_name:<44}{cap_B:>7}", end="")
    for name, v in EVENTS.items():
        usable_bits = cap_B * 8 - BATCH_HEADER_BITS
        n = usable_bits // v["batched"]
        print(f"{n:>8}", end="")
    print()

print("\n[3] MIXED REALISTIC BATCH (what one field team actually accumulates)")
mix = {"CELL_STATUS": 6, "SURVIVOR_REPORT": 2, "POSITION": 8, "INVENTORY_DELTA": 3}
tot = BATCH_HEADER_BITS + sum(EVENTS[k]["batched"] * n for k, n in mix.items())
print(f"    mix = {mix}")
print(f"    total = {tot} bits = {b2B(tot)} bytes  ({sum(mix.values())} events)")
for env_name, cap_B in ENV.items():
    print(f"    -> {env_name:<44} {math.ceil(b2B(tot)/cap_B)} SMS")

print("\n[4] DEMO-SCENARIO VOLUME vs ANDROID OUTGOING THROTTLE (~30 msgs / 30 min)\n")
# Two teams offline for a 10-minute demo window, then both sync.
scenarios = {
    "Demo (2 teams x 19 events, D-01 duplicate-search scenario)": 2 * 19,
    "Busy hour (5 teams x 40 events)":                             5 * 40,
    "Full shift (20 teams x 150 events)":                         20 * 150,
}
avg_evt_bits = sum(EVENTS[k]["batched"] * n for k, n in mix.items()) / sum(mix.values())
for label, n_events in scenarios.items():
    payload_bits = BATCH_HEADER_BITS * math.ceil(n_events / 19) + avg_evt_bits * n_events
    for env_name, cap_B in [("Data SMS", 134), ("Text SMS", 120)]:
        msgs = math.ceil(b2B(payload_bits) / cap_B)
        verdict = "OK" if msgs <= 30 else "EXCEEDS 30/30min THROTTLE"
        print(f"  {label:<58} {env_name:<10} {msgs:>4} SMS   {verdict}")
    print()

print("[5] KEY SIZING DECISIONS SURFACED BY THIS EXPERIMENT")
print("  * A 128-bit UUID event id costs 16B/event and would fit only",
      f"{(134*8 - BATCH_HEADER_BITS)//(128+EVENTS['CELL_STATUS']['batched'])}",
      "events per data SMS.")
print(f"    (device_id, seq) = {b2B(F['device_id']+F['seq'])}B and fits far more. UUIDs are unaffordable here.")
print("  * Absolute lat/lon (2 x float64 = 16B) vs origin-relative 16-bit (4B):",
      "4x saving at 1m resolution within +/-32km.")
print("  * Position events are the cheapest individually but dominate by count ->")
print("    confirms PI-08 (event-driven capture, never streaming).")
