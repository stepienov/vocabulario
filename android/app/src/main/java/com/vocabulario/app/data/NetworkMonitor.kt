package com.vocabulario.app.data

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NetworkMonitor @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val connectivity = context.getSystemService(ConnectivityManager::class.java)
    private val _isOnline = MutableStateFlow(isCurrentlyOnline())
    val isOnline: StateFlow<Boolean> = _isOnline.asStateFlow()

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = refresh()
        override fun onLost(network: Network) = refresh()
        override fun onUnavailable() = refresh()
        override fun onCapabilitiesChanged(
            network: Network,
            networkCapabilities: NetworkCapabilities,
        ) = refresh()
    }

    private val airplaneReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context?, intent: Intent?) = refresh()
    }

    private val mainHandler = Handler(Looper.getMainLooper())

    init {
        runCatching {
            connectivity.registerDefaultNetworkCallback(callback)
        }
        runCatching {
            val filter = IntentFilter(Intent.ACTION_AIRPLANE_MODE_CHANGED)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                context.registerReceiver(airplaneReceiver, filter, Context.RECEIVER_EXPORTED)
            } else {
                context.registerReceiver(airplaneReceiver, filter)
            }
        }
        refresh()
    }

    fun isCurrentlyOnline(): Boolean {
        if (isAirplaneModeOn()) return false
        return connectivity.allNetworks.any { network ->
            val caps = connectivity.getNetworkCapabilities(network) ?: return@any false
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        }
    }

    private fun isAirplaneModeOn(): Boolean =
        Settings.Global.getInt(
            context.contentResolver,
            Settings.Global.AIRPLANE_MODE_ON,
            0,
        ) != 0

    private fun refresh() {
        val online = isCurrentlyOnline()
        // Callbacki sieci mogą przyjść z wątku systemowego — StateFlow dla UI zawsze na main.
        mainHandler.post {
            _isOnline.value = online
        }
    }
}
