# Native Android client

This is the Kotlin/Jetpack Compose rewrite, built beside the existing Capacitor client.
It talks to the same backend and intentionally does not embed the React/Vite app.

From `frontend/`, after installing JDK 21+ and Android SDK 36:

```bash
./android/gradlew -p native-android assembleDebug
```

`npm run android:build` and `npm run android:install` build and update this native
client. Install uses `adb install -r` to preserve the saved backend connection.
The old Capacitor client is available through `android:web:build` and
`android:web:install`; it shares the application ID but stores its connection
separately, so switching clients can show a different connection state.

## Mobile workflow

- Searchable/sortable project cards, pull-to-refresh, pagination, and saved project steps.
- Swipe between References, Master, and Concepts; open Gallery from its floating button.
- Photo collections with cached thumbnails, full-screen viewing, linked comparison of
  2–4 images, Markdown prompts, and multi-select save/Trash/enhance actions.
- Concept sets are separate from scene/pose groups. Filter by set, select/deselect
  its available concepts together, and see the set name in concept detail. Set controls
  appear when the backend provides `collection_id` / `collection_name`; older servers
  retain scene/pose grouping.
- Concept details show results from the current project or all projects. Favourite
  concepts sync with the backend; dislikes, Best photos, and named generation setups
  are stored locally on this phone, separately for each backend address.
- Review the master, concepts, styling, model, size, and count before generation.
  Master generation supports 1–4 variants; concept/enhanced images expose Enhance
  and the three retry modes from image detail.
- A global queue exposes active, failed, and recent jobs with cancel/retry controls.
  Job SSE follows foreground lifecycle with polling/reconnection fallback.
- Gallery search indexes all pages locally, supports tags/prompts/project names and
  accent-insensitive queries, and retains a disk cache. Image disk cache is bounded
  to 256 MB.

Connection and Trash are under Home → More; disconnect requires confirmation.
Sticker Studio is not included in this native client.

## Backend compatibility

This change does not require the optional project-page endpoint: a missing
`GET /api/projects/page` falls back to the existing project list and local paging.
`GET /api/projects/{project_id}/jobs/events` enables realtime updates; polling
continues when SSE is unavailable. Other actions use the existing gallery,
concept/enhancement, bookmark, preset, and Trash APIs.

## Validation

```bash
./android/gradlew -p native-android assembleDebug testDebugUnitTest lintDebug
```

Run from `frontend/` with JDK 21+ and Android SDK 36 configured.
