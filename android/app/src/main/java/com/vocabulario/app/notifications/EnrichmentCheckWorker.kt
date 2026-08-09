package com.vocabulario.app.notifications

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

@HiltWorker
class EnrichmentCheckWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val repository: LearningRepository,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!repository.hasSyncableSession()) return Result.success()
        return try {
            val settings = repository.getSettings()
            if (!settings.cards_ready_push_enabled) return Result.success()
            val pendingBefore = repository.listCards().count { it.enrichment_status == "pending" }
            if (pendingBefore == 0) return Result.success()
            repository.syncNow(fullReplace = false)
            val pendingAfter = repository.listCards().count { it.enrichment_status == "pending" }
            val becameReady = pendingBefore - pendingAfter
            if (becameReady > 0) {
                NotificationHelper.showCardsReady(applicationContext, becameReady)
            }
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
