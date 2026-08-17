package com.vocabulario.app.notifications

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.vocabulario.app.data.LearningRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class StudyReminderReceiver : BroadcastReceiver() {

    @Inject lateinit var repository: LearningRepository
    @Inject lateinit var scheduler: NotificationScheduler

    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        val app = context.applicationContext
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                when (intent.action) {
                    ACTION_FIRE -> fireAndReschedule(app)
                    Intent.ACTION_BOOT_COMPLETED,
                    Intent.ACTION_MY_PACKAGE_REPLACED,
                    Intent.ACTION_TIMEZONE_CHANGED,
                    Intent.ACTION_TIME_CHANGED,
                    -> scheduler.rescheduleFromPrefs()
                    else -> if (intent.action == null) fireAndReschedule(app)
                }
            } finally {
                pending.finish()
            }
        }
    }

    private suspend fun fireAndReschedule(app: Context) {
        val settings = runCatching { repository.getSettings() }.getOrNull()
        val enabled = settings?.study_reminder_enabled == true || scheduler.reminderEnabled()
        if (enabled) {
            val due = runCatching { repository.getQueue().due.size }.getOrDefault(0)
            NotificationHelper.showStudyReminder(app, due)
        }
        scheduler.rescheduleFromPrefs()
    }

    companion object {
        const val ACTION_FIRE = "com.vocabulario.app.STUDY_REMINDER"
    }
}
