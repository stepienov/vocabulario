package com.vocabulario.app.data.session

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/** Jedna unikalna praca; tokeny zostają w zaszyfrowanej kolejce, nigdy w `inputData`. */
@Singleton
class RevocationScheduler @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val workManager get() = WorkManager.getInstance(context)

    /** Po nowym zleceniu lub starcie aplikacji: od razu, gdy jest sieć (zastępuje czekający backoff). */
    fun runNow() = enqueue(0L, ExistingWorkPolicy.REPLACE)

    /** Po 429: kolejna próba dopiero po `Retry-After`, dopięta za bieżącą pracą. */
    fun runAfter(delayMs: Long) = enqueue(delayMs.coerceAtLeast(0L), ExistingWorkPolicy.APPEND_OR_REPLACE)

    private fun enqueue(delayMs: Long, policy: ExistingWorkPolicy) {
        val request = OneTimeWorkRequestBuilder<SessionRevocationWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, BACKOFF_SECONDS, TimeUnit.SECONDS)
            .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
            .build()
        workManager.enqueueUniqueWork(WORK_NAME, policy, request)
    }

    private companion object {
        const val WORK_NAME = "vocabulario_session_revocation"
        const val BACKOFF_SECONDS = 30L
    }
}

@HiltWorker
class SessionRevocationWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val processor: RevocationProcessor,
    private val scheduler: RevocationScheduler,
    private val clock: WallClock,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val report = runCatching { processor.processDue() }.getOrNull() ?: return@withContext Result.retry()
        when {
            report.retryNeeded -> Result.retry()
            report.nextDeferredAtMs != null -> {
                scheduler.runAfter(report.nextDeferredAtMs - clock.nowMs())
                Result.success()
            }
            else -> Result.success()
        }
    }
}
