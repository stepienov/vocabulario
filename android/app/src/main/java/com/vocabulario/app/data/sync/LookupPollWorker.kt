package com.vocabulario.app.data.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.api.LookupResponse
import com.vocabulario.app.data.lookup.CategoryLookupCoordinator
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
    private val categoryLookupCoordinator: CategoryLookupCoordinator,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!repository.hasSyncableSession()) return Result.success()
        val query = persistence.loadQuery() ?: return Result.success()
        val byCategory = persistence.loadByCategory()
        return try {
            val cached = if (byCategory) {
                repository.lookupCategoryCached(query)
            } else {
                repository.lookupCached(query)
            }
            accept(query, byCategory, cached)
            if (cached.ai_complete) return Result.success()
            val expanded = if (byCategory) {
                repository.lookupCategoryExpand(query)
            } else {
                repository.lookupExpand(query)
            }
            accept(query, byCategory, expanded)
            Result.success()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            if (runAttemptCount >= 6) Result.failure() else Result.retry()
        }
    }

    private fun accept(
        query: String,
        byCategory: Boolean,
        response: LookupResponse,
    ) {
        if (byCategory) {
            categoryLookupCoordinator.acceptServerResult(query, response)
        } else {
            lookupCoordinator.acceptServerResult(query, response)
        }
    }
}
