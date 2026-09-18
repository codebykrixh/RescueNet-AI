"""SP-01a addendum: throttle is PER-APP-PER-DEVICE, not per-incident.
Redo section [4] on the correct basis: uplink per field device vs downlink from gateway."""
import math
AVG_EVT_B, HDR_B, CAP = 70.6/8, 7, 134   # avg batched event bits/8, header bytes, data-SMS bytes

def msgs(n_events, per_batch=19):
    payload = HDR_B*math.ceil(n_events/per_batch) + AVG_EVT_B*n_events
    return math.ceil(payload/CAP)

print("="*74); print("SP-01a ADDENDUM -- throttle applied per device (~30 msgs / 30 min)"); print("="*74)
print("\nUPLINK: each field device sends only its OWN events\n")
for label, ev, dev in [("Demo window (1 team, 19 events)",19,1),
                       ("Busy hour (1 team, 40 events)",40,1),
                       ("Full 8h shift (1 team, 150 events)",150,1)]:
    m = msgs(ev)
    print(f"  {label:<40} {m:>3} SMS/device   {'OK' if m<=30 else 'THROTTLED'}")

print("\nDOWNLINK: gateway sends assignments/acks to N devices\n")
for teams in (2,5,10,20):
    # gateway must reach each device separately: SMS has no broadcast
    per_device_msgs = 1           # one assignment batch per device per cycle
    total = teams*per_device_msgs
    for cycles,label in ((1,"one assignment cycle"),(3,"three cycles in 30 min")):
        t = total*cycles
        print(f"  {teams:>2} teams, {label:<24} {t:>3} SMS from gateway  "
              f"{'OK' if t<=30 else '*** THROTTLED ***'}")
    print()
print("FINDING: the field uplink is comfortably inside the throttle at every")
print("realistic volume. The GATEWAY DOWNLINK is the chokepoint -- SMS has no")
print("broadcast, so one gateway handset must send N separate messages, and at")
print(">=10 teams with repeated assignment cycles it hits the 30/30min limit.")
print("\nIMPLICATION: prototype gateway should be RECEIVE-MOSTLY. Push assignments")
print("over data when available; use SMS downlink only for the demo's 2 teams.")
