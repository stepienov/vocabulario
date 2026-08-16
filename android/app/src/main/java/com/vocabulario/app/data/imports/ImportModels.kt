package com.vocabulario.app.data.imports

import com.vocabulario.app.data.api.ImportJobItemResponse
import com.vocabulario.app.data.api.ImportJobProgressResponse
import kotlinx.serialization.Serializable

@Serializable
enum class ImportStatus {
    Idle,
    Queued,
    Analyzing,
    Review,
    Committing,
    Cancelling,
    Done,
    Failed,
    Cancelled,
    Error,
}

fun parseImportStatus(raw: String?): ImportStatus = when (raw?.lowercase()) {
    "queued" -> ImportStatus.Queued
    "analyzing" -> ImportStatus.Analyzing
    "review" -> ImportStatus.Review
    "committing" -> ImportStatus.Committing
    "cancelling" -> ImportStatus.Cancelling
    "done" -> ImportStatus.Done
    "failed" -> ImportStatus.Failed
    "cancelled" -> ImportStatus.Cancelled
    else -> ImportStatus.Error
}

@Serializable
data class ImportJobState(
    val status: ImportStatus = ImportStatus.Idle,
    val jobId: String? = null,
    val sourceName: String? = null,
    val mode: String = "vocabulario",
    val targetListId: String? = null,
    val targetListName: String? = null,
    val stage: String = "queued",
    val processed: Int = 0,
    val total: Int = 0,
    val currentLabel: String? = null,
    val currentAttempt: Int = 0,
    val readyCount: Int = 0,
    val duplicateCount: Int = 0,
    val failedCount: Int = 0,
    val createdCount: Int = 0,
    val items: List<ImportJobItemResponse> = emptyList(),
    val result: ImportResult? = null,
    val error: String? = null,
    val notice: String? = null,
    val showAbortConfirm: Boolean = false,
    val expandedSection: String? = null,
) {
    val busy: Boolean
        get() = status == ImportStatus.Queued ||
            status == ImportStatus.Analyzing ||
            status == ImportStatus.Committing ||
            status == ImportStatus.Cancelling

    val blocksUi: Boolean
        get() = busy || status == ImportStatus.Review

    val showOutcome: Boolean
        get() = status == ImportStatus.Done ||
            status == ImportStatus.Failed ||
            status == ImportStatus.Cancelled ||
            status == ImportStatus.Error

    val readyItems: List<ImportJobItemResponse>
        get() = items.filter { it.verdict == "ready" }.sortedWith(importLemmaComparator)

    val duplicateItems: List<ImportJobItemResponse>
        get() = items.filter { it.verdict == "duplicate" }.sortedWith(importLemmaComparator)

    val failedItems: List<ImportJobItemResponse>
        get() = items.filter { it.verdict == "failed" }.sortedWith(importLemmaComparator)

    val errorClipboard: String
        get() = failedItems
            .sortedBy { it.ordinal }
            .mapNotNull { it.lemma?.takeIf(String::isNotBlank) ?: it.input_label.takeIf(String::isNotBlank) }
            .joinToString("; ")
}

@Serializable
data class ImportResult(
    val created: Int = 0,
    val duplicates: Int = 0,
    val failed: Int = 0,
)

fun ImportJobProgressResponse.toState(
    previous: ImportJobState = ImportJobState(),
    includeItems: Boolean = true,
): ImportJobState {
    val parsed = parseImportStatus(status)
    val nextItems = if (includeItems && items.isNotEmpty()) items else previous.items
    return previous.copy(
        status = parsed,
        jobId = job_id,
        sourceName = normalizeImportSourceName(source_name) ?: previous.sourceName,
        mode = mode,
        targetListId = list_id ?: previous.targetListId,
        targetListName = list_name ?: previous.targetListName,
        stage = stage,
        processed = processed,
        total = total,
        currentLabel = current_label,
        currentAttempt = current_attempt,
        readyCount = ready_count,
        duplicateCount = duplicate_count,
        failedCount = failed_count,
        createdCount = created_count,
        items = nextItems,
        result = if (parsed == ImportStatus.Done) {
            ImportResult(created = created_count, duplicates = duplicate_count, failed = failed_count)
        } else {
            previous.result
        },
        error = error_message ?: previous.error,
        showAbortConfirm = previous.showAbortConfirm,
        expandedSection = previous.expandedSection,
    )
}

private val IMPORT_ARTICLES = setOf(
    "el", "la", "los", "las",
    "le", "les", "un", "une",
    "der", "die", "das", "ein", "eine",
    "the", "a", "an",
    "il", "lo", "i", "gli",
    "o", "os", "as",
)

fun importSortKey(lemma: String?): String {
    val raw = lemma?.trim().orEmpty()
    if (raw.isEmpty()) return ""
    val lower = raw.lowercase()
    val parts = lower.split(Regex("\\s+"))
    val rest = if (parts.size > 1 && parts[0] in IMPORT_ARTICLES) {
        parts.drop(1).joinToString(" ")
    } else {
        lower
    }
    return rest.removePrefix("l'").removePrefix("l’")
}

val importLemmaComparator: Comparator<ImportJobItemResponse> =
    compareBy<ImportJobItemResponse> {
        importSortKey(it.lemma?.takeIf(String::isNotBlank) ?: it.input_label)
    }.thenBy { it.ordinal }

fun normalizeImportSourceName(raw: String?): String? {
    val name = raw?.trim().orEmpty()
    if (name.isEmpty()) return null
    if (name.equals("paste", ignoreCase = true) || name.equals("Wklejka", ignoreCase = true)) {
        return "paste"
    }
    return name
}

fun isPasteImportSource(raw: String?): Boolean =
    normalizeImportSourceName(raw) == "paste"
