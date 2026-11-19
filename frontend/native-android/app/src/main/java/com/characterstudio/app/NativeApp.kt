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
import androidx.lifecycle.repeatOnLifecycle
import androidx.compose.runtime.key
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
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
    var projectInitialStep by remember { mutableIntStateOf(-1) }
    var projectReturnScreen by remember { mutableStateOf("dashboard") }
    val libraryScope = rememberCoroutineScope()
    val library = remember(origin) { origin?.let { LibrarySession(it, libraryScope, context.applicationContext) } }

    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    LaunchedEffect(library, lifecycleOwner) {
        val session = library ?: return@LaunchedEffect
        lifecycleOwner.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) { session.syncHomeGeneration() }
    }

    BackHandler(enabled = screen == "project" || screen == "gallery" || screen == "trash" || screen == "queue") {
        screen = if (screen == "project") projectReturnScreen else "dashboard"
    }

    androidx.compose.material3.MaterialTheme(colorScheme = StudioColors) {
    androidx.compose.material3.Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().safeDrawingPadding().imePadding()) {
    when (screen) {
        "connect" -> ConnectionScreen { connected ->
            prefs.origin = connected
            origin = connected
            screen = "dashboard"
        }
        "project" -> key(selectedProject) { ProjectScreen(
            origin = origin!!,
            projectId = selectedProject!!,
            initialStep = projectInitialStep,
            library = library!!,
            onOpenProject = { selectedProject = it; projectInitialStep = -1 },
            onBack = { screen = projectReturnScreen },
        )
        }
        "queue" -> QueueScreen(library!!, onBack = { screen = "dashboard" }, onOpenProject = {
            selectedProject = it; projectInitialStep = -1; projectReturnScreen = "queue"; screen = "project"
        })
        "trash" -> TrashScreen(origin = origin!!, onBack = { screen = "dashboard" })
        "gallery" -> GalleryScreen(session = library!!, onBack = { screen = "dashboard" }, onOpenProject = {
            selectedProject = it; projectInitialStep = -1; projectReturnScreen = "gallery"; screen = "project"
        })
        else -> DashboardScreen(
            session = library!!,
            onOpen = { selectedProject = it; projectInitialStep = -1; projectReturnScreen = "dashboard"; screen = "project" },
            onProjectGallery = { selectedProject = it; projectInitialStep = 3; projectReturnScreen = "dashboard"; screen = "project" },
            onQueue = { screen = "queue" },
            onGallery = { screen = "gallery" },
            onTrash = { screen = "trash" },
            onDisconnect = { prefs.origin = null; origin = null; screen = "connect" },
        )
    }
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

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun DashboardScreen(session: LibrarySession, onOpen: (String) -> Unit, onProjectGallery: (String) -> Unit, onGallery: () -> Unit, onQueue: () -> Unit, onTrash: () -> Unit, onDisconnect: () -> Unit) {
    val origin = session.origin
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    val feed = session.projects
    val projects = feed.items
    val visibleProjects = projects
    val error = feed.error
    val loading = feed.loading && projects.isEmpty()
    var showCreate by remember { mutableStateOf(false) }
    var showConnection by remember { mutableStateOf(false) }
    var showMore by remember { mutableStateOf(false) }
    var showSearch by session::showSearch
    var search by session::search
    var sort by session::sort
    var showSort by remember { mutableStateOf(false) }
    LaunchedEffect(search, sort) {
        val sortKey = when (sort) {
            "Name A–Z" -> "name_asc"; "Name Z–A" -> "name_desc"
            "Most photos" -> "photos"; "Most active jobs" -> "active"; else -> "updated"
        }
        if (search.trim() != session.appliedQuery || sortKey != session.appliedSort) {
            kotlinx.coroutines.delay(300)
            session.appliedQuery = search.trim(); session.appliedSort = sortKey
            feed.refresh()
            session.listState.scrollToItem(0)
        } else feed.ensureLoaded()
    }
    LaunchedEffect(feed) {
        snapshotFlow { session.listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index to feed.items.size }.collect { (last, size) ->
            if (last != null && last >= size - 5 && feed.error == null) feed.loadMore()
        }
    }

    androidx.compose.material3.pulltorefresh.PullToRefreshBox(isRefreshing = feed.refreshing, onRefresh = { feed.refresh() }, modifier = Modifier.fillMaxSize()) {
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.fillMaxWidth()) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text("Projects", style = MaterialTheme.typography.headlineSmall)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = onGallery) { Text("Gallery") }
                TextButton(onClick = onQueue) { Text("Queue · ${session.queue.count { isGenerating(it.status) }}") }
                androidx.compose.foundation.layout.Box {
                    TextButton(onClick = { showMore = true }) { Text("More ⋯") }
                    androidx.compose.material3.DropdownMenu(
                        expanded = showMore,
                        onDismissRequest = { showMore = false },
                    ) {
                        androidx.compose.material3.DropdownMenuItem(
                            text = { Text("Connection") },
                            onClick = { showMore = false; showConnection = true },
                        )
                        androidx.compose.material3.DropdownMenuItem(
                            text = { Text("Trash") },
                            onClick = { showMore = false; onTrash() },
                        )
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Text("${feed.total} projects", style = MaterialTheme.typography.labelLarge)
            Row {
                TextButton(onClick = { showSearch = !showSearch; if (!showSearch) search = "" }) {
                    Text(if (showSearch) "Close search" else "Search")
                }
                androidx.compose.foundation.layout.Box {
                    TextButton(onClick = { showSort = true }) { Text("Sort: $sort") }
                    androidx.compose.material3.DropdownMenu(expanded = showSort, onDismissRequest = { showSort = false }) {
                        listOf("Default", "Name A–Z", "Name Z–A", "Most photos", "Most active jobs").forEach { option ->
                            androidx.compose.material3.DropdownMenuItem(
                                text = { Text(if (sort == option) "✓ $option" else option) },
                                onClick = { sort = option; showSort = false },
                            )
                        }
                    }
                }
            }
        }
        if (showSearch) OutlinedTextField(
            value = search, onValueChange = { search = it },
            label = { Text("Search projects") }, placeholder = { Text("Name or description") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
            trailingIcon = { if (search.isNotEmpty()) TextButton(onClick = { search = "" }) { Text("Clear") } },
        )
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
            TextButton(onClick = { feed.refresh() }) { Text("Retry") }
        }
        LazyColumn(modifier = Modifier.weight(1f), contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 88.dp), state = session.listState, verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (loading) item { CircularProgressIndicator() }
            if (!loading && error == null && projects.isEmpty()) item { Text(if (search.isBlank()) "No projects yet. Create the first one." else "No projects match your search.") }
            items(visibleProjects, key = { it.id }) { project ->
                Card(
                    onClick = { onOpen(project.id) },
                    modifier = Modifier.fillMaxWidth(),
                    shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
                    colors = androidx.compose.material3.CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest),
                    border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)),
                ) {
                    Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    ProjectPreview(origin, project)
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(project.name, style = MaterialTheme.typography.titleMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold, maxLines = 2, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                        project.description?.takeIf { it.isNotBlank() }?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 1,
                                overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text("${project.assetCount} photos · ${project.completedJobs} completed", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (project.activeJobs > 0) Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            GenerationLoading()
                            Text("${project.activeJobs} generating", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        }
                        androidx.compose.material3.FilledTonalButton(
                            onClick = { onProjectGallery(project.id) },
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 14.dp, vertical = 0.dp),
                            colors = androidx.compose.material3.ButtonDefaults.filledTonalButtonColors(
                                containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                                contentColor = MaterialTheme.colorScheme.primary,
                            ),
                        ) { Text("Photos ↗", style = MaterialTheme.typography.labelMedium) }
                    }
                    }
                }
            }
            if (feed.hasMore) item {
                if (feed.loading) CircularProgressIndicator(Modifier.padding(16.dp))
                else TextButton(onClick = { feed.loadMore() }) { Text(if (feed.error != null) "Retry loading more" else "Load more") }
            }
        }
    }
    androidx.compose.material3.FloatingActionButton(
        onClick = { showCreate = true },
        modifier = Modifier.align(androidx.compose.ui.Alignment.BottomEnd).padding(24.dp)
            .size(56.dp).then(Modifier.semantics { contentDescription = "New project" }),
        shape = androidx.compose.foundation.shape.CircleShape,
        containerColor = MaterialTheme.colorScheme.primary,
        contentColor = MaterialTheme.colorScheme.onPrimary,
    ) { Text("+", style = MaterialTheme.typography.headlineMedium) }
    }
    if (showCreate) CreateProjectDialog(client, origin, { project -> showCreate = false; feed.refresh(); onOpen(project.id) }, { showCreate = false })
    if (showConnection) ConnectionDialog(origin, onDismiss = { showConnection = false }, onDisconnect = {
        showConnection = false
        onDisconnect()
    })
}

@Composable
private fun GalleryScreen(session: LibrarySession, onBack: () -> Unit, onOpenProject: (String) -> Unit) {
    val feed = session.gallery
    LaunchedEffect(feed) { feed.ensureLoaded() }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← Projects") }
            Text("Gallery", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
        }
        PhotoGallery(session.origin, feed.items, Modifier.weight(1f), onOpenProject = onOpenProject,
            feed = feed, gridState = session.gridState) { id -> feed.remove(id) }
    }
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
