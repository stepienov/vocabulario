package com.vocabulario.app.data.deletion

import com.vocabulario.app.auth.GoogleIdTokenProvider
import com.vocabulario.app.data.AuthRepository
import com.vocabulario.app.data.api.DeletionCancelBody
import com.vocabulario.app.data.api.DeletionGoogleChallengeRequest
import com.vocabulario.app.data.api.DeletionGoogleProofRequest
import com.vocabulario.app.data.api.DeletionProofRequest
import com.vocabulario.app.data.api.DeletionProofResponse
import com.vocabulario.app.data.api.DeletionRequestBody
import com.vocabulario.app.data.api.DeletionStatusRequest
import com.vocabulario.app.data.api.DeletionView
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.api.apiErrorCode
import com.vocabulario.app.data.session.LogoutConsent
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import java.security.SecureRandom
import java.util.Base64
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/** Dowód hasłem wystawiono dla innego konta niż to, które jest zalogowane (lub zapisane w pokwitowaniu). */
class DeletionOwnerMismatchException : Exception("deletion_owner_mismatch")

sealed interface DeletionOutcome {
    data object None : DeletionOutcome
    data class Pending(val view: DeletionView) : DeletionOutcome
    data object Cancelled : DeletionOutcome
    data object Completed : DeletionOutcome
}

internal const val DELETION_STATE_COMPLETED = "completed"
internal const val DELETION_STATE_CANCELLED = "cancelled"
internal const val DELETION_METHOD_PASSWORD = "password"
internal const val DELETION_METHOD_GOOGLE = "google"

/** 32 losowe bajty jako base64url bez dopełnienia (43 znaki), jak wymaga serwer. */
internal fun newSecret32(random: SecureRandom = SecureRandom()): String {
    val bytes = ByteArray(32)
    random.nextBytes(bytes)
    return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
}

/** Odrzucenie, po którym ponowienie z tym samym `request_id` nie ma sensu. */
internal fun isDefinitiveRejection(e: Throwable): Boolean {
    val code = (e as? HttpException)?.code() ?: return false
    return code in 400..499 && code != 408 && code != 426 && code != 429
}

/**
 * Usuwanie konta z poziomu aplikacji (E-001/F-006/T-002 §5). Pokwitowanie trafia do Keystore
 * przed wysłaniem wniosku; dane lokalne znikają dopiero po wiarygodnym `completed` ze statusu.
 */
@Singleton
class AccountDeletionRepository @Inject constructor(
    private val api: VocabularioApi,
    private val store: DeletionReceiptStore,
    private val sessionCoordinator: SessionCoordinator,
    private val authRepository: AuthRepository,
) {
    val receipt: StateFlow<DeletionReceipt?> get() = store.receipt

    /** Niewysłane operacje na tym urządzeniu; inne urządzenia nie są znane. */
    suspend fun unsentLocalCount(): Int = authRepository.ownerSnapshot().unsentCount

    suspend fun load(): DeletionReceipt? = store.load()

    suspend fun request(email: String, password: String): DeletionView =
        submitRequest(email, DELETION_METHOD_PASSWORD) {
            api.deletionProofPassword(DeletionProofRequest(email.trim(), password, "request"))
        }

    /** Konto bez hasła potwierdza wniosek kontem Google; adres trafia tylko do lokalnego pokwitowania. */
    suspend fun requestWithGoogle(email: String, provider: GoogleIdTokenProvider): DeletionView =
        submitRequest(email, DELETION_METHOD_GOOGLE) { googleProof("request", provider) }

    private suspend fun googleProof(action: String, provider: GoogleIdTokenProvider): DeletionProofResponse {
        val challenge = api.deletionGoogleChallenge(DeletionGoogleChallengeRequest(action))
        val idToken = provider.idToken(challenge.nonce)
        return api.deletionProofGoogle(DeletionGoogleProofRequest(challenge.challenge_id, idToken, action))
    }

    private suspend fun submitRequest(
        email: String,
        method: String,
        obtainProof: suspend () -> DeletionProofResponse,
    ): DeletionView {
        val owner = (sessionCoordinator.state.value as? SessionState.Active)?.ownerUserId
        val proof = obtainProof()
        if (owner == null || !proof.user_id.equals(owner, ignoreCase = true)) throw DeletionOwnerMismatchException()

        // Ponowienie po utracie odpowiedzi używa tego samego `request_id` i sekretu statusu.
        val receipt = store.load()?.takeIf { it.userId == proof.user_id && it.deletion == null }?.copy(method = method)
            ?: DeletionReceipt(UUID.randomUUID().toString(), newSecret32(), email.trim(), proof.user_id, method = method)
        store.save(receipt)
        val view = try {
            api.deletionRequest(DeletionRequestBody(receipt.requestId, proof.action_token, receipt.statusSecret))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            if (isDefinitiveRejection(e)) store.clear()
            throw e
        }
        // Zmiana trasy zamyka ekran, który to wywołał; reszta musi dojść do końca.
        withContext(NonCancellable) {
            store.save(receipt.copy(deletion = view))
            runCatching { sessionCoordinator.signOutLocally() }
        }
        return view
    }

    /** Bez pollingu: wywoływane przy wejściu na ekran i na przycisk. */
    suspend fun refreshStatus(): DeletionOutcome {
        val receipt = store.load() ?: return DeletionOutcome.None
        val view = try {
            api.deletionStatus(DeletionStatusRequest(receipt.requestId, receipt.statusSecret))
        } catch (e: HttpException) {
            if (e.code() == 404 && e.apiErrorCode() == "deletion_not_found" && receipt.deletion == null) {
                store.clear()
                return DeletionOutcome.None
            }
            throw e
        }
        return withContext(NonCancellable) {
            when (view.state) {
                DELETION_STATE_CANCELLED -> {
                    store.clear()
                    DeletionOutcome.Cancelled
                }
                DELETION_STATE_COMPLETED -> {
                    wipeLocalData(receipt.userId)
                    store.clear()
                    DeletionOutcome.Completed
                }
                else -> {
                    store.save(receipt.copy(deletion = view))
                    DeletionOutcome.Pending(view)
                }
            }
        }
    }

    suspend fun cancel(password: String) {
        val receipt = store.load() ?: return
        finishCancel(receipt, api.deletionProofPassword(DeletionProofRequest(receipt.email, password, "cancel")))
    }

    suspend fun cancelWithGoogle(provider: GoogleIdTokenProvider) {
        val receipt = store.load() ?: return
        finishCancel(receipt, googleProof("cancel", provider))
    }

    private suspend fun finishCancel(receipt: DeletionReceipt, proof: DeletionProofResponse) {
        if (!proof.user_id.equals(receipt.userId, ignoreCase = true)) throw DeletionOwnerMismatchException()
        val deletionId = proof.deletion_id ?: receipt.deletion?.deletion_id ?: throw DeletionOwnerMismatchException()
        val withCancelId = receipt.cancelRequestId?.let { receipt }
            ?: receipt.copy(cancelRequestId = UUID.randomUUID().toString()).also { store.save(it) }
        api.deletionCancel(DeletionCancelBody(deletionId, withCancelId.cancelRequestId!!, proof.action_token))
        store.clear()
    }

    /** Dane innego konta na urządzeniu zostają; usuwamy tylko to, co należało do usuniętego konta. */
    private suspend fun wipeLocalData(deletedUserId: String) {
        val snapshot = authRepository.ownerSnapshot()
        val owner = snapshot.ownerUserId
        if (owner != null && !owner.equals(deletedUserId, ignoreCase = true)) return
        authRepository.logout(LogoutConsent.DiscardConfirmed(snapshot.unsentFingerprint))
    }
}
