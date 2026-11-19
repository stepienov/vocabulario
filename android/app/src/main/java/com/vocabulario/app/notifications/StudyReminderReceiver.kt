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
                    ACTION_FIRE -> {
                        val generation = intent.getLongExtra(EXTRA_GENERATION, -1L)
                        if (scheduler.isCurrentGeneration(generation)) fireAndReschedule(app)
                    }
                    Intent.ACTION_BOOT_COMPLETED,
                    Intent.ACTION_MY_PACKAGE_REPLACED,
                    Intent.ACTION_TIMEZONE_CHANGED,
                    Intent.ACTION_TIME_CHANGED,
                    -> reconcile()
                }
            } finally {
                pending.finish()
            }
        }
    }

    /** Alarm należy do konta, które go zaplanowało; po zmianie lub wylogowaniu znika. */
    private suspend fun reconcile() {
        val owner = repository.activeOwnerId()
        if (owner != null && owner == scheduler.boundOwner()) {
            scheduler.rescheduleFromPrefs()
        } else {
            scheduler.scheduleStudyReminder(scheduler.reminderHour(), enabled = false)
        }
    }

    private suspend fun fireAndReschedule(app: Context) {
        val owner = repository.activeOwnerId()
        if (owner == null || owner != scheduler.boundOwner()) {
            scheduler.scheduleStudyReminder(scheduler.reminderHour(), enabled = false)
            return
        }
        if (scheduler.mayShowReminder(owner)) {
            NotificationHelper.showStudyReminder(app)
            if (NotificationHelper.canPost(app)) scheduler.markShownToday(owner)
        }
        scheduler.rescheduleFromPrefs()
    }

    companion object {
        const val ACTION_FIRE = "com.vocabulario.app.STUDY_REMINDER"
        const val EXTRA_GENERATION = "generation"
    }
}
