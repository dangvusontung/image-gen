# Native Android client

This is the Kotlin/Jetpack Compose rewrite, built beside the existing Capacitor client.
It talks to the same backend and intentionally does not embed the React/Vite app.

From `frontend/`, after installing JDK 21+ and Android SDK 36:

```bash
./android/gradlew -p native-android assembleDebug
```

The native client supports backend URL/QR connection, project listing/creation, project
settings (provider/model), photo upload, rights and asset selection, master/turnaround/
concept generation, workflow approval, enhancement, job polling with cancel/retry/dismiss,
global gallery, image previews, and Downloads export. Sticker Studio is intentionally not
included in this native rewrite.
