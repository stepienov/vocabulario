package com.vocabulario.app.data.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * WorkManager budzi proces gdy Activity jest w tle — coroutines w app-scope
 * nie biegną, gdy Android zamrozi proces.
 */
@Singleton
class BackgroundJobScheduler @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val workManager get() = WorkManager.getInstance(context)

    private val networkConstraints = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    fun enqueueLookup(replace: Boolean = false) {
        val request = OneTimeWorkRequestBuilder<LookupPollWorker>()
            .setConstraints(networkConstraints)
            .setBackoffCriteria(BackoffPolicy.LINEAR, 10, TimeUnit.SECONDS)
            .build()
        workManager.enqueueUniqueWork(
            LOOKUP_WORK,
            if (replace) ExistingWorkPolicy.REPLACE else ExistingWorkPolicy.KEEP,
            request,
        )
    }

    fun cancelLookup() {
        workManager.cancelUniqueWork(LOOKUP_WORK)
    }

    fun enqueueImport(replace: Boolean = false) {
        val request = OneTimeWorkRequestBuilder<ImportPollWorker>()
            .setConstraints(networkConstraints)
            .setBackoffCriteria(BackoffPolicy.LINEAR, 10, TimeUnit.SECONDS)
            .build()
        workManager.enqueueUniqueWork(
            IMPORT_WORK,
            if (replace) ExistingWorkPolicy.REPLACE else ExistingWorkPolicy.KEEP,
            request,
        )
    }

    fun cancelImport() {
        workManager.cancelUniqueWork(IMPORT_WORK)
    }

    companion object {
        const val LOOKUP_WORK = "vocabulario_lookup_poll"
        const val IMPORT_WORK = "vocabulario_import_poll"
    }
}
