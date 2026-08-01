package com.vocabulario.app.data.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

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
        return try {
            learningRepository.syncNow(fullReplace = true)
            Result.success()
        } catch (_: Exception) {
            if (runAttemptCount >= 4) Result.failure() else Result.retry()
        }
    }
}
