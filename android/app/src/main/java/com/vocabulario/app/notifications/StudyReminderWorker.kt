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
        return try {
            val settings = runCatching { repository.getSettings() }.getOrNull()
            if (settings?.study_reminder_enabled != true) return Result.success()
            val due = runCatching { repository.getQueue().due.size }.getOrDefault(0)
            NotificationHelper.showStudyReminder(applicationContext, due)
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
