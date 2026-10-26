package org.bakery.bakeryapp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

public class ReminderWorker extends Worker {
    private static final String CHANNEL_ID = "bakery_reminders";

    public ReminderWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context ctx = getApplicationContext();
        String title = getInputData().getString("title");
        String text = getInputData().getString("text");
        int id = getInputData().getInt("id", 0);

        NotificationManager nm =
                (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "Order reminders", NotificationManager.IMPORTANCE_HIGH);
            nm.createNotificationChannel(ch);
        }

        Intent launch = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName());
        PendingIntent pi = PendingIntent.getActivity(
                ctx, id, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification n = new NotificationCompat.Builder(ctx, CHANNEL_ID)
                .setSmallIcon(ctx.getApplicationInfo().icon)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build();
        nm.notify(id, n);
        return Result.success();
    }
}
