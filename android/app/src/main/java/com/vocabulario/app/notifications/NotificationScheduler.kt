package com.vocabulario.app.notifications

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.vocabulario.app.MainActivity
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
    private val alarmManager get() = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager

    fun reminderHour(): Int = prefs.getInt(KEY_HOUR, 19).coerceIn(0, 23)

    fun reminderMinute(): Int = prefs.getInt(KEY_MINUTE, 0).coerceIn(0, 59)

    fun reminderEnabled(): Boolean = prefs.getBoolean(KEY_ENABLED, false)

    fun scheduleStudyReminder(hour: Int, enabled: Boolean, minute: Int = reminderMinute()) {
        val safeHour = hour.coerceIn(0, 23)
        val safeMinute = minute.coerceIn(0, 59)
        prefs.edit()
            .putInt(KEY_HOUR, safeHour)
            .putInt(KEY_MINUTE, safeMinute)
            .putBoolean(KEY_ENABLED, enabled)
            .apply()
        workManager.cancelUniqueWork(STUDY_WORK)
        val pending = reminderPendingIntent()
        alarmManager.cancel(pending)
        if (!enabled) return
        val triggerAt = nextTriggerMillis(safeHour, safeMinute)
        val showIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        runCatching {
            alarmManager.setAlarmClock(
                AlarmManager.AlarmClockInfo(triggerAt, showIntent),
                pending,
            )
        }.onFailure {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                alarmManager.setAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerAt,
                    pending,
                )
            } else {
                @Suppress("DEPRECATION")
                alarmManager.set(AlarmManager.RTC_WAKEUP, triggerAt, pending)
            }
        }
    }

    fun rescheduleFromPrefs() {
        scheduleStudyReminder(reminderHour(), reminderEnabled(), reminderMinute())
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

    private fun reminderPendingIntent(): PendingIntent {
        val intent = Intent(context, StudyReminderReceiver::class.java).apply {
            action = StudyReminderReceiver.ACTION_FIRE
        }
        return PendingIntent.getBroadcast(
            context,
            REQUEST_STUDY,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    companion object {
        private const val STUDY_WORK = "vocabulario_study_reminder"
        private const val ENRICHMENT_WORK = "vocabulario_enrichment_check"
        private const val ENRICHMENT_SOON = "vocabulario_enrichment_soon"
        private const val REQUEST_STUDY = 4101
        private const val KEY_HOUR = "hour"
        private const val KEY_MINUTE = "minute"
        private const val KEY_ENABLED = "enabled"

        fun nextTriggerMillis(hour: Int, minute: Int, now: Calendar = Calendar.getInstance()): Long {
            val target = now.clone() as Calendar
            target.set(Calendar.HOUR_OF_DAY, hour)
            target.set(Calendar.MINUTE, minute)
            target.set(Calendar.SECOND, 0)
            target.set(Calendar.MILLISECOND, 0)
            if (target.timeInMillis <= now.timeInMillis) {
                target.add(Calendar.DAY_OF_YEAR, 1)
            }
            return target.timeInMillis
        }
    }
}
