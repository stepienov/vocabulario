package com.vocabulario.app.data.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.imports.ImportController
import com.vocabulario.app.data.imports.ImportStatePersistence
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.CancellationException

@HiltWorker
class ImportPollWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val repository: LearningRepository,
    private val persistence: ImportStatePersistence,
    private val importController: ImportController,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!repository.hasSyncableSession()) return Result.success()
        val jobId = persistence.loadJobId() ?: return Result.success()
        return try {
            val busy = repository.asCurrentOwner {
                val progress = repository.getImportJobProgress(jobId)
                repository.ensureOwnerCurrent()
                importController.ingestRemoteProgress(progress)
                importController.state.value.busy
            }
            when (busy) {
                true -> Result.retry()
                false -> Result.success()
                // Zastąpiony właściciel: ponawiamy tylko, gdy to samo konto nadal czeka na ten job.
                null -> if (persistence.loadJobId() == jobId && repository.hasActiveOwner()) {
                    Result.retry()
                } else {
                    Result.success()
                }
            }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            if (runAttemptCount >= 8) Result.failure() else Result.retry()
        }
    }
}
