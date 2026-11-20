package com.vocabulario.app.data.session

import android.content.Context
import com.vocabulario.app.data.lookup.LookupQueryPersistence
import com.vocabulario.app.data.sync.BackgroundJobScheduler
import com.vocabulario.app.data.sync.SyncScheduler
import com.vocabulario.app.notifications.NotificationHelper
import com.vocabulario.app.notifications.NotificationScheduler
import com.vocabulario.app.notifications.ReadyBatchTracker
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.CopyOnWriteArrayList
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Singletony trzymające w pamięci stan konta rejestrują tu reset. Odwrócona zależność, bo
 * tworzenie koordynatorów wznawia zapamiętane wyszukiwania; nieutworzone nie mają czego czyścić.
 */
@Singleton
class AccountResetHooks @Inject constructor() {
    private val hooks = CopyOnWriteArrayList<() -> Unit>()

    fun register(hook: () -> Unit) {
        hooks += hook
    }

    fun dispatch() {
        hooks.forEach { hook -> runCatching { hook() } }
    }
}

/**
 * Po usunięciu danych właściciela: stop pracy jednorazowej, wyciszenie przypomnień i powiadomień
 * konta, wyczyszczenie stanu w pamięci. Okresowy sync i sprawdzanie kart zostają zaplanowane,
 * ale bez aktywnego właściciela niczego nie robią. Odwołanie sesji na serwerze nie jest ruszane.
 */
@Singleton
class AccountSignOutCleanup @Inject constructor(
    @ApplicationContext private val context: Context,
    private val hooks: AccountResetHooks,
    private val syncScheduler: SyncScheduler,
    private val backgroundJobs: BackgroundJobScheduler,
    private val notificationScheduler: NotificationScheduler,
    private val readyBatchTracker: ReadyBatchTracker,
    private val lookupPersistence: LookupQueryPersistence,
) {
    suspend fun afterOwnerDataRemoved() {
        syncScheduler.cancelOnce()
        backgroundJobs.cancelLookup()
        backgroundJobs.cancelImport()
        notificationScheduler.silenceAccount()
        readyBatchTracker.clearAll()
        NotificationHelper.cancelAccountNotifications(context)
        runCatching { lookupPersistence.saveQuery(null) }
        hooks.dispatch()
    }
}
