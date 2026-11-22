package com.vocabulario.app.data

import android.content.Context
import com.vocabulario.app.data.api.LegalAcceptanceBody
import com.vocabulario.app.data.api.LegalManifest
import com.vocabulario.app.data.api.LegalStatus
import com.vocabulario.app.data.api.UserResponse
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.SessionCoordinator
import com.vocabulario.app.data.session.SessionState
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import retrofit2.HttpException
import java.io.IOException
import java.util.concurrent.ConcurrentHashMap
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Stan bramki akceptacji warunków (F-007/T-003). Jak [EmailVerificationGate] nie zależy od API,
 * więc interceptor OkHttp może go ustawić po 403 `terms_acceptance_required`.
 */
@Singleton
class LegalGate @Inject constructor(
    private val tokenStore: TokenStore,
    private val sessionCoordinator: SessionCoordinator,
) {
    val required: Flow<Boolean> =
        combine(tokenStore.legalRequiredOwner, sessionCoordinator.state, ::verificationRequiredFor)
            .distinctUntilChanged()

    fun isRequired(): Boolean =
        verificationRequiredFor(tokenStore.legalRequiredOwner.value, sessionCoordinator.state.value)

    fun onServerRequired() {
        val state = sessionCoordinator.state.value as? SessionState.Active ?: return
        state.ownerUserId?.let { tokenStore.setLegalRequiredOwner(it) }
    }

    /** Odpowiedź `/me` innego właściciela niż obecny (spóźniona po zmianie konta) jest pomijana. */
    fun apply(me: UserResponse) {
        val status = me.legal_status ?: return
        val owner = (sessionCoordinator.state.value as? SessionState.Active)?.ownerUserId
        if (owner != null && owner != me.id) return
        tokenStore.setLegalRequiredOwner(me.id.takeIf { status.acceptance_required })
    }

    fun onAccepted() = tokenStore.setLegalRequiredOwner(null)
}

/** Manifest dokumentów z ETag (bez pollingu) i akceptacja aktualnej wersji. */
@Singleton
class LegalRepository @Inject constructor(
    @ApplicationContext context: Context,
    private val api: VocabularioApi,
    private val tokenStore: TokenStore,
    private val gate: LegalGate,
) {
    private val cache = ConcurrentHashMap<String, Pair<String, LegalManifest>>()
    private val prefs = context.getSharedPreferences("vocabulario_support", Context.MODE_PRIVATE)

    /** Adres wsparcia z ostatniego manifestu; zostaje na urządzeniu, żeby pomoc działała offline. */
    fun supportEmail(): String? = prefs.getString(KEY_SUPPORT_EMAIL, null)?.takeIf { it.isNotBlank() }

    suspend fun manifest(): LegalManifest {
        val locale = tokenStore.mailLocale()
        val cached = cache[locale]
        val response = api.legalCurrent(locale, cached?.first)
        if (response.code() == 304 && cached != null) return cached.second
        if (!response.isSuccessful) throw HttpException(response)
        val body = response.body() ?: throw IOException("empty legal manifest")
        response.headers()["ETag"]?.let { cache[locale] = it to body }
        prefs.edit().putString(KEY_SUPPORT_EMAIL, body.support_email).apply()
        return body
    }

    /** Odświeża adres wsparcia po cichu; błąd sieci zostawia ostatnią znaną wartość. */
    suspend fun refreshSupportEmail(): String? {
        runCatching { manifest() }
        return supportEmail()
    }

    suspend fun accept(manifest: LegalManifest): LegalStatus {
        val status = api.acceptLegal(acceptanceFor(manifest))
        gate.onAccepted()
        return status
    }

    private companion object {
        const val KEY_SUPPORT_EMAIL = "support_email"
    }
}

/** Oświadczenie o wieku i warunki są potwierdzane osobno; tu obie zgody są już zaznaczone. */
fun acceptanceFor(manifest: LegalManifest): LegalAcceptanceBody =
    LegalAcceptanceBody(manifest.terms_version, manifest.locale, adult_confirmed = true)

/** Adres publicznej strony (np. `/privacy`) z bazowego URL API zakończonego `/api/v1/`. */
fun publicSiteUrl(apiBase: String, path: String): String =
    apiBase.trimEnd('/').removeSuffix("/api/v1") + path
