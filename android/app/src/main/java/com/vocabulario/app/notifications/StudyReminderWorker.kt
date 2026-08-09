package com.vocabulario.app.notifications

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

@HiltWorker
class StudyReminderWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val repository: LearningRepository,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!repository.hasSyncableSession()) return Result.success()
        return try {
            val settings = repository.getSettings()
            if (!settings.study_reminder_enabled) return Result.success()
            val queue = repository.getQueue()
            val due = queue.due.size
            if (due > 0) {
                NotificationHelper.showStudyReminder(applicationContext, due)
            }
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
