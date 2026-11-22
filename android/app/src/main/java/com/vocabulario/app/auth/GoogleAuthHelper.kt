package com.vocabulario.app.auth

import android.content.Context
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.vocabulario.app.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CancellationException
import javax.inject.Inject
import javax.inject.Singleton

/** Użytkownik zamknął selektor Google: powrót bez błędu i bez żądania do serwera. */
class GoogleSignInCancelledException : Exception("google_sign_in_cancelled")

/** Selektor zwrócił coś innego niż token tożsamości Google. */
class GoogleTokenMissingException : Exception("google_token_missing")

/** Wybór konta Google z nonce wydanym przez serwer; wywoływany wyłącznie po świadomym kliknięciu. */
fun interface GoogleIdTokenProvider {
    suspend fun idToken(nonce: String): String
}

@Singleton
class GoogleAuthHelper @Inject constructor(
    @ApplicationContext private val appContext: Context,
) {

    fun provider(activityContext: Context): GoogleIdTokenProvider =
        GoogleIdTokenProvider { nonce -> signIn(activityContext, nonce) }

    suspend fun signIn(activityContext: Context, nonce: String): String {
        val option = GetSignInWithGoogleOption.Builder(BuildConfig.GOOGLE_WEB_CLIENT_ID)
            .setNonce(nonce)
            .build()
        val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
        val credential = try {
            CredentialManager.create(activityContext).getCredential(activityContext, request).credential
        } catch (e: GetCredentialCancellationException) {
            throw GoogleSignInCancelledException()
        }
        if (credential is CustomCredential &&
            credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
        ) {
            return GoogleIdTokenCredential.createFrom(credential.data).idToken
        }
        throw GoogleTokenMissingException()
    }

    /** Po świadomym wylogowaniu; nie oznacza odłączenia Google od konta w aplikacji. */
    suspend fun clearCredentialState(): Boolean = try {
        CredentialManager.create(appContext).clearCredentialState(ClearCredentialStateRequest())
        true
    } catch (e: CancellationException) {
        throw e
    } catch (_: Exception) {
        false
    }
}
