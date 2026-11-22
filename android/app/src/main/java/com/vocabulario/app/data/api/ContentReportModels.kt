package com.vocabulario.app.data.api

import kotlinx.serialization.Serializable

/** Zgłoszenie treści (F-007/T-002); treść wysyłana jest dokładnie taka, jaką użytkownik widział w podglądzie. */
@Serializable
data class ContentReportRequest(
    val client_report_id: String,
    val profile_id: String,
    val target_kind: String,
    val target_id: String? = null,
    val field: String,
    val reason: String,
    val excerpt: String,
    val note: String? = null,
    val app_version: String? = null,
)

@Serializable
data class ContentReportReceipt(
    val report_id: String,
    val status: String,
    val received_at: String = "",
    val resolution_code: String? = null,
)

object ReportReason {
    const val INCORRECT = "incorrect"
    const val OFFENSIVE = "offensive"
    const val PRIVACY = "privacy"
    const val OTHER = "other"
    val all = listOf(INCORRECT, OFFENSIVE, PRIVACY, OTHER)
}

object ReportLimits {
    const val EXCERPT_MAX = 4000
    const val NOTE_MAX = 1000
}
