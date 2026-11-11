package com.characterstudio.app;

import android.app.DownloadManager;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.widget.Toast;
import android.webkit.URLUtil;
import java.net.HttpURLConnection;
import java.net.URL;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "StudioDownloads")
public class StudioDownloadsPlugin extends Plugin {
    @PluginMethod
    public void download(PluginCall call) {
        new Thread(() -> startDownload(call)).start();
    }

    private void startDownload(PluginCall call) {
        try {
            Uri uri = Uri.parse(call.getString("url", ""));
            if (!"http".equals(uri.getScheme()) && !"https".equals(uri.getScheme())) {
                call.reject("Invalid download URL");
                return;
            }
            String path = uri.getPath();
            boolean zip = path != null && path.endsWith("/export");
            boolean sheet = path != null && path.endsWith("/contact-sheet");
            String format = uri.getQueryParameter("format");
            String extension = zip ? ".zip" : sheet || "png".equals(format) ? ".png" : "jpeg".equals(format) ? ".jpg" : "";
            String filename = "CharacterStudio-" + System.currentTimeMillis() + extension;
            if (!zip && !sheet && (format == null || "original".equals(format))) {
                HttpURLConnection connection = (HttpURLConnection) new URL(uri.toString()).openConnection();
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(8000);
                try {
                    if (connection.getResponseCode() != 200) throw new IllegalStateException("Image unavailable");
                    String original = URLUtil.guessFileName(uri.toString(), connection.getHeaderField("Content-Disposition"), connection.getContentType());
                    filename = "CharacterStudio-" + System.currentTimeMillis() + "-" + original.replaceAll("[^a-zA-Z0-9._-]", "_");
                } finally { connection.disconnect(); }
            }
            DownloadManager.Request request = new DownloadManager.Request(uri)
                .setTitle(filename)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
            DownloadManager manager = (DownloadManager) getContext().getSystemService(Context.DOWNLOAD_SERVICE);
            manager.enqueue(request);
            getActivity().runOnUiThread(() -> Toast.makeText(getContext(), "Saving to Downloads", Toast.LENGTH_SHORT).show());
            call.resolve();
        } catch (Exception error) {
            call.reject("Unable to start download", error);
        }
    }
}
