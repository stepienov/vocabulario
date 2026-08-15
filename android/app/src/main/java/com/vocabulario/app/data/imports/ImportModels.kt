package com.vocabulario.app.data.imports

import com.vocabulario.app.data.api.ImportDisplayCard
import com.vocabulario.app.data.api.ImportValidWord
import kotlinx.serialization.Serializable

@Serializable
enum class ImportStatus {
    Idle,
    Processing,
    Review,
    Committing,
    Done,
    Error,
}

@Serializable
data class ImportResult(
    val created: Int = 0,
    val duplicates: Int = 0,
    val failed: Int = 0,
)

@Serializable
data class ImportJobState(
    val status: ImportStatus = ImportStatus.Idle,
    val sourceName: String? = null,
    val mode: String = "vocabulario",
    val targetListId: String? = null,
    val targetListName: String? = null,
    val processed: Int = 0,
    val total: Int = 0,
    val valid: List<ImportValidWord> = emptyList(),
    val displayCards: List<ImportDisplayCard> = emptyList(),
    val invalid: List<String> = emptyList(),
    val deselectedKeys: Set<String> = emptySet(),
    val result: ImportResult? = null,
    val error: String? = null,
    /** UI-only; not restored from DataStore. */
    val showAbortConfirm: Boolean = false,
) {
    val busy: Boolean
        get() = status == ImportStatus.Processing || status == ImportStatus.Committing

    val selectedCount: Int
        get() = when (mode) {
            "preserve" -> displayCards.count { it.key !in deselectedKeys }
            else -> valid.count { it.input !in deselectedKeys }
        }

    val selectedValid: List<ImportValidWord>
        get() = valid.filter { it.input !in deselectedKeys }

    val selectedDisplayCards: List<ImportDisplayCard>
        get() = displayCards.filter { it.key !in deselectedKeys }
}
