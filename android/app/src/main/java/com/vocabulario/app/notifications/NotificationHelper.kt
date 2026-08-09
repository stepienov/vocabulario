package com.vocabulario.app.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.vocabulario.app.R

object NotificationHelper {
    const val CHANNEL_STUDY = "study"
    const val CHANNEL_CARDS = "cards"

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
        ensureChannels(context)
        val notification = NotificationCompat.Builder(context, CHANNEL_STUDY)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle(context.getString(R.string.notif_study_title))
            .setContentText(context.getString(R.string.notif_study_body, dueCount))
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(context).notify(1001, notification)
    }

    fun showCardsReady(context: Context, count: Int) {
        ensureChannels(context)
        val notification = NotificationCompat.Builder(context, CHANNEL_CARDS)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle(context.getString(R.string.notif_cards_ready_title))
            .setContentText(context.getString(R.string.notif_cards_ready_body, count))
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(context).notify(1002, notification)
    }
}
