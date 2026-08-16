package com.vocabulario.app.notifications

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.vocabulario.app.MainActivity
import com.vocabulario.app.R

object NotificationHelper {
    const val CHANNEL_STUDY = "study"
    const val CHANNEL_CARDS = "cards"

    fun canPost(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= 33) {
            val granted = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) return false
        }
        return NotificationManagerCompat.from(context).areNotificationsEnabled()
    }

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_STUDY,
                context.getString(R.string.notif_channel_study),
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_CARDS,
                context.getString(R.string.notif_channel_cards),
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
    }

    fun showStudyReminder(context: Context, dueCount: Int) {
        post(
            context,
            CHANNEL_STUDY,
            1001,
            context.getString(R.string.notif_study_title),
            context.getString(R.string.notif_study_body, dueCount),
        )
    }

    fun showCardsReady(context: Context, count: Int) {
        post(
            context,
            CHANNEL_CARDS,
            1002,
            context.getString(R.string.notif_cards_ready_title),
            context.getString(R.string.notif_cards_ready_body, count),
        )
    }

    fun showOfflineReady(context: Context, count: Int) {
        post(
            context,
            CHANNEL_CARDS,
            1003,
            context.getString(R.string.notif_offline_ready_title),
            context.getString(R.string.notif_offline_ready_body, count),
        )
    }

    fun showImportReady(context: Context, count: Int) {
        post(
            context,
            CHANNEL_CARDS,
            1004,
            context.getString(R.string.notif_import_ready_title),
            context.getString(R.string.notif_import_ready_body, count),
        )
    }

    private fun post(
        context: Context,
        channel: String,
        id: Int,
        title: String,
        body: String,
    ) {
        if (!canPost(context)) return
        ensureChannels(context)
        val launch = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val tap = PendingIntent.getActivity(
            context,
            id,
            launch,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_stat_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setContentIntent(tap)
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(id, notification) }
    }
}
