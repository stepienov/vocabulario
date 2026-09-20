package com.vocabulario.app

import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import com.vocabulario.app.data.LearningRepository
import com.vocabulario.app.data.imports.ImportController
import com.vocabulario.app.data.lookup.CategoryLookupCoordinator
import com.vocabulario.app.data.lookup.LookupCoordinator
import com.vocabulario.app.data.sync.BackgroundJobScheduler
import com.vocabulario.app.notifications.NotificationScheduler
import com.vocabulario.app.notifications.ReadyBatchTracker
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Process lifecycle — nie zależy od tego, czy HomeScreen jest w kompozycji.
 * ON_STOP: WorkManager ma prawo sieć w tle. ON_START: od razu cache/status, bez czekania
 * na rozmrożenie zawieszonego HTTP.
 */
@Singleton
class AppVisibilityHandler @Inject constructor(
    private val lookupCoordinator: LookupCoordinator,
    private val categoryLookupCoordinator: CategoryLookupCoordinator,
    private val importController: ImportController,
    private val scheduler: BackgroundJobScheduler,
    private val repository: LearningRepository,
    private val readyBatchTracker: ReadyBatchTracker,
    private val notificationScheduler: NotificationScheduler,
) : DefaultLifecycleObserver {

    override fun onStart(owner: LifecycleOwner) {
        lookupCoordinator.retryPending()
        categoryLookupCoordinator.retryPending()
        importController.onAppForeground()
        repository.requestBackgroundSync()
    }

    override fun onStop(owner: LifecycleOwner) {
        val lookupBusy = lookupCoordinator.state.value.expanding ||
            categoryLookupCoordinator.state.value.expanding
        if (lookupBusy) scheduler.enqueueLookup(replace = false)
        if (importController.state.value.busy) scheduler.enqueueImport(replace = false)
        if (readyBatchTracker.hasWatches()) notificationScheduler.scheduleEnrichmentSoon()
    }
}
