"""
SP-01b-M  --  MANUAL SMS wire test payload generator  (THROWAWAY SPIKE CODE)
Requires NO Android SDK and NO app: payloads are pasted into the stock SMS app.
Answers: does a full-size GSM-7 payload survive the carriers byte-identical?
Run:  python3 spikes/sp01b_manual_payloads.py            -> generates payloads
      python3 spikes/sp01b_manual_payloads.py --verify   -> checks what arrived
"""
import sys, zlib

# base64url alphabet is GSM-7 safe (A-Z a-z 0-9 - _), so 1 char = 1 septet.
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

def payload(n, tag):
    """Deterministic n-char body whose last 8 chars are a CRC32 of the rest."""
    body = "".join(ALPHA[(i * 7 + ord(tag[0])) % 64] for i in range(n - 12))
    crc = format(zlib.crc32(body.encode()) & 0xFFFFFFFF, "08x")
    return f"{tag}|{body}|{crc}"[:n].ljust(n, "=")

TESTS = [
    ("T1", 160, "single segment, max GSM-7  -> must arrive as 1 SMS, unaltered"),
    ("T2", 161, "one char over  -> forces concatenation into 2 segments"),
    ("T3", 306, "2 concatenated segments (2 x 153)"),
    ("T4", 459, "3 concatenated segments (3 x 153)"),
    ("T5", 120, "the REAL budget: 120 chars = 120 bytes payload per SP-01a"),
]

def verify(received, expected):
    if received == expected: return "EXACT MATCH"
    if len(received) != len(expected): return f"LENGTH DIFF: got {len(received)}, expected {len(expected)}"
    diffs = [i for i,(a,b) in enumerate(zip(received,expected)) if a!=b]
    return f"CORRUPTED at {len(diffs)} positions, first at index {diffs[0]}"

if "--verify" in sys.argv:
    # Identify each line by the test ID it carries, NOT by its position in the
    # paste. Lines may arrive in any order, and each tag legitimately appears
    # more than once because the protocol tests A->B and B->A.
    BY_TAG = {tag: n for tag, n, _ in TESTS}
    print("Paste each RECEIVED message body, one per line, then Ctrl-D:\n")
    got = [l.rstrip("\n") for l in sys.stdin if l.strip()]
    for lineno, line in enumerate(got, 1):
        tag = (line.split("|", 1)[0] if "|" in line else line[:2]).strip()
        if tag not in BY_TAG:
            print(f"  line {lineno}: UNKNOWN TEST ID {tag!r} "
                  f"(expected one of {', '.join(sorted(BY_TAG))}) "
                  f"-- prefix corrupted, or not a spike payload")
            continue
        n = BY_TAG[tag]
        print(f"  line {lineno}  {tag} ({n} chars): {verify(line, payload(n, tag))}")
    sys.exit()

print("=" * 78)
print("SP-01b-M  MANUAL SMS PAYLOADS  --  send each from handset A to handset B")
print("=" * 78)
print("\nPROCEDURE")
print("  1. On handset A, open the stock SMS app.")
print("  2. Paste each payload below EXACTLY, send to handset B, note send time.")
print("  3. On handset B, note arrival time and how many messages the app shows.")
print("  4. Copy the received body back, run: python3 spikes/sp01b_manual_payloads.py --verify")
print("  5. Repeat A->B and B->A so BOTH carriers are tested in both directions.\n")
for tag, n, why in TESTS:
    p = payload(n, tag)
    print("-" * 78)
    print(f"{tag}  ({n} chars)  {why}")
    print(f"expected segments: {1 if n<=160 else -(-n//153)}")
    print(p)
print("-" * 78)
print("\nRECORD FOR EACH: send time | arrival time | segments shown | verify result")
