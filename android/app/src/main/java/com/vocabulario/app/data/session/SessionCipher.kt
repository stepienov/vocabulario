package com.vocabulario.app.data.session

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

interface SessionCipher {
    fun encrypt(plain: ByteArray): ByteArray

    /** Rzuca [SessionKeyUnavailableException], gdy klucza nie ma (np. odtworzenie na innym urządzeniu). */
    fun decrypt(blob: ByteArray): ByteArray
}

class SessionKeyUnavailableException : Exception("session key unavailable")

/** AES-256/GCM w Android Keystore; świeży IV przy każdym zapisie, wersjonowany format bloba. */
@Singleton
class KeystoreSessionCipher @Inject constructor() : SessionCipher {

    override fun encrypt(plain: ByteArray): ByteArray {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, existingKey() ?: generateKey())
        val iv = cipher.iv
        val sealed = cipher.doFinal(plain)
        return byteArrayOf(FORMAT_V1, iv.size.toByte()) + iv + sealed
    }

    override fun decrypt(blob: ByteArray): ByteArray {
        require(blob.size > 2 && blob[0] == FORMAT_V1) { "unsupported session blob" }
        val ivLength = blob[1].toInt()
        require(ivLength in 12..16 && blob.size > 2 + ivLength) { "corrupt session blob" }
        val iv = blob.copyOfRange(2, 2 + ivLength)
        val key = existingKey() ?: throw SessionKeyUnavailableException()
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(TAG_BITS, iv))
        return cipher.doFinal(blob, 2 + ivLength, blob.size - 2 - ivLength)
    }

    private fun existingKey(): SecretKey? {
        val store = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        return store.getKey(KEY_ALIAS, null) as? SecretKey
    }

    private fun generateKey(): SecretKey {
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "vocabulario_session_v1"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val TAG_BITS = 128
        const val FORMAT_V1: Byte = 1
    }
}
