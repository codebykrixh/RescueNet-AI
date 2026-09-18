package ai.rescuenet.field.transport

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull

/**
 * The platform's verdict on a **send submission** — not on delivery.
 *
 * `SmsManager` reports this asynchronously through the `sentIntent`
 * `PendingIntent`. **This is where SP-01b-A's `GENERIC_FAILURE` appeared**, and
 * discarding it (the earlier `sentIntent = null`) made that failure invisible.
 *
 * [SUBMITTED] means the radio accepted the message. It is **not** evidence that
 * the carrier delivered it, and never evidence that the gateway accepted the
 * batch — only the ACK says that (D-06).
 */
enum class SmsSendResult {
    /** `Activity.RESULT_OK` — handed to the radio. Says nothing about delivery. */
    SUBMITTED,

    /** `RESULT_ERROR_GENERIC_FAILURE` — the throttle and most carrier refusals surface here. */
    GENERIC_FAILURE,

    NO_SERVICE,
    RADIO_OFF,
    NULL_PDU,

    /** An unmapped platform code, or no result before the timeout. */
    UNKNOWN,
}

/**
 * The one place `android.telephony.SmsManager` is touched.
 *
 * Isolating it keeps [SmsTransport]'s batching, budget and eligibility logic
 * testable on the JVM **without sending a real message**, and keeps platform SMS
 * knowledge at the very bottom — `06` §3 rule 3 and `06` §8: *"All SMS-specific
 * knowledge lives here and nowhere else."*
 */
interface SmsSender {
    /** Submits one text message and awaits the platform's send result. */
    suspend fun sendText(destination: String, body: String): SmsSendResult
}

/**
 * Real sender. **GSM-7 text only** — D-02a is Final and binary/port-addressed
 * SMS is rejected on measured evidence (SP-01b-A Q1: 0/10 delivered, 10/10
 * `GENERIC_FAILURE`). `sendDataMessage` is deliberately never called.
 *
 * A per-send `PendingIntent` carries the platform verdict back to a short-lived
 * dynamically registered receiver, so no manifest entry and no application
 * lifecycle work is needed. Nothing sensitive is logged: not the destination,
 * not the body, not the MAC.
 */
class AndroidSmsSender(
    private val context: Context,
    private val timeoutMs: Long = DEFAULT_TIMEOUT_MS,
) : SmsSender {

    private val counter = AtomicInteger(0)

    override suspend fun sendText(destination: String, body: String): SmsSendResult {
        val token = counter.incrementAndGet()
        val action = "$ACTION_SENT.$token"
        val app = context.applicationContext

        val result = withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine { cont ->
                val receiver = object : BroadcastReceiver() {
                    override fun onReceive(c: Context, i: Intent) {
                        runCatching { app.unregisterReceiver(this) }
                        if (cont.isActive) cont.resume(map(resultCode))
                    }
                }
                ContextCompat.registerReceiver(
                    app, receiver, IntentFilter(action), ContextCompat.RECEIVER_NOT_EXPORTED,
                )
                cont.invokeOnCancellation { runCatching { app.unregisterReceiver(receiver) } }

                val sent = PendingIntent.getBroadcast(
                    app, token, Intent(action).setPackage(app.packageName),
                    PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE,
                )
                try {
                    app.getSystemService(SmsManager::class.java)
                        .sendTextMessage(destination, null, body, sent, null)
                } catch (e: Exception) {
                    runCatching { app.unregisterReceiver(receiver) }
                    if (cont.isActive) cont.resume(SmsSendResult.UNKNOWN)
                }
            }
        }
        return result ?: SmsSendResult.UNKNOWN
    }

    private fun map(code: Int): SmsSendResult = when (code) {
        Activity.RESULT_OK -> SmsSendResult.SUBMITTED
        SmsManager.RESULT_ERROR_GENERIC_FAILURE -> SmsSendResult.GENERIC_FAILURE
        SmsManager.RESULT_ERROR_NO_SERVICE -> SmsSendResult.NO_SERVICE
        SmsManager.RESULT_ERROR_RADIO_OFF -> SmsSendResult.RADIO_OFF
        SmsManager.RESULT_ERROR_NULL_PDU -> SmsSendResult.NULL_PDU
        else -> SmsSendResult.UNKNOWN
    }

    companion object {
        private const val ACTION_SENT = "ai.rescuenet.field.SMS_SENT"
        const val DEFAULT_TIMEOUT_MS = 60_000L
    }
}
