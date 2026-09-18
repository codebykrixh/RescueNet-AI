package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.store.DeviceCredentialStore
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * `07` row 12 / `09` §8 — token and `hmac_secret` in `EncryptedSharedPreferences`.
 *
 * No test prints either value. The `hmac_secret` is recoverable by design
 * (DM-47) because M8 must recompute a MAC with it; that is exactly why it must
 * never reach an unencrypted store.
 */
@RunWith(AndroidJUnit4::class)
class CredentialStoreTest {

    private lateinit var store: DeviceCredentialStore

    @Before fun setUp() {
        store = DeviceCredentialStore(context())
        store.clear()
    }

    @Test fun credentialsSurviveAStoreReopen() {
        val token = "t_" + "0".repeat(41)
        val secret = ByteArray(32) { (it * 7 % 251).toByte() }
        store.storeToken(token)
        store.storeHmacSecret(secret)
        store.storeDeviceId(DEVICE_ID)

        val reopened = DeviceCredentialStore(context())
        assertEquals(token, reopened.token())
        assertArrayEquals(secret, reopened.hmacSecret())
        assertEquals(DEVICE_ID, reopened.deviceId())
    }

    /**
     * **Negative control for credential confidentiality.** The backing file must
     * not contain either value in plaintext. If `EncryptedSharedPreferences`
     * were swapped for plain `SharedPreferences`, this test fails.
     */
    @Test fun theBackingFileContainsNeitherValueInPlaintext() {
        val token = "TOKEN_SENTINEL_9f2c4a1e"
        val secretText = "HMAC_SENTINEL_5b8d3e77"
        store.storeToken(token)
        store.storeHmacSecret(secretText.toByteArray())

        val dir = File(context().applicationInfo.dataDir, "shared_prefs")
        val files = dir.listFiles().orEmpty().filter { it.name.contains("rescuenet_device_credential") }
        assertFalse("the credential prefs file must exist", files.isEmpty())

        files.forEach { f ->
            val raw = f.readBytes().toString(Charsets.ISO_8859_1)
            assertFalse("token must not be stored in plaintext", raw.contains(token))
            assertFalse("hmac_secret must not be stored in plaintext", raw.contains(secretText))
            assertFalse("the key name must not be plaintext either", raw.contains("hmac_secret"))
        }
    }

    @Test fun clearRemovesEverything() {
        store.storeToken("t_x"); store.storeHmacSecret(byteArrayOf(1, 2, 3))
        store.clear()
        assertNull(store.token())
        assertNull(store.hmacSecret())
        assertNull(store.deviceId())
    }
}
