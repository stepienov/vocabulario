package com.vocabulario.app.data

import com.vocabulario.app.BuildConfig
import com.vocabulario.app.data.api.ContentReportReceipt
import com.vocabulario.app.data.api.ContentReportRequest
import com.vocabulario.app.data.api.ReportLimits
import com.vocabulario.app.data.api.VocabularioApi
import com.vocabulario.app.data.api.apiErrorCode
import com.vocabulario.app.data.local.OfflineStore
import com.vocabulario.app.data.sync.OP_CONTENT_REPORT
import com.vocabulario.app.data.sync.OutboxStep
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/** Szkic zgłoszenia: pola wybrane przez użytkownika i tekst pokazany w podglądzie. */
data class ContentReportDraft(
    val profileId: String,
    val targetKind: String,
    val targetId: String?,
    val field: String,
    val reason: String,
    val excerpt: String,
    val note: String?,
)

sealed interface ReportSubmitResult {
    data class Sent(val receipt: ContentReportReceipt) : ReportSubmitResult

    /** Zapisane na tym urządzeniu, jeszcze nie wysłane; można ponowić albo anulować. */
    data class Queued(val reportId: String) : ReportSubmitResult

    /** Serwer odrzucił zgłoszenie na stałe (np. cel nie istnieje); nic nie zostaje w kolejce. */
    data class Rejected(val reportId: String, val code: String) : ReportSubmitResult
}

/**
 * Zgłoszenia treści idą przez outbox: szkic z `client_report_id` zapisuje się w Room przed
 * pierwszym żądaniem, a payload nie zmienia się przy kolejnych próbach (idempotencja po stronie serwera).
 */
@Singleton
class ContentReportRepository @Inject constructor(
    private val api: VocabularioApi,
    private val offlineStore: OfflineStore,
    private val networkMonitor: NetworkMonitor,
) {
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun submit(draft: ContentReportDraft): ReportSubmitResult {
        val reportId = UUID.randomUUID().toString()
        val payload = json.encodeToString(ContentReportRequest.serializer(), requestFor(draft, reportId))
        offlineStore.enqueueOp(OP_CONTENT_REPORT, payload, reportId)
        return sendQueued(reportId)
    }

    /** Ponowna próba tego samego, niezmienionego zgłoszenia. */
    suspend fun retry(reportId: String): ReportSubmitResult = sendQueued(reportId)

    suspend fun cancel(reportId: String) = offlineStore.removeOpByClientId(reportId)

    suspend fun status(reportId: String): ContentReportReceipt? =
        runCatching { withTimeout(SUBMIT_TIMEOUT_MS) { api.contentReportStatus(reportId) } }.getOrNull()

    private suspend fun sendQueued(reportId: String): ReportSubmitResult {
        val op = offlineStore.opByClientId(reportId) ?: return ReportSubmitResult.Rejected(reportId, "gone")
        if (!networkMonitor.isCurrentlyOnline()) return ReportSubmitResult.Queued(reportId)
        return try {
            val receipt = deliver(op.payloadJson)
            offlineStore.removeOpByClientId(reportId)
            ReportSubmitResult.Sent(receipt)
        } catch (e: HttpException) {
            val code = e.apiErrorCode()
            if (isPermanentRejection(e.code())) {
                offlineStore.removeOpByClientId(reportId)
                ReportSubmitResult.Rejected(reportId, code ?: "http_${e.code()}")
            } else {
                ReportSubmitResult.Queued(reportId)
            }
        } catch (e: IOException) {
            ReportSubmitResult.Queued(reportId)
        } catch (e: CancellationException) {
            if (e is TimeoutCancellationException) ReportSubmitResult.Queued(reportId) else throw e
        }
    }

    /** Wysyłka z kolejki w tle: błąd przejściowy nie blokuje reszty outboxu, błąd trwały usuwa zgłoszenie. */
    suspend fun deliverForOutbox(payloadJson: String): OutboxStep =
        try {
            deliver(payloadJson)
            OutboxStep.Applied
        } catch (e: HttpException) {
            if (isPermanentRejection(e.code())) OutboxStep.AlreadyApplied else OutboxStep.Deferred(OP_CONTENT_REPORT)
        } catch (e: IOException) {
            OutboxStep.Deferred(OP_CONTENT_REPORT)
        } catch (e: CancellationException) {
            if (e is TimeoutCancellationException) OutboxStep.Deferred(OP_CONTENT_REPORT) else throw e
        }

    private suspend fun deliver(payloadJson: String): ContentReportReceipt {
        val body = json.decodeFromString(ContentReportRequest.serializer(), payloadJson)
        return withTimeout(SUBMIT_TIMEOUT_MS) { api.createContentReport(body) }
    }

    private companion object {
        const val SUBMIT_TIMEOUT_MS = 15_000L
    }
}

/** 4xx poza bramkami i limitami (401/403/408/429) nie zmieni się przy ponowieniu: brak celu, konflikt, błędne dane. */
internal fun isPermanentRejection(status: Int): Boolean =
    status in 400..499 && status != 401 && status != 403 && status != 408 && status != 429

internal fun requestFor(draft: ContentReportDraft, reportId: String): ContentReportRequest =
    ContentReportRequest(
        client_report_id = reportId,
        profile_id = draft.profileId,
        target_kind = draft.targetKind,
        target_id = draft.targetId,
        field = draft.field,
        reason = draft.reason,
        excerpt = draft.excerpt.trim().take(ReportLimits.EXCERPT_MAX),
        note = draft.note?.trim()?.takeIf { it.isNotEmpty() }?.take(ReportLimits.NOTE_MAX),
        app_version = BuildConfig.VERSION_NAME.take(32),
    )
