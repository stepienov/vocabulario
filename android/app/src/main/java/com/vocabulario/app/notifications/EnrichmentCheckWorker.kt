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
    private val tracker: ReadyBatchTracker,
    private val scheduler: NotificationScheduler,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!repository.hasSyncableSession()) return Result.success()
        return try {
            val settings = repository.getSettings()
            val on = settings.study_reminder_enabled || settings.cards_ready_push_enabled
            if (!on) return Result.success()
            repository.syncNow(fullReplace = false)
            repository.evaluateReadyBatches()
            if (tracker.hasWatches()) scheduler.scheduleEnrichmentSoon()
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
