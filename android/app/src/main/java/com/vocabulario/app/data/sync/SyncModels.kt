package com.vocabulario.app.data.sync

import com.vocabulario.app.data.api.LanguageProfileResponse
import com.vocabulario.app.data.session.OwnerContext

/** Zakres jednego przebiegu: widoczny profil albo wszystkie profile z niewysłaną pracą (logout). */
enum class SyncScope { ACTIVE_PROFILE, ALL_PENDING_PROFILES }

enum class SyncPhase { LOOKUPS, OUTBOX, PUSH, PROFILES, PULL }

enum class FailureKind { OFFLINE, AUTH, VERIFICATION, LEGAL, UPDATE_REQUIRED, RATE_LIMITED, SERVER, CLIENT, PROTOCOL, CURSOR_EXPIRED }

/** Przyczyna bez treści użytkownika; [code] to kod API albo techniczny kod klienta. */
data class SyncFailure(
    val kind: FailureKind,
    val code: String,
    val retryable: Boolean,
    val retryAfterSec: Long? = null,
)

private val AUTH_CODES = setOf(
    "not_authenticated",
    "invalid_token",
    "invalid_refresh_token",
    "session_revoked",
    "session_expired",
    "session_upgrade_required",
    "restore_recovery_required",
)

const val CODE_LEGAL_ACCEPTANCE_REQUIRED = "terms_acceptance_required"

/** Zarezerwowany typ outboxu z F-007/T-002; liczony w QueueSnapshot, nigdy po cichu pomijany. */
const val OP_CONTENT_REPORT = "content_report"

/** Trwałe intenty profilu (F-003/T-004): edycja pól i wybór aktywnej pary; payload zawiera `profileId`. */
const val OP_PROFILE_UPDATE = "profile_update"
const val OP_PROFILE_ACTIVATE = "profile_activate"

/** Czysta klasyfikacja; [transport] oznacza błąd sieci/timeout, nie pewność braku Internetu. */
fun classifyFailure(
    status: Int?,
    apiCode: String?,
    retryAfterSec: Long? = null,
    transport: Boolean = false,
): SyncFailure {
    val code = apiCode?.trim()?.lowercase()?.takeIf { it.isNotEmpty() }
    if (transport) return SyncFailure(FailureKind.OFFLINE, code ?: "network", retryable = true)
    return when {
        status == null -> SyncFailure(FailureKind.CLIENT, code ?: "unexpected", retryable = false)
        // 426 nie jest błędem pracy: nic nie blokujemy ani nie ponawiamy, kolejka czeka na aktualizację.
        status == 426 -> SyncFailure(FailureKind.UPDATE_REQUIRED, code ?: "app_update_required", retryable = false)
        status == 401 || code in AUTH_CODES ->
            SyncFailure(FailureKind.AUTH, code ?: "unauthorized", retryable = false)
        status == 403 && code == "email_verification_required" ->
            SyncFailure(FailureKind.VERIFICATION, code, retryable = false)
        code == CODE_LEGAL_ACCEPTANCE_REQUIRED ->
            SyncFailure(FailureKind.LEGAL, code, retryable = false)
        status == 410 && code == "sync_cursor_expired" ->
            SyncFailure(FailureKind.CURSOR_EXPIRED, code, retryable = true)
        status == 429 -> SyncFailure(FailureKind.RATE_LIMITED, code ?: "rate_limited", true, retryAfterSec)
        status == 408 || status >= 500 ->
            SyncFailure(FailureKind.SERVER, code ?: "server_$status", true, retryAfterSec)
        else -> SyncFailure(FailureKind.CLIENT, code ?: "http_$status", retryable = false)
    }
}

sealed interface PhaseOutcome {
    object Ok : PhaseOutcome

    /** Faza nie była potrzebna (np. profile już znane); nie obniża wyniku. */
    object NotNeeded : PhaseOutcome

    /** Faza przerwana wcześniejszą awarią; nigdy nie udaje sukcesu. */
    data class NotRun(val reason: String) : PhaseOutcome

    data class Failed(val failure: SyncFailure) : PhaseOutcome
}

/** Stan kolejek wszystkich profili z jednego spójnego odczytu Room. */
data class QueueSnapshot(
    val reviews: Int = 0,
    val moves: Int = 0,
    val undos: Int = 0,
    val lookupsQueued: Int = 0,
    val lookupsNeedsReview: Int = 0,
    val outboxPending: Int = 0,
    val outboxParked: Int = 0,
    val outboxBlocked: Int = 0,
    val contentReports: Int = 0,
    val blockedReviews: Int = 0,
    val blockedMoves: Int = 0,
    val blockedUndos: Int = 0,
) {
    val total: Int
        get() = reviews + moves + undos + lookupsQueued + lookupsNeedsReview +
            outboxPending + outboxParked + outboxBlocked + contentReports

    /** Wymaga decyzji użytkownika lub poprawki; automatyczne ponawianie nic nie zmieni. */
    val blocked: Int
        get() = blockedReviews + blockedMoves + blockedUndos + outboxBlocked + outboxParked

    /** Praca, którą kolejny przebieg może jeszcze wysłać. */
    val waiting: Int
        get() = (total - blocked - lookupsNeedsReview).coerceAtLeast(0)

    /** Nierozwiązana praca sync; stub „do sprawdzenia" czeka na użytkownika, nie na sieć. */
    val unresolved: Int
        get() = total - lookupsNeedsReview
}

data class SyncReport(
    val owner: OwnerContext?,
    val scope: SyncScope,
    val startedAt: Long,
    val finishedAt: Long,
    val phases: Map<SyncPhase, PhaseOutcome>,
    val pullByProfile: Map<String, PhaseOutcome>,
    val sent: Int,
    val confirmed: Int,
    val queue: QueueSnapshot,
    val supersededReviews: Int = 0,
)

sealed interface SyncResult {
    data class Complete(val report: SyncReport) : SyncResult

    data class Partial(
        val report: SyncReport,
        val retryable: Boolean,
        val retryAfterSec: Long? = null,
    ) : SyncResult

    data class Offline(val report: SyncReport) : SyncResult

    /** Drugi sync już trwa; to nie jest ani sukces, ani awaria. */
    object Busy : SyncResult

    data class AuthRequired(val report: SyncReport) : SyncResult

    data class VerificationRequired(val report: SyncReport) : SyncResult

    data class LegalAcceptanceRequired(val report: SyncReport) : SyncResult

    /** Serwer wymaga nowszej wersji aplikacji; praca i sesja zostają bez zmian. */
    data class UpdateRequired(val report: SyncReport) : SyncResult

    data class Failed(
        val report: SyncReport,
        val code: String,
        val retryable: Boolean,
        val retryAfterSec: Long? = null,
    ) : SyncResult

    /** Inny właściciel lub generacja; praca porzucona bez zapisu. */
    object Superseded : SyncResult
}

/** Czy WorkManager ma ponowić pracę (z backoffem); auth/weryfikacja/konflikt czekają na użytkownika. */
val SyncResult.shouldRetry: Boolean
    get() = when (this) {
        is SyncResult.Offline -> true
        is SyncResult.Partial -> retryable
        is SyncResult.Failed -> retryable
        else -> false
    }

val SyncResult.retryAfterSec: Long?
    get() = when (this) {
        is SyncResult.Partial -> retryAfterSec
        is SyncResult.Failed -> retryAfterSec
        else -> null
    }

enum class WorkerDecision { SUCCESS, RETRY, FAILURE }

/**
 * Wynik dla WorkManagera: ponawiamy tylko to, co może się poprawić samo, w limicie prób;
 * auth, weryfikacja, zgody, konflikty i Busy kończą się bez ponawiania (kolejka zostaje nietknięta).
 */
fun SyncResult.workerDecision(runAttemptCount: Int, maxRetries: Int = 4): WorkerDecision = when {
    shouldRetry -> if (runAttemptCount >= maxRetries) WorkerDecision.FAILURE else WorkerDecision.RETRY
    this is SyncResult.Failed -> WorkerDecision.FAILURE
    else -> WorkerDecision.SUCCESS
}

/** Wynik wyliczany wyłącznie z raportu; brak błędu i pusta kolejka bez pull nie dają Complete. */
fun evaluateSyncResult(report: SyncReport): SyncResult {
    val outcomes = report.phases.values + report.pullByProfile.values
    val failures = outcomes.filterIsInstance<PhaseOutcome.Failed>().map { it.failure }
    failures.firstOrNull { it.kind == FailureKind.AUTH }?.let { return SyncResult.AuthRequired(report) }
    failures.firstOrNull { it.kind == FailureKind.VERIFICATION }?.let { return SyncResult.VerificationRequired(report) }
    failures.firstOrNull { it.kind == FailureKind.LEGAL }?.let { return SyncResult.LegalAcceptanceRequired(report) }
    failures.firstOrNull { it.kind == FailureKind.UPDATE_REQUIRED }?.let { return SyncResult.UpdateRequired(report) }

    val allRan = outcomes.none { it is PhaseOutcome.NotRun }
    val pullOk = report.pullByProfile.isNotEmpty() &&
        report.pullByProfile.values.all { it is PhaseOutcome.Ok }
    if (failures.isEmpty()) {
        return if (allRan && pullOk && report.queue.unresolved == 0) {
            SyncResult.Complete(report)
        } else {
            SyncResult.Partial(report, retryable = report.queue.waiting > 0 || !allRan || !pullOk)
        }
    }

    val progressed = report.confirmed > 0 || report.pullByProfile.values.any { it is PhaseOutcome.Ok }
    if (!progressed && failures.all { it.kind == FailureKind.OFFLINE }) return SyncResult.Offline(report)
    val retryAfter = failures.mapNotNull { it.retryAfterSec }.maxOrNull()
    val retryable = failures.any { it.retryable }
    if (progressed) return SyncResult.Partial(report, retryable, retryAfter)
    val first = failures.first()
    return SyncResult.Failed(report, first.code, retryable, retryAfter)
}

/** Wynik rozpoznania profili; pusta lista z błędu nigdy nie jest ConfirmedEmpty. */
sealed interface ProfileResolution {
    enum class Source { CACHE, SERVER }

    data class Found(
        val profiles: List<LanguageProfileResponse>,
        val activeId: String?,
        val source: Source,
    ) : ProfileResolution

    /** Wyłącznie poprawne 200 z pustą listą dla bieżącego kontekstu. */
    object ConfirmedEmpty : ProfileResolution

    data class Unavailable(val cause: SyncFailure, val hasCache: Boolean) : ProfileResolution

    data class AuthRequired(val reason: String) : ProfileResolution

    object VerificationRequired : ProfileResolution

    object LegalAcceptanceRequired : ProfileResolution

    object Superseded : ProfileResolution
}

/** Onboarding tylko po potwierdzeniu, że konto nie ma profilu. */
val ProfileResolution.needsOnboarding: Boolean
    get() = this is ProfileResolution.ConfirmedEmpty

/** Zamienia błąd pobrania listy profili na zamknięty wynik. */
fun resolveProfileFailure(failure: SyncFailure, hasCache: Boolean): ProfileResolution = when (failure.kind) {
    FailureKind.AUTH -> ProfileResolution.AuthRequired(failure.code)
    FailureKind.VERIFICATION -> ProfileResolution.VerificationRequired
    FailureKind.LEGAL -> ProfileResolution.LegalAcceptanceRequired
    else -> ProfileResolution.Unavailable(failure, hasCache)
}

/** Wynik serwera dla jednej operacji push. */
data class OpAck(val clientId: String, val outcome: String, val reason: String?)

sealed interface AckDecision {
    /** [blocked] mapuje ID → przyczynę; pozostałe potwierdzone ID można zdjąć z kolejki. */
    data class Valid(val confirmed: List<String>, val blocked: Map<String, String>) : AckDecision

    /** Brak, duplikat lub obce ID albo nieznany outcome; żaden wiersz nie jest zdejmowany. */
    data class ProtocolError(val code: String) : AckDecision
}

private val CONFIRMING_OUTCOMES = setOf("applied", "duplicate", "superseded")
private val BLOCKING_OUTCOMES = setOf("not_found", "conflict")

/**
 * Dokładnie jeden wynik na każde wysłane ID. Odpowiedź starego serwera (null) nie dowodzi
 * zapisu, więc nic nie jest potwierdzone.
 */
fun interpretAck(sentIds: List<String>, results: List<OpAck>?): AckDecision {
    if (sentIds.isEmpty()) return AckDecision.Valid(emptyList(), emptyMap())
    if (results == null) return AckDecision.ProtocolError("ack_missing")
    val expected = sentIds.toSet()
    if (expected.size != sentIds.size) return AckDecision.ProtocolError("ack_duplicate_sent_id")
    val seen = HashSet<String>()
    val confirmed = mutableListOf<String>()
    val blocked = linkedMapOf<String, String>()
    for (item in results) {
        if (item.clientId !in expected) return AckDecision.ProtocolError("ack_unknown_id")
        if (!seen.add(item.clientId)) return AckDecision.ProtocolError("ack_duplicate_id")
        when (item.outcome) {
            in CONFIRMING_OUTCOMES -> confirmed += item.clientId
            in BLOCKING_OUTCOMES -> blocked[item.clientId] = item.reason ?: item.outcome
            else -> return AckDecision.ProtocolError("ack_unknown_outcome")
        }
    }
    if (seen.size != expected.size) return AckDecision.ProtocolError("ack_missing_id")
    return AckDecision.Valid(confirmed, blocked)
}

/** Wynik jednej operacji outboxu; nieznany typ i wadliwy JSON to Blocked, nigdy ACK. */
sealed interface OutboxStep {
    object Applied : OutboxStep

    object AlreadyApplied : OutboxStep

    /** Zależność (np. create listy) jeszcze nie zakończona; kolejne operacje tej listy czekają. */
    data class Deferred(val dependency: String) : OutboxStep

    data class Blocked(val code: String) : OutboxStep
}

enum class BlockedKind { REVIEW, MOVE, UNDO, OUTBOX }

internal fun canOverlayLocalSrs(localGeneration: Long, serverGeneration: Long): Boolean =
    localGeneration == serverGeneration

/** Zablokowana operacja kolejki (id to clientId, a dla outboxu numer seq) z kodem przyczyny. */
data class BlockedItem(
    val kind: BlockedKind,
    val id: String,
    val reason: String,
    /** Dla outboxu: typ operacji i profil, żeby UI dobrało etykietę i dostępne akcje. */
    val type: String? = null,
    val profileId: String? = null,
)
