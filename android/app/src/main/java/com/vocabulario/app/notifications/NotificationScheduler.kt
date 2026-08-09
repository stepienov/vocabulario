package com.vocabulario.app.notifications

import android.content.Context
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.Calendar
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NotificationScheduler @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val workManager get() = WorkManager.getInstance(context)

    fun scheduleStudyReminder(hour: Int, enabled: Boolean) {
        if (!enabled) {
            workManager.cancelUniqueWork(STUDY_WORK)
            return
        }
        val now = Calendar.getInstance()
        val target = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour.coerceIn(0, 23))
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (timeInMillis <= now.timeInMillis) add(Calendar.DAY_OF_YEAR, 1)
        }
        val delayMs = target.timeInMillis - now.timeInMillis
        val request = PeriodicWorkRequestBuilder<StudyReminderWorker>(24, TimeUnit.HOURS)
            .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
            .build()
        workManager.enqueueUniquePeriodicWork(
            STUDY_WORK,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    fun scheduleEnrichmentCheck() {
        val request = PeriodicWorkRequestBuilder<EnrichmentCheckWorker>(30, TimeUnit.MINUTES).build()
        workManager.enqueueUniquePeriodicWork(
            ENRICHMENT_WORK,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    companion object {
        private const val STUDY_WORK = "vocabulario_study_reminder"
        private const val ENRICHMENT_WORK = "vocabulario_enrichment_check"
    }
}
