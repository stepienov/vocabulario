package com.vocabulario.app.notifications

import android.content.Context
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
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
    private val prefs = context.getSharedPreferences("vocabulario_reminder", Context.MODE_PRIVATE)

    fun reminderMinute(): Int = prefs.getInt(KEY_MINUTE, 0).coerceIn(0, 59)

    fun scheduleStudyReminder(hour: Int, enabled: Boolean, minute: Int = reminderMinute()) {
        val safeHour = hour.coerceIn(0, 23)
        val safeMinute = minute.coerceIn(0, 59)
        prefs.edit()
            .putInt(KEY_HOUR, safeHour)
            .putInt(KEY_MINUTE, safeMinute)
            .putBoolean(KEY_ENABLED, enabled)
            .apply()
        if (!enabled) {
            workManager.cancelUniqueWork(STUDY_WORK)
            return
        }
        val now = Calendar.getInstance()
        val target = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, safeHour)
            set(Calendar.MINUTE, safeMinute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (timeInMillis <= now.timeInMillis) add(Calendar.DAY_OF_YEAR, 1)
        }
        val delayMs = (target.timeInMillis - now.timeInMillis).coerceAtLeast(1L)
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
        val request = PeriodicWorkRequestBuilder<EnrichmentCheckWorker>(15, TimeUnit.MINUTES).build()
        workManager.enqueueUniquePeriodicWork(
            ENRICHMENT_WORK,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    fun scheduleEnrichmentSoon() {
        val request = OneTimeWorkRequestBuilder<EnrichmentCheckWorker>()
            .setInitialDelay(12, TimeUnit.SECONDS)
            .build()
        workManager.enqueueUniqueWork(
            ENRICHMENT_SOON,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    companion object {
        private const val STUDY_WORK = "vocabulario_study_reminder"
        private const val ENRICHMENT_WORK = "vocabulario_enrichment_check"
        private const val ENRICHMENT_SOON = "vocabulario_enrichment_soon"
        private const val KEY_HOUR = "hour"
        private const val KEY_MINUTE = "minute"
        private const val KEY_ENABLED = "enabled"
    }
}
