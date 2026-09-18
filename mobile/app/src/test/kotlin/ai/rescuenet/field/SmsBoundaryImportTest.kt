package ai.rescuenet.field

import org.junit.Assert.*
import org.junit.Test
import java.io.File

/**
 * **The M8 import/boundary test** — `12` M8 completion criteria:
 * *"no SMS knowledge above the transport interface — verified by an import
 * test"*, and `06` §3 rule 3 / §8: *"All SMS-specific knowledge lives here and
 * nowhere else."*
 *
 * This is a source-level scan rather than a reflection check, because the
 * property is about **compile-time dependencies**: a package that never imports
 * SMS or codec symbols cannot acquire SMS behaviour at runtime.
 */
class SmsBoundaryImportTest {

    private val mainRoot = File("src/main/kotlin/ai/rescuenet/field")

    /** Packages that must remain entirely free of SMS and codec knowledge. */
    private val above = listOf("domain", "store", "sync")

    /** Symbols that constitute SMS or wire-codec knowledge. */
    private val forbidden = listOf(
        "SmsManager", "SmsTransport", "SmsSender", "sendTextMessage", "sendDataMessage",
        "ai.rescuenet.field.codec", "SmsCodec", "BatchMac", "AckCodec", "WireEvent",
        "BitWriter", "BitReader", "base64url", "Base64", "gsm", "GSM",
    )

    private fun kotlinFiles(pkg: String): List<File> =
        File(mainRoot, pkg).listFiles()?.filter { it.extension == "kt" } ?: emptyList()

    private fun codeLines(f: File): List<Pair<Int, String>> {
        val out = mutableListOf<Pair<Int, String>>()
        var inBlock = false
        f.readLines().forEachIndexed { i, raw ->
            val t = raw.trim()
            if (t.startsWith("/*")) inBlock = true
            val isComment = inBlock || t.startsWith("*") || t.startsWith("//")
            if (t.contains("*/")) inBlock = false
            if (!isComment && t.isNotEmpty()) out += (i + 1) to raw
        }
        return out
    }

    @Test fun sourceTreeIsWhereWeThinkItIs() {
        assertTrue("test must run from the module dir; got ${mainRoot.absolutePath}", mainRoot.isDirectory)
        above.forEach { assertTrue("$it must exist", File(mainRoot, it).isDirectory) }
    }

    /** No package above the transport boundary may reference SMS or the codec. */
    @Test fun noSmsOrCodecKnowledgeAboveTheTransportInterface() {
        val violations = mutableListOf<String>()
        above.forEach { pkg ->
            kotlinFiles(pkg).forEach { f ->
                codeLines(f).forEach { (n, line) ->
                    forbidden.forEach { sym ->
                        if (line.contains(sym)) violations += "$pkg/${f.name}:$n references '$sym'"
                    }
                }
            }
        }
        assertTrue("SMS/codec knowledge leaked above the transport interface:\n" +
            violations.joinToString("\n"), violations.isEmpty())
    }

    /** The sync layer must depend only on the abstract Transport, never a concrete one. */
    @Test fun syncLayerDependsOnlyOnTheTransportAbstraction() {
        val leaks = kotlinFiles("sync").flatMap { f ->
            codeLines(f).filter { (_, l) ->
                l.contains("InternetTransport") || l.contains("SmsTransport")
            }.map { (n, _) -> "sync/${f.name}:$n" }
        }
        assertTrue("sync must not name a concrete transport: $leaks", leaks.isEmpty())
    }

    /** SmsManager may appear in exactly one file, the platform sender. */
    @Test fun smsManagerAppearsOnlyInTheDedicatedSender() {
        val files = mainRoot.walkTopDown().filter { it.extension == "kt" }
            .filter { f -> codeLines(f).any { it.second.contains("SmsManager") } }
            .map { it.name }.toList()
        assertEquals("SmsManager must be confined to AndroidSmsSender", listOf("SmsSender.kt"), files)
    }

    /** Binary SMS must not exist anywhere: D-02a rejected it on measured evidence. */
    @Test fun noBinarySmsAnywhereInProduction() {
        val hits = mainRoot.walkTopDown().filter { it.extension == "kt" }.flatMap { f ->
            codeLines(f).filter { it.second.contains("sendDataMessage") }.map { "${f.name}:${it.first}" }
        }.toList()
        assertTrue("sendDataMessage must never be called (D-02a, SP-01b-A Q1 failed): $hits", hits.isEmpty())
    }

    /** No second credential store and no second HMAC implementation. */
    @Test fun exactlyOneCredentialStoreAndOneMacImplementation() {
        val all = mainRoot.walkTopDown().filter { it.extension == "kt" }.toList()
        val stores = all.filter { f -> codeLines(f).any { it.second.contains("EncryptedSharedPreferences") } }
        assertEquals("one credential store only", listOf("DeviceCredentialStore.kt"), stores.map { it.name })
        val macs = all.filter { f -> codeLines(f).any { it.second.contains("Mac.getInstance") } }
        assertEquals("one MAC implementation only", listOf("BatchMac.kt"), macs.map { it.name })
    }
}
