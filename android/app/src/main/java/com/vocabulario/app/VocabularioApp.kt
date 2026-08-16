package com.vocabulario.app

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.local.TokenStore
import com.vocabulario.app.data.sync.SyncScheduler
import com.vocabulario.app.i18n.AppLocale
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
                AppLocale.apply(tokenStore.peekAppLang())
            }
        }
        NotificationHelper.ensureChannels(this)
        syncScheduler.schedulePeriodic()
        syncScheduler.requestNow()
        notificationScheduler.scheduleEnrichmentCheck()
        appScope.launch {
            runCatching {
                val settings = learningRepository.getSettings()
                notificationScheduler.scheduleStudyReminder(
                    hour = settings.reminder_hour,
                    enabled = settings.study_reminder_enabled || settings.cards_ready_push_enabled,
                )
            }
        }
        appScope.launch {
            runCatching { AppLocale.apply(tokenStore.peekAppLang()) }
        }
    }
}
