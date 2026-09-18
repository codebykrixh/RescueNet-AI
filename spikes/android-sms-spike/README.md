# SP-01b-A / SP-02 — Android SMS spike app

**THROWAWAY. NOT ARCHITECTURE. Delete once results are recorded in `docs/04-feasibility-validation.md`.**

## Prerequisite (currently missing on this machine)
Android Studio + SDK. Verified absent: no `adb`, no SDK, no Gradle, no `kotlinc`.
Install Android Studio, then: new "Empty Activity" project, package `spike.sms`,
replace `MainActivity.kt` with this file, add the manifest entries below, build, install on **both** handsets.

## Manifest additions
```xml
<uses-permission android:name="android.permission.SEND_SMS"/>
<uses-permission android:name="android.permission.RECEIVE_SMS"/>
<application ...>
  <receiver android:name=".SentReceiver" android:exported="false">
    <intent-filter><action android:name="spike.SENT"/></intent-filter>
  </receiver>
  <receiver android:name=".SmsReceiver" android:exported="true">
    <intent-filter android:priority="999">
      <action android:name="android.provider.Telephony.SMS_RECEIVED"/>
    </intent-filter>
    <intent-filter android:priority="999">
      <action android:name="android.intent.action.DATA_SMS_RECEIVED"/>
      <data android:scheme="sms" android:port="16000"/>
    </intent-filter>
  </receiver>
</application>
```

## Procedure
1. Install on handset A and handset B. Grant SMS permissions on both.
2. Enter B's number on A. Run **Q1** (10 binary), wait, run **Q2** (10 text).
3. Reverse direction (B → A) so both carriers are tested both ways.
4. Run **Q3** on one handset only — 40 rapid sends to locate the throttle.
5. Capture logs: `adb logcat -s SMSSPIKE` on each handset, or copy from the on-screen log.
6. Record every field into the tables in `docs/04-feasibility-validation.md` §4.1/§4.2.

## What each button proves
| Button | Question | Pass criterion |
|---|---|---|
| Q1 | Does port-addressed binary SMS survive the carrier? | ≥9/10 `RECV BIN` with `bytes=134` |
| Q2 | Does 120-char GSM-7 text survive? | ≥9/10 `RECV TXT` with `chars=120`, `segments=1` |
| Q3 | Where does the throttle fire? | Note the seq at which `SEND-RESULT` stops being `OK` or a dialog appears |

**Do not infer a result that the log does not show.** Empty result = not run.
