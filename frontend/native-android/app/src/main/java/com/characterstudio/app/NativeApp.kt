package com.characterstudio.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.imePadding
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
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.activity.compose.BackHandler

@Composable
fun NativeApp() {
    val context = LocalContext.current
    val prefs = remember { AppPrefs(context) }
    var origin by remember { mutableStateOf(prefs.origin) }
    var screen by remember { mutableStateOf(if (origin == null) "connect" else "dashboard") }
    var selectedProject by remember { mutableStateOf<String?>(null) }
    var projectInitialStep by remember { mutableIntStateOf(0) }

    BackHandler(enabled = screen == "project" || screen == "gallery" || screen == "trash") {
        screen = "dashboard"
    }

    androidx.compose.material3.MaterialTheme {
    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().safeDrawingPadding().imePadding()) {
    when (screen) {
        "connect" -> ConnectionScreen { connected ->
            prefs.origin = connected
            origin = connected
            screen = "dashboard"
        }
        "project" -> ProjectScreen(
            origin = origin!!,
            projectId = selectedProject!!,
            initialStep = projectInitialStep,
            onBack = { screen = "dashboard" },
        )
        "trash" -> TrashScreen(origin = origin!!, onBack = { screen = "dashboard" })
        "gallery" -> GalleryScreen(origin = origin!!, onBack = { screen = "dashboard" })
        else -> DashboardScreen(
            origin = origin!!,
            onOpen = { selectedProject = it; projectInitialStep = 0; screen = "project" },
            onProjectGallery = { selectedProject = it; projectInitialStep = 3; screen = "project" },
            onGallery = { screen = "gallery" },
            onTrash = { screen = "trash" },
            onDisconnect = { prefs.origin = null; origin = null; screen = "connect" },
        )
    }
    }
    }
}

private class AppPrefs(context: android.content.Context) {
    private val values = context.getSharedPreferences("character-studio", android.content.Context.MODE_PRIVATE)
    var origin: String?
        get() = values.getString("backend", null)
        set(value) { values.edit().apply { if (value == null) remove("backend") else putString("backend", value) }.apply() }
}

@Composable
private fun DashboardScreen(origin: String, onOpen: (String) -> Unit, onProjectGallery: (String) -> Unit, onGallery: () -> Unit, onTrash: () -> Unit, onDisconnect: () -> Unit) {
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
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Projects", style = MaterialTheme.typography.headlineMedium)
            Text(origin, style = MaterialTheme.typography.bodySmall)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onGallery) { Text("Gallery") }
                TextButton(onClick = onTrash) { Text("Trash") }
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
                        OutlinedButton(onClick = { onProjectGallery(project.id) }) { Text("Project photos") }
                    }
                }
            }
        }
    }
    if (showCreate) CreateProjectDialog(client, origin, { project -> showCreate = false; projects = projects + project; onOpen(project.id) }, { showCreate = false })
}

@Composable
private fun GalleryScreen(origin: String, onBack: () -> Unit) {
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var items by remember { mutableStateOf<List<GalleryItem>>(emptyList()) }
    var preview by remember { mutableStateOf<String?>(null) }
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
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        ResultImage(origin, item.id) { preview = item.id }
                        Column { Text(item.filename); Text("${item.projectName} · ${item.purpose}", style = MaterialTheme.typography.bodySmall) }
                        TextButton(onClick = {
                            val req = DownloadManager.Request(Uri.parse("$origin/api/assets/${item.id}/download?format=original"))
                                .setTitle(item.filename).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                                .setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, item.filename)
                            context.getSystemService(DownloadManager::class.java)?.enqueue(req)
                        }) { Text("Save") }
                        TextButton(onClick = { scope.launch {
                            runCatching { client.trashAsset(origin, item.id) }.onSuccess { items = items.filterNot { it.id == item.id }; error = null }.onFailure { error = it.message }
                        } }) { Text("Move image to Trash") }
                    }
                }
            }
        }
    }
    preview?.let { ImageViewer(origin, it) { preview = null } }
}

@Composable
private fun CreateProjectDialog(client: BackendClient, origin: String, onCreated: (ProjectSummary) -> Unit, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var sources by remember { mutableStateOf(emptyList<ProjectSummary>()) }
    var sourceId by remember { mutableStateOf("") }
    var includeConfiguration by remember { mutableStateOf(true) }
    var createdProject by remember { mutableStateOf<ProjectSummary?>(null) }
    LaunchedEffect(origin) { runCatching { client.listProjects(origin) }.onSuccess { sources = it } }
    var error by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New project") },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true, enabled = !saving && createdProject == null)
            OutlinedTextField(description, { description = it }, label = { Text("Description") }, enabled = !saving && createdProject == null)
            ServerChoice("Starting prompts", sourceId, listOf("") + sources.map { it.id }, enabled = !saving,
                labels = mapOf("" to "Use backend defaults") + sources.associate { it.id to ("Copy from "+it.name) }) { sourceId = it }
            if (sourceId.isNotBlank()) Row {
                Checkbox(includeConfiguration, onCheckedChange = { includeConfiguration = it }, enabled = !saving)
                Text("Also copy provider, model and per-step configuration", Modifier.padding(top = 12.dp))
            }
            Text("Photos and generated images are not copied.", style = MaterialTheme.typography.bodySmall)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        } },
        confirmButton = { TextButton(enabled = name.isNotBlank() && !saving, onClick = {
            saving = true
            scope.launch {
                try {
                    val created = createdProject ?: client.createProject(origin, name.trim(), description.trim()).also { createdProject = it }
                    if (sourceId.isNotBlank()) client.copyPrompts(origin, created.id, sourceId, includeConfiguration)
                    onCreated(created)
                } catch (e: Exception) { error = (if (createdProject != null) "Project created; prompt setup failed. Retry to finish without creating another project. " else "")+e.message; saving = false }
            }
        }) { Text(if (saving) "Creating…" else "Create") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
internal fun ProjectSettingsDialog(
    detail: ProjectDetail?, providers: List<ProviderSummary>, client: BackendClient, origin: String, projectId: String,
    onSaved: () -> Unit, onDismiss: () -> Unit, presets: List<StepPreset> = emptyList(), onPrompts: () -> Unit = {},
) {
    if (detail == null) return
    val scope = rememberCoroutineScope()
    var name by remember(detail.id) { mutableStateOf(detail.name) }
    var description by remember(detail.id) { mutableStateOf(detail.description.orEmpty()) }
    var provider by remember(detail.id) { mutableStateOf(detail.provider) }
    var model by remember(detail.id) { mutableStateOf(detail.model) }
    var presetId by remember(detail.id) { mutableStateOf(detail.presetId) }
    var workflowMode by remember(detail.id) { mutableStateOf(detail.workflowMode) }
    var error by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Project settings") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true)
            OutlinedTextField(description, { description = it }, label = { Text("Description") })
            OutlinedButton(onClick = onPrompts, enabled = !saving, modifier = Modifier.fillMaxWidth()) { Text("View, edit or copy prompts") }
            ServerChoice("Per-step configuration", presetId.orEmpty(), listOf("") + presets.map { it.id }, enabled = !saving,
                labels = mapOf("" to "None · use project settings") + presets.associate { it.id to it.name }) { presetId = it.takeIf { id -> id.isNotBlank() } }
            presets.find { it.id == presetId }?.let { preset ->
                preset.steps.forEach { (step, target) -> Text(step+": "+target.provider+" / "+target.model+(if (target.size.isNotBlank()) " · "+target.size else ""), style = MaterialTheme.typography.bodySmall) }
            }
            ServerChoice("Generation workflow", workflowMode, listOf("manual", "hybrid", "hybrid_gemini"), enabled = !saving,
                labels = mapOf("manual" to "Manual · one provider for all steps", "hybrid" to "Gemini 1K → FLUX.2 Pro", "hybrid_gemini" to "Gemini 1K for every step")) { workflowMode = it }
            Text("Per-step configurations take priority. Unconfigured steps use the workflow below.", style = MaterialTheme.typography.bodySmall)
            ServerChoice("Provider", provider, providers.filter { it.selectable }.map { it.name }, enabled = !saving) { selected ->
                provider = selected
                model = providers.find { it.name == selected }?.models?.firstOrNull().orEmpty()
            }
            ServerChoice("Model", model, providers.find { it.name == provider }?.models.orEmpty(), enabled = !saving) { model = it }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(onClick = {
        saving = true
        scope.launch { runCatching { client.updateProjectSettings(origin, projectId, name, description, provider, model, presetId, workflowMode) }.onSuccess { onSaved() }.onFailure { error = it.message }; saving = false }
    }, enabled = !saving && name.isNotBlank() && provider.isNotBlank() && model.isNotBlank()) { Text("Save") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
internal fun ServerChoice(label: String, value: String, options: List<String>, enabled: Boolean, labels: Map<String, String> = emptyMap(), onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium)
        androidx.compose.foundation.layout.Box {
            OutlinedButton(onClick = { expanded = true }, enabled = enabled && options.isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text(labels[value] ?: value.ifBlank { "Loading…" }, maxLines = 2) }
            androidx.compose.material3.DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                options.forEach { option -> androidx.compose.material3.DropdownMenuItem(text = { Text(labels[option] ?: option) }, onClick = { expanded = false; onSelect(option) }) }
            }
        }
    }
}
