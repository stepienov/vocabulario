package com.vocabulario.app.notifications

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
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
    private val alarmManager get() = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager

    fun reminderHour(): Int = prefs.getInt(KEY_HOUR, 19).coerceIn(0, 23)

    fun reminderMinute(): Int = prefs.getInt(KEY_MINUTE, 0).coerceIn(0, 59)

    fun reminderEnabled(): Boolean = prefs.getBoolean(KEY_ENABLED, false)

    /** Konto, dla którego zaplanowano jedyny alarm przypomnienia; null, gdy alarmu nie ma. */
    fun boundOwner(): String? = prefs.getString(KEY_OWNER, null)

    /**
     * Jeden alarm na właściciela. Bez [owner] albo z [enabled] = false alarm jest anulowany;
     * każde ustawienie podnosi generację, więc zaległy alarm poprzedniego harmonogramu jest ignorowany.
     * Alarm niedokładny (setAndAllowWhileIdle) wystarcza do przypomnienia o nauce.
     */
    fun scheduleStudyReminder(hour: Int, enabled: Boolean, minute: Int = reminderMinute(), owner: String? = null) {
        val safeHour = hour.coerceIn(0, 23)
        val safeMinute = minute.coerceIn(0, 59)
        val active = enabled && !owner.isNullOrBlank()
        val generation = prefs.getLong(KEY_GENERATION, 0L) + 1
        prefs.edit()
            .putInt(KEY_HOUR, safeHour)
            .putInt(KEY_MINUTE, safeMinute)
            .putBoolean(KEY_ENABLED, active)
            .putString(KEY_OWNER, if (active) owner else null)
            .putLong(KEY_GENERATION, generation)
            .apply()
        alarmManager.cancel(reminderPendingIntent(generation))
        if (!active) return
        alarmManager.setAndAllowWhileIdle(
            AlarmManager.RTC_WAKEUP,
            nextTriggerMillis(safeHour, safeMinute),
            reminderPendingIntent(generation),
        )
    }

    /** Alarm po restarcie, zmianie czasu lub aktualizacji: odnawia go tylko dla zapisanego właściciela. */
    fun rescheduleFromPrefs() {
        scheduleStudyReminder(reminderHour(), reminderEnabled(), reminderMinute(), boundOwner())
    }

    fun isCurrentGeneration(generation: Long): Boolean = generation == prefs.getLong(KEY_GENERATION, 0L)

    /** Przypomnienie pokazujemy raz dziennie na właściciela, także po restarcie i odnowieniu alarmu. */
    fun markShownToday(owner: String, now: Calendar = Calendar.getInstance()) {
        prefs.edit().putString(KEY_LAST_SHOWN, reminderDayKey(owner, now)).apply()
    }

    fun mayShowReminder(currentOwner: String?, now: Calendar = Calendar.getInstance()): Boolean =
        shouldShowReminder(
            enabled = reminderEnabled(),
            boundOwner = boundOwner(),
            currentOwner = currentOwner,
            lastShownKey = prefs.getString(KEY_LAST_SHOWN, null),
            todayKey = currentOwner?.let { reminderDayKey(it, now) },
        )

    /** Wylogowanie: alarm przypomnienia i zaplanowane sprawdzenie kart nie należą już do nikogo. */
    fun silenceAccount() {
        scheduleStudyReminder(reminderHour(), enabled = false, minute = reminderMinute())
        prefs.edit().remove(KEY_LAST_SHOWN).apply()
        workManager.cancelUniqueWork(ENRICHMENT_SOON)
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

    private fun reminderPendingIntent(generation: Long): PendingIntent {
        val intent = Intent(context, StudyReminderReceiver::class.java).apply {
            action = StudyReminderReceiver.ACTION_FIRE
            putExtra(StudyReminderReceiver.EXTRA_GENERATION, generation)
        }
        return PendingIntent.getBroadcast(
            context,
            REQUEST_STUDY,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    companion object {
        private const val ENRICHMENT_WORK = "vocabulario_enrichment_check"
        private const val ENRICHMENT_SOON = "vocabulario_enrichment_soon"
        private const val REQUEST_STUDY = 4101
        private const val KEY_HOUR = "hour"
        private const val KEY_MINUTE = "minute"
        private const val KEY_ENABLED = "enabled"
        private const val KEY_OWNER = "owner"
        private const val KEY_GENERATION = "generation"
        private const val KEY_LAST_SHOWN = "last_shown"

        fun reminderDayKey(owner: String, now: Calendar): String =
            "$owner|${now.get(Calendar.YEAR)}-${now.get(Calendar.DAY_OF_YEAR)}"

        fun shouldShowReminder(
            enabled: Boolean,
            boundOwner: String?,
            currentOwner: String?,
            lastShownKey: String?,
            todayKey: String?,
        ): Boolean =
            enabled && !currentOwner.isNullOrBlank() && boundOwner == currentOwner &&
                todayKey != null && lastShownKey != todayKey

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
