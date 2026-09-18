#!/usr/bin/env bash
# TR-19 (= SP-04) — "100% of acknowledged writes survive five kill/reboot cycles".
#
# Level D, instrumented, PHYSICAL DEVICE ONLY. An emulator cannot satisfy this:
# the reboot is the measurement, not scaffolding around it.
#
# Cycle: force-stop -> reboot -> wait for boot -> verify every acknowledged
# write is still present with its outbox row and its seq.
#
# Usage:  ANDROID_HOME=... JAVA_HOME=<Studio JBR> mobile/tools/tr19_cycles.sh [cycles]
set -euo pipefail

CYCLES="${1:-5}"
PKG=ai.rescuenet.field
RUNNER="$PKG.test/androidx.test.runner.AndroidJUnitRunner"
CLS="$PKG.Tr19DurabilityTest"
ADB="${ANDROID_HOME:?ANDROID_HOME must be set}/platform-tools/adb"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

run_phase() {
  # NOTE: `am instrument` returns INSTRUMENTATION_CODE: -1 on SUCCESS
  # (Activity.RESULT_OK). Success is "OK (n tests)"; failure is "FAILURES!!!".
  local log=/tmp/tr19_phase.txt
  echo "    -> $1"
  "$ADB" shell am instrument -w -r -e class "$CLS#$1" "$RUNNER" >"$log" 2>&1 || true
  grep -E 'OK \([0-9]+ test|FAILURES!!!|Tests run:' "$log" | sed 's/^/       /'
  if grep -q 'FAILURES!!!' "$log" || ! grep -qE 'OK \([1-9][0-9]* test' "$log"; then
    echo "    PHASE FAILED — transcript:"
    tail -30 "$log" | sed 's/^/       /'
    exit 1
  fi
}

wait_for_device() {
  "$ADB" wait-for-device
  until [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
    sleep 3
  done
  # sys.boot_completed fires while credential-encrypted storage may still be
  # LOCKED. Room then fails with SQLITE_CANTOPEN, which looks like data loss and
  # is not. Wait for the user to be genuinely unlocked before touching the DB.
  "$ADB" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true
  local waited=0
  until "$ADB" shell dumpsys user 2>/dev/null | grep -q 'RUNNING_UNLOCKED'; do
    sleep 5; waited=$((waited + 5))
    if [ "$waited" -ge 300 ]; then
      echo "    STALLED: handset still locked after ${waited}s."
      echo "    Credential-encrypted storage is unavailable until it is unlocked by hand."
      echo "    Unlock the phone and re-run. An emulator is NOT a substitute (TR-19 is level D)."
      exit 2
    fi
  done
  sleep 5
}

echo "== building and installing =="
(cd "$HERE" && ./gradlew :app:installDebug :app:installDebugAndroidTest --console=plain -q)

echo "== resetting on-disk database =="
run_phase phase0_reset

echo "== seeding acknowledged writes =="
run_phase phase1_writeAndAcknowledge

for i in $(seq 1 "$CYCLES"); do
  echo "== cycle $i/$CYCLES =="
  echo "    force-stop"
  "$ADB" shell am force-stop "$PKG" || true
  "$ADB" shell am force-stop "$PKG.test" || true
  echo "    reboot"
  "$ADB" reboot
  sleep 10
  wait_for_device
  run_phase phase2_verifySurvived
  run_phase phase1_writeAndAcknowledge
done

echo "== TR-19 COMPLETE: $CYCLES kill/reboot cycles, all acknowledged writes survived =="
