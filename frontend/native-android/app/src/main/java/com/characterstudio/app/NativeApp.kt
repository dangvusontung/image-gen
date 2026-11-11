package com.characterstudio.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import android.app.DownloadManager
import android.net.Uri
import coil.compose.AsyncImage
import kotlinx.coroutines.launch

@Composable
fun NativeApp() {
    val context = LocalContext.current
    val prefs = remember { AppPrefs(context) }
    var origin by remember { mutableStateOf(prefs.origin) }
    var screen by remember { mutableStateOf(if (origin == null) "connect" else "dashboard") }
    var selectedProject by remember { mutableStateOf<String?>(null) }

    when (screen) {
        "connect" -> ConnectionScreen { connected ->
            prefs.origin = connected
            origin = connected
            screen = "dashboard"
        }
        "project" -> ProjectScreen(
            origin = origin!!,
            projectId = selectedProject!!,
            onBack = { screen = "dashboard" },
        )
        "gallery" -> GalleryScreen(origin = origin!!, onBack = { screen = "dashboard" })
        else -> DashboardScreen(
            origin = origin!!,
            onOpen = { selectedProject = it; screen = "project" },
            onGallery = { screen = "gallery" },
            onDisconnect = { prefs.origin = null; origin = null; screen = "connect" },
        )
    }
}

private class AppPrefs(context: android.content.Context) {
    private val values = context.getSharedPreferences("character-studio", android.content.Context.MODE_PRIVATE)
    var origin: String?
        get() = values.getString("backend", null)
        set(value) { values.edit().apply { if (value == null) remove("backend") else putString("backend", value) }.apply() }
}

@Composable
private fun DashboardScreen(origin: String, onOpen: (String) -> Unit, onGallery: () -> Unit, onDisconnect: () -> Unit) {
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    var projects by remember { mutableStateOf<List<ProjectSummary>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    var showCreate by remember { mutableStateOf(false) }

    fun refresh() {
        loading = true
        scope.launch {
            runCatching { client.listProjects(origin) }
                .onSuccess { projects = it; error = null }
                .onFailure { error = it.message }
            loading = false
        }
    }
    LaunchedEffect(origin) { refresh() }

    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column { Text("Projects", style = MaterialTheme.typography.headlineMedium); Text(origin, style = MaterialTheme.typography.bodySmall) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onGallery) { Text("Gallery") }
                TextButton(onClick = onDisconnect) { Text("Disconnect") }
                Button(onClick = { showCreate = true }) { Text("New") }
            }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (loading) CircularProgressIndicator()
        else if (projects.isEmpty()) Text("No projects yet. Create the first one.")
        else LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(projects, key = { it.id }) { project ->
                Card(Modifier.fillMaxWidth().clickable { onOpen(project.id) }) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(project.name, style = MaterialTheme.typography.titleLarge)
                        Text(project.description ?: "No description", style = MaterialTheme.typography.bodyMedium)
                        Text("${project.assetCount} assets · ${project.completedJobs} completed jobs · ${project.activeJobs} active", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
    if (showCreate) CreateProjectDialog(client, origin, { project -> showCreate = false; projects = projects + project }, { showCreate = false })
}

@Composable
private fun GalleryScreen(origin: String, onBack: () -> Unit) {
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var items by remember { mutableStateOf<List<GalleryItem>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(origin) { runCatching { client.listGallery(origin) }.onSuccess { items = it }.onFailure { error = it.message } }
    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TextButton(onClick = onBack) { Text("← Projects") }
        Text("Gallery", style = MaterialTheme.typography.headlineMedium)
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (items.isEmpty()) Text("No completed generated images yet.")
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(items, key = { it.id }) { item ->
                Card(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        AsyncImage(model = "$origin/api/assets/${item.id}/content", contentDescription = item.filename, modifier = Modifier.size(76.dp))
                        Column(Modifier.weight(1f)) { Text(item.filename); Text("${item.projectName} · ${item.purpose}", style = MaterialTheme.typography.bodySmall) }
                        TextButton(onClick = {
                            val req = DownloadManager.Request(Uri.parse("$origin/api/assets/${item.id}/download?format=original"))
                                .setTitle(item.filename).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                                .setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, item.filename)
                            context.getSystemService(DownloadManager::class.java)?.enqueue(req)
                        }) { Text("Save") }
                    }
                }
            }
        }
    }
}

@Composable
private fun CreateProjectDialog(client: BackendClient, origin: String, onCreated: (ProjectSummary) -> Unit, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New project") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true)
            OutlinedTextField(description, { description = it }, label = { Text("Description") })
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        } },
        confirmButton = { TextButton(enabled = name.isNotBlank() && !saving, onClick = {
            saving = true
            scope.launch { runCatching { client.createProject(origin, name.trim(), description.trim()) }
                .onSuccess(onCreated).onFailure { error = it.message; saving = false } }
        }) { Text(if (saving) "Creating…" else "Create") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun ProjectScreen(origin: String, projectId: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    var project by remember { mutableStateOf<ProjectDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var uploading by remember { mutableStateOf(false) }
    var generating by remember { mutableStateOf(false) }
    var jobMessage by remember { mutableStateOf<String?>(null) }
    var jobs by remember { mutableStateOf<List<JobSummary>>(emptyList()) }
    var workflow by remember { mutableStateOf<org.json.JSONObject?>(null) }
    var concepts by remember { mutableStateOf<List<ConceptSummary>>(emptyList()) }
    var showSettings by remember { mutableStateOf(false) }
    var providers by remember { mutableStateOf<List<ProviderSummary>>(emptyList()) }
    var rightsConfirmed by remember { mutableStateOf(false) }
    val reload = suspend {
        runCatching { client.getProject(origin, projectId) }.onSuccess { project = it; rightsConfirmed = it.rightsConfirmed }.onFailure { error = it.message }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        uploading = true
        scope.launch {
            runCatching { client.uploadAssets(origin, projectId, uris, context.contentResolver); reload() }
                .onFailure { error = it.message }
            uploading = false
        }
    }
    LaunchedEffect(projectId) {
        reload()
        runCatching { client.workflow(origin, projectId) }.onSuccess { workflow = it }
        runCatching { client.listProviders(origin) }.onSuccess { providers = it }
        while (true) {
            runCatching { client.listJobs(origin, projectId) }.onSuccess { jobs = it }
            runCatching { client.workflow(origin, projectId) }.onSuccess { workflow = it }
            runCatching { client.listConcepts(origin, projectId) }.onSuccess { concepts = it }
            reload()
            kotlinx.coroutines.delay(3000)
        }
    }
    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        TextButton(onClick = onBack) { Text("← Projects") }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        project?.let { detail ->
            Text(detail.name, style = MaterialTheme.typography.headlineMedium)
            Text(detail.description ?: "No description")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { showSettings = true }) { Text("Project settings") }
            }
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Checkbox(checked = rightsConfirmed, onCheckedChange = { checked ->
                    rightsConfirmed = checked
                    scope.launch { runCatching { client.updateProject(origin, projectId, checked) }.onFailure { error = it.message } }
                })
                Text("I have permission to use these images")
            }
            HorizontalDivider()
            Text("Assets (${detail.assets.size})", style = MaterialTheme.typography.titleLarge)
            if (detail.assets.isEmpty()) Text("No assets yet. Upload flow is next.")
            detail.assets.forEach { asset ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Checkbox(checked = asset.selected, onCheckedChange = { selected ->
                        scope.launch { runCatching { client.updateAsset(origin, asset.id, selected) }.onSuccess { reload() }.onFailure { error = it.message } }
                    })
                    AsyncImage(
                        model = "$origin/api/assets/${asset.id}/content",
                        contentDescription = asset.filename,
                        modifier = Modifier.size(64.dp),
                    )
                    Column(Modifier.weight(1f)) {
                        Text(asset.filename)
                        Text(asset.kind, style = MaterialTheme.typography.bodySmall)
                    }
                    TextButton(onClick = {
                        val request = DownloadManager.Request(Uri.parse("$origin/api/assets/${asset.id}/download?format=original"))
                            .setTitle(asset.filename)
                            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                            .setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, asset.filename)
                        (context.getSystemService(DownloadManager::class.java))?.enqueue(request)
                    }) { Text("Save") }
                    TextButton(onClick = {
                        scope.launch { runCatching { client.deleteAsset(origin, asset.id) }.onSuccess { reload() }.onFailure { error = it.message } }
                    }) { Text("Delete") }
                }
            }
            Button(enabled = !uploading, onClick = { picker.launch("image/*") }) { Text(if (uploading) "Uploading…" else "Upload photos") }
            val selectedCount = detail.assets.count { it.selected }
            val approvedMaster = workflow?.optString("approved_master_id").orEmpty().isNotBlank()
            Button(enabled = selectedCount > 0 && rightsConfirmed && !generating, onClick = {
                generating = true
                scope.launch {
                    runCatching { client.generateMaster(origin, projectId) }
                        .onSuccess { ids -> jobMessage = "Master generation queued: ${ids.joinToString()}" }
                        .onFailure { error = it.message }
                    generating = false
                }
            }) { Text(if (generating) "Queueing…" else "Generate master") }
            Button(enabled = approvedMaster && !generating, onClick = {
                generating = true
                scope.launch {
                    runCatching { client.generateTurnaround(origin, projectId) }
                        .onSuccess { ids -> jobMessage = "Turnaround queued: ${ids.size} angles" }
                        .onFailure { error = it.message }
                    generating = false
                }
            }) { Text("Generate turnaround") }
            Button(enabled = approvedMaster && !generating, onClick = {
                generating = true
                scope.launch {
                    runCatching { client.generateConcepts(origin, projectId) }
                        .onSuccess { ids -> jobMessage = "Concept generation queued: ${ids.size} jobs" }
                        .onFailure { error = it.message }
                    generating = false
                }
            }) { Text("Generate concepts") }
            jobMessage?.let { Text(it, color = MaterialTheme.colorScheme.secondary) }
            workflow?.let { state ->
                val masters = state.optJSONArray("masters")?.length() ?: 0
                val turnarounds = state.optJSONArray("turnarounds")?.length() ?: 0
                Text("Workflow: $masters master versions · $turnarounds turnaround versions · ${if (approvedMaster) "master approved" else "master not approved"}", style = MaterialTheme.typography.bodySmall)
                val masterRows = state.optJSONArray("masters")
                if (!approvedMaster && masterRows != null) {
                    for (index in 0 until masterRows.length()) {
                        val row = masterRows.getJSONObject(index)
                        val job = row.optJSONObject("job")
                        if (job?.optString("status") == "succeeded") {
                            val versionId = row.optString("id")
                            Button(onClick = { scope.launch { runCatching { client.approveMaster(origin, projectId, versionId) }.onSuccess { reload() }.onFailure { error = it.message } } }) { Text("Approve master ${row.optInt("round")}/${row.optInt("variant")}") }
                        }
                    }
                }
                val turnRows = state.optJSONArray("turnarounds")
                if (turnRows != null) {
                    for (index in 0 until turnRows.length()) {
                        val row = turnRows.getJSONObject(index)
                        val turnId = row.optString("id")
                        val stale = row.optBoolean("stale")
                        val approvedTurn = state.optString("approved_turnaround_id") == turnId
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("Turnaround #${row.optInt("number")} ${if (stale) "(stale)" else ""}${if (approvedTurn) " · approved" else ""}", modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                            if (!stale && !approvedTurn) TextButton(onClick = { scope.launch { runCatching { client.approveTurnaround(origin, projectId, turnId) }.onSuccess { workflow = client.workflow(origin, projectId) }.onFailure { error = it.message } } }) { Text("Approve") }
                            TextButton(onClick = { scope.launch { runCatching { client.deleteTurnaround(origin, projectId, turnId) }.onSuccess { workflow = client.workflow(origin, projectId) }.onFailure { error = it.message } } }) { Text("Delete") }
                        }
                    }
                }
            }
            Text("Jobs", style = MaterialTheme.typography.titleLarge)
            jobs.take(8).forEach { job ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("${job.purpose}: ${job.status}${job.error?.let { " — $it" } ?: ""}", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                    if (job.status == "queued" || job.status == "submitting" || job.status == "running") TextButton(onClick = { scope.launch { runCatching { client.cancelJob(origin, job.id) }.onFailure { error = it.message } } }) { Text("Cancel") }
                    if (job.status == "failed" || job.status == "cancelled") {
                        TextButton(onClick = { scope.launch { runCatching { client.retryJob(origin, job.id) }.onFailure { error = it.message } } }) { Text("Retry") }
                        TextButton(onClick = { scope.launch { runCatching { client.dismissJob(origin, job.id) }.onFailure { error = it.message } } }) { Text("Dismiss") }
                    }
                }
            }
            Text("Concepts (${concepts.size})", style = MaterialTheme.typography.titleLarge)
            concepts.take(6).forEach { concept ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("${concept.status}: ${concept.brief.take(90)}", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                    if (concept.status == "succeeded") TextButton(onClick = { scope.launch { runCatching { client.enhance(origin, projectId, concept.id) }.onFailure { error = it.message } } }) { Text("Enhance") }
                }
            }
        } ?: CircularProgressIndicator()
    }
    if (showSettings) ProjectSettingsDialog(
        detail = project, providers = providers, client = client, origin = origin, projectId = projectId,
        onSaved = { showSettings = false; scope.launch { reload() } }, onDismiss = { showSettings = false },
    )
}

@Composable
private fun ProjectSettingsDialog(
    detail: ProjectDetail?, providers: List<ProviderSummary>, client: BackendClient, origin: String, projectId: String,
    onSaved: () -> Unit, onDismiss: () -> Unit,
) {
    if (detail == null) return
    val scope = rememberCoroutineScope()
    var name by remember(detail.id) { mutableStateOf(detail.name) }
    var description by remember(detail.id) { mutableStateOf(detail.description.orEmpty()) }
    var provider by remember(detail.id) { mutableStateOf(detail.provider) }
    var model by remember(detail.id) { mutableStateOf(detail.model) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Project settings") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true)
            OutlinedTextField(description, { description = it }, label = { Text("Description") })
            OutlinedTextField(provider, { provider = it }, label = { Text("Provider") }, singleLine = true)
            OutlinedTextField(model, { model = it }, label = { Text("Model") }, singleLine = true)
            Text("Available: ${providers.filter { it.selectable }.joinToString { it.name }}", style = MaterialTheme.typography.bodySmall)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(onClick = {
        scope.launch { runCatching { client.updateProjectSettings(origin, projectId, name, description, provider, model) }.onSuccess { onSaved() }.onFailure { error = it.message } }
    }, enabled = name.isNotBlank() && provider.isNotBlank() && model.isNotBlank()) { Text("Save") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}
