package com.vocabulario.app.data.sync

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.CancellationException

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val learningRepository: LearningRepository,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!learningRepository.hasSyncableSession()) {
            return Result.success()
        }
        val result = try {
            learningRepository.syncNow()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "Background sync failed (${e.javaClass.simpleName})")
            return if (runAttemptCount >= 4) Result.failure() else Result.retry()
        }
        val blocked = when (result) {
            is SyncResult.Partial -> result.report.queue.blocked
            is SyncResult.Failed -> result.report.queue.blocked
            else -> 0
        }
        if (blocked > 0) Log.e(TAG, "Background sync has blocked changes")
        return when (result.workerDecision(runAttemptCount)) {
            WorkerDecision.SUCCESS -> Result.success()
            WorkerDecision.RETRY -> Result.retry()
            WorkerDecision.FAILURE -> {
                Log.e(TAG, "Background sync could not complete")
                Result.failure()
            }
        }
    }

    private companion object {
        const val TAG = "SyncWorker"
    }
}
