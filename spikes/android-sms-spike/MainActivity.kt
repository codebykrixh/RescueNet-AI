// SP-01b-A / SP-02  --  THROWAWAY SPIKE APP. NOT ARCHITECTURE. DELETE AFTER USE.
// Answers three questions and nothing else:
//   Q1 does port-addressed BINARY SMS survive the carrier?
//   Q2 does 120-byte GSM-7 TEXT SMS survive the carrier?
//   Q3 where does the outgoing-SMS throttle actually fire?
package spike.sms

import android.app.*; import android.content.*; import android.os.*
import android.telephony.SmsManager; import android.widget.*
import androidx.core.app.ActivityCompat
import java.text.SimpleDateFormat; import java.util.*

const val PORT = 16000
lateinit var log: TextView
val ts: SimpleDateFormat = SimpleDateFormat("HH:mm:ss.SSS", Locale.US)
fun logLine(s: String) { val l = "${ts.format(Date())}  $s"; android.util.Log.i("SMSSPIKE", l)
    Handler(Looper.getMainLooper()).post { log.append("$l\n") } }

class MainActivity : Activity() {
    private var dest = ""                       // set this to handset B's number
    private val sent = mutableMapOf<Int, Long>() // seq -> send time

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        ActivityCompat.requestPermissions(this,
            arrayOf(android.Manifest.permission.SEND_SMS, android.Manifest.permission.RECEIVE_SMS), 1)

        val num = EditText(this).apply { hint = "destination number (+91...)" }
        log = TextView(this).apply { textSize = 10f; setTextIsSelectable(true) }
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; addView(num) }

        fun button(label: String, action: () -> Unit) =
            root.addView(Button(this).apply { text = label
                setOnClickListener { dest = num.text.toString().trim(); action() } })

        // Q1: 10 binary data SMS, 134 bytes each, 30s apart
        button("Q1  send 10 x BINARY (134B)") { burst(10, 30_000) { i -> sendBinary(i, 134) } }
        // Q2: 10 text SMS, 120 chars each, 30s apart
        button("Q2  send 10 x TEXT (120 chars)") { burst(10, 30_000) { i -> sendText(i, 120) } }
        // Q3: 40 text SMS as fast as possible -- find the throttle
        button("Q3  THROTTLE: 40 x TEXT rapid") { burst(40, 500) { i -> sendText(1000 + i, 40) } }
        button("dump log") { logLine("--- ${sent.size} sends recorded ---") }
        root.addView(ScrollView(this).apply { addView(log) })
        setContentView(root)
        logLine("ready. receiver listening on port $PORT and on plain SMS.")
    }

    private fun burst(n: Int, gapMs: Long, send: (Int) -> Unit) {
        Thread { for (i in 1..n) { try { send(i) } catch (e: Exception) {
            logLine("SEND-EXCEPTION seq=$i ${e.javaClass.simpleName}: ${e.message}") }
            Thread.sleep(gapMs) } }.start()
    }

    private fun pending(seq: Int, kind: String): PendingIntent {
        val i = Intent("spike.SENT").putExtra("seq", seq).putExtra("kind", kind)
        return PendingIntent.getBroadcast(this, seq, i, PendingIntent.FLAG_IMMUTABLE)
    }

    private fun sendBinary(seq: Int, bytes: Int) {
        val payload = ByteArray(bytes) { ((seq * 7 + it) % 251).toByte() }
        payload[0] = seq.toByte()
        sent[seq] = System.currentTimeMillis()
        SmsManager.getDefault().sendDataMessage(dest, null, PORT.toShort(), payload, pending(seq, "BIN"), null)
        logLine("SENT-ATTEMPT BIN seq=$seq bytes=$bytes")
    }

    private fun sendText(seq: Int, chars: Int) {
        val alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        val body = "S$seq|" + (0 until chars - 8).map { alpha[(it * 7 + seq) % 64] }.joinToString("")
        sent[seq] = System.currentTimeMillis()
        SmsManager.getDefault().sendTextMessage(dest, null, body.take(chars), pending(seq, "TXT"), null)
        logLine("SENT-ATTEMPT TXT seq=$seq chars=${body.take(chars).length}")
    }
}

// Result of the SEND attempt (not delivery) -- catches throttle and radio errors.
class SentReceiver : BroadcastReceiver() {
    override fun onReceive(c: Context, i: Intent) {
        val seq = i.getIntExtra("seq", -1); val kind = i.getStringExtra("kind")
        val r = when (resultCode) {
            Activity.RESULT_OK -> "OK"
            SmsManager.RESULT_ERROR_GENERIC_FAILURE -> "GENERIC_FAILURE (throttle often surfaces here)"
            SmsManager.RESULT_ERROR_NO_SERVICE -> "NO_SERVICE"
            SmsManager.RESULT_ERROR_RADIO_OFF -> "RADIO_OFF"
            SmsManager.RESULT_ERROR_NULL_PDU -> "NULL_PDU"
            else -> "UNKNOWN($resultCode)"
        }
        logLine("SEND-RESULT $kind seq=$seq -> $r")
    }
}

// Inbound: binary on PORT, and plain text.
class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(c: Context, i: Intent) {
        when (i.action) {
            "android.intent.action.DATA_SMS_RECEIVED" -> {
                val pdus = i.extras?.get("pdus") as? Array<*> ?: return
                var total = 0; var first = -1
                pdus.forEach { p ->
                    val m = android.telephony.SmsMessage.createFromPdu(p as ByteArray)
                    val b = m.userData ?: ByteArray(0)
                    total += b.size; if (first < 0 && b.isNotEmpty()) first = b[0].toInt()
                }
                logLine("RECV BIN seq=$first bytes=$total")
            }
            "android.provider.Telephony.SMS_RECEIVED" -> {
                val msgs = android.provider.Telephony.Sms.Intents.getMessagesFromIntent(i)
                val body = msgs.joinToString("") { it.messageBody }
                logLine("RECV TXT chars=${body.length} head=${body.take(12)} segments=${msgs.size}")
            }
        }
    }
}
