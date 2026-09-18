package ai.rescuenet.field.store

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Device credential storage — `07` row 12 and `09` §8.
 *
 * `09` §8: *"Token and `hmac_secret` in Android encrypted storage. `hmac_secret`
 * is never transmitted after enrolment."* `07` row 12 names the mechanism:
 * `EncryptedSharedPreferences`.
 *
 * This is the one place on the device that is **not** covered by `06` §14's
 * "no at-rest encryption at Level 1" — that limitation applies to the event
 * database, which holds incident data. Credentials are held separately and
 * encrypted, backed by a hardware-backed key where the device provides one.
 *
 * Neither value is ever logged, printed, or included in any diagnostic. The
 * `hmac_secret` is consumed by **M8**'s batch MAC (DM-49); M6 only stores it.
 */
class DeviceCredentialStore(context: Context) {

    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context.applicationContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context.applicationContext,
            FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun storeToken(token: String) = prefs.edit().putString(KEY_TOKEN, token).commit()

    fun token(): String? = prefs.getString(KEY_TOKEN, null)

    fun storeHmacSecret(secret: ByteArray) =
        prefs.edit().putString(KEY_HMAC, secret.toHex()).commit()

    fun hmacSecret(): ByteArray? = prefs.getString(KEY_HMAC, null)?.fromHex()

    fun storeDeviceId(deviceId: Int) = prefs.edit().putInt(KEY_DEVICE_ID, deviceId).commit()

    fun deviceId(): Int? =
        if (prefs.contains(KEY_DEVICE_ID)) prefs.getInt(KEY_DEVICE_ID, -1) else null

    fun clear() = prefs.edit().clear().commit()

    private fun ByteArray.toHex() = joinToString("") { "%02x".format(it) }

    private fun String.fromHex() =
        ByteArray(length / 2) { substring(it * 2, it * 2 + 2).toInt(16).toByte() }

    private companion object {
        const val FILE_NAME = "rescuenet_device_credential"
        const val KEY_TOKEN = "token"
        const val KEY_HMAC = "hmac_secret"
        const val KEY_DEVICE_ID = "device_id"
    }
}
