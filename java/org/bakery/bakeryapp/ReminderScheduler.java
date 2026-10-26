package org.bakery.bakeryapp;

import android.content.Context;

import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;

import java.util.concurrent.TimeUnit;

public class ReminderScheduler {

    public static void schedule(Context ctx, int id, String title, String text, long delayMs) {
        Data data = new Data.Builder()
                .putString("title", title)
                .putString("text", text)
                .putInt("id", id)
                .build();
        OneTimeWorkRequest req = new OneTimeWorkRequest.Builder(ReminderWorker.class)
                .setInitialDelay(Math.max(delayMs, 0L), TimeUnit.MILLISECONDS)
                .setInputData(data)
                .build();
        WorkManager.getInstance(ctx)
                .enqueueUniqueWork("order_" + id, ExistingWorkPolicy.REPLACE, req);
    }

    public static void cancel(Context ctx, int id) {
        WorkManager.getInstance(ctx).cancelUniqueWork("order_" + id);
    }
}
