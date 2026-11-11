package com.vocabulario.app.data.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.lookup.LookupCoordinator
import com.vocabulario.app.data.lookup.LookupQueryPersistence
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.CancellationException

/**
 * Dokańcza /lookup/expand gdy apka jest zminimalizowana.
 * Serwer i tak trzyma inflight task — worker czeka na ten sam wynik i wpuszcza go do coordinators.
 */
@HiltWorker
class LookupPollWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val repository: LearningRepository,
    private val persistence: LookupQueryPersistence,
    private val lookupCoordinator: LookupCoordinator,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!repository.hasSyncableSession()) return Result.success()
        val query = persistence.loadQuery() ?: return Result.success()
        if (persistence.loadByCategory()) return Result.success()
        return try {
            val expanded = repository.lookupExpand(query, more = persistence.loadMore())
            lookupCoordinator.acceptServerResult(query, expanded)
            Result.success()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            if (runAttemptCount >= 6) Result.failure() else Result.retry()
        }
    }
}
