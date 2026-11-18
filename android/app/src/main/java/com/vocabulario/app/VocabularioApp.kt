package com.vocabulario.app

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.work.Configuration
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.session.RevocationScheduler
import com.vocabulario.app.data.session.RevocationStore
import com.vocabulario.app.data.sync.SyncScheduler
import com.vocabulario.app.notifications.NotificationHelper
import com.vocabulario.app.notifications.NotificationScheduler
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import javax.inject.Inject

@HiltAndroidApp
class VocabularioApp : Application(), Configuration.Provider {

    @Inject lateinit var workerFactory: HiltWorkerFactory
    @Inject lateinit var syncScheduler: SyncScheduler
    @Inject lateinit var notificationScheduler: NotificationScheduler
    @Inject lateinit var tokenStore: TokenStore
    @Inject lateinit var learningRepository: LearningRepository
    @Inject lateinit var appVisibilityHandler: AppVisibilityHandler
    @Inject lateinit var revocationStore: RevocationStore
    @Inject lateinit var revocationScheduler: RevocationScheduler

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun onCreate() {
        super.onCreate()
        runBlocking {
            runCatching {
                tokenStore.awaitReady()
                learningRepository.applyAppLocaleFromActiveProfile()
            }
        }
        NotificationHelper.ensureChannels(this)
        syncScheduler.schedulePeriodic()
        syncScheduler.requestNow()
        notificationScheduler.scheduleEnrichmentCheck()
        ProcessLifecycleOwner.get().lifecycle.addObserver(appVisibilityHandler)
        appScope.launch(Dispatchers.IO) {
            // Start aplikacji podejmuje zaległe odwołania sesji; bez cyklicznego pollingu.
            runCatching { if (revocationStore.load().pendingCount > 0) revocationScheduler.runNow() }
        }
        appScope.launch {
            runCatching {
                val settings = learningRepository.getSettings()
                notificationScheduler.scheduleStudyReminder(
                    hour = settings.reminder_hour,
                    enabled = settings.study_reminder_enabled || settings.cards_ready_push_enabled,
                    minute = notificationScheduler.reminderMinute(),
                )
            }
        }
    }
}
