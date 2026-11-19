package com.characterstudio.app

import androidx.lifecycle.repeatOnLifecycle

import android.app.DownloadManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import coil.compose.AsyncImage
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

private fun JSONObject.rows(key: String): List<JSONObject> = optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getJSONObject(it) } } ?: emptyList()
private fun JSONObject.outputs(): List<String> = optJSONArray("output_asset_ids")?.let { a -> (0 until a.length()).map { a.getString(it) } } ?: emptyList()
private fun JSONObject.realId(key: String) = optString(key).takeIf { it.isNotBlank() && it != "null" }

@Composable
internal fun ProjectScreen(origin: String, projectId: String, onBack: () -> Unit, initialStep: Int = -1, library: LibrarySession, onOpenProject: (String) -> Unit) {
    val client = remember { BackendClient() }; val scope = rememberCoroutineScope(); val context = LocalContext.current
    var project by remember { mutableStateOf<ProjectDetail?>(null) }
    var workflow by remember { mutableStateOf(JSONObject()) }
    var concepts by remember { mutableStateOf(emptyList<JSONObject>()) }; var proposals by remember { mutableStateOf(emptyList<JSONObject>()) }
    val galleryFeed = remember(projectId, library) { library.gallery(projectId) }
    val gallery = galleryFeed.items
    LaunchedEffect(galleryFeed) { galleryFeed.ensureLoaded() }
    var jobs by remember { mutableStateOf(emptyList<JobSummary>()) }
    val favouritePrefs = remember { context.getSharedPreferences("concept-favourites", android.content.Context.MODE_PRIVATE) }
    val favouriteKey = origin+"/"+projectId
    var favourites by remember(origin) { mutableStateOf(emptySet<String>()) }
    var bookmarkLoaded by remember(origin) { mutableStateOf(false) }
    var bookmarkVersion by remember { mutableIntStateOf(0) }
    var bookmarkSaving by remember { mutableStateOf(false) }
    var bookmarkError by remember { mutableStateOf<String?>(null) }
    var showFilters by remember { mutableStateOf(false) }
    var showSearch by rememberSaveable { mutableStateOf(false) }
    var showAdvancedCreate by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable(projectId) { mutableStateOf("") }
    var favouritesOnly by rememberSaveable(projectId) { mutableStateOf(false) }
    var picked by remember { mutableStateOf(setOf<String>()) }
    val dislikePrefs = remember { context.getSharedPreferences("concept-dislikes", android.content.Context.MODE_PRIVATE) }
    var dislikes by remember(origin) { mutableStateOf(dislikePrefs.getStringSet(origin, emptySet()).orEmpty().toSet()) }
    var dislikeFilter by rememberSaveable(projectId) { mutableStateOf("hide") }
    fun toggleDislike(row: JSONObject) {
        val key = conceptIdentity(row)
        val disliked = key !in dislikes
        dislikes = if (disliked) dislikes + key else dislikes - key
        dislikePrefs.edit().putStringSet(origin, dislikes.toSet()).apply()
        if (disliked) {
            val hiddenIds = proposals.filter { conceptIdentity(it) == key }.map { it.getString("id") }.toSet()
            picked = picked - hiddenIds
        }
    }
    var progressFilter by rememberSaveable(projectId) { mutableStateOf("all") }
    var detailConcept by remember { mutableStateOf<JSONObject?>(null) }
    var historyKey by remember { mutableStateOf<String?>(null) }
    var archiveFilter by rememberSaveable(projectId) { mutableStateOf("active") }
    var archiveLoading by remember { mutableStateOf(false) }
    var collectionFilter by rememberSaveable(projectId) { mutableStateOf("") }
    var groupFilter by rememberSaveable(projectId) { mutableStateOf("All groups") }
    var groupMode by rememberSaveable(projectId) { mutableStateOf("Bộ concept") }
    val stylingPrefs = remember { context.getSharedPreferences("concept-styling", android.content.Context.MODE_PRIVATE) }
    val stylingKey = origin+"/"+projectId
    var choices by remember(stylingKey) { mutableStateOf(runCatching {
        val defaults = defaultConceptChoices()
        val saved = JSONObject(stylingPrefs.getString(stylingKey, "{}").orEmpty())
        saved.keys().forEach { defaults.put(it, saved.get(it)) }; defaults
    }.getOrElse { defaultConceptChoices() }) }
    var stylingMenu by remember { mutableStateOf(JSONObject()) }
    var showStyling by remember { mutableStateOf(false) }
    var masterCount by rememberSaveable(projectId) { mutableIntStateOf(1) }
    var customCount by rememberSaveable(projectId) { mutableIntStateOf(1) }
    fun saveChoices(next: JSONObject) { choices = JSONObject(next.toString()); stylingPrefs.edit().putString(stylingKey, choices.toString()).apply() }
    var promptEdit by remember { mutableStateOf<JSONObject?>(null) }
    fun toggleFavourite(row: JSONObject) {
        if (bookmarkSaving) return
        val key = conceptIdentity(row)
        val desired = key !in favourites
        bookmarkVersion += 1
        bookmarkSaving = true
        scope.launch {
            try {
                client.setBookmark(origin, key, desired)
                favourites = if (desired) favourites + key else favourites - key
                bookmarkError = null
                bookmarkLoaded = true
            } catch (e: Exception) { bookmarkError = e.message }
            finally { bookmarkVersion += 1; bookmarkSaving = false }
        }
    }

    var presets by remember { mutableStateOf(emptyList<StepPreset>()) }
    var providers by remember { mutableStateOf(emptyList<ProviderSummary>()) }
    var error by remember { mutableStateOf<String?>(null) }; var notice by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }; var settings by remember { mutableStateOf(false) }
    val setupStore = remember(origin) { GenerationSetupStore(context.applicationContext, origin) }
    var showSetups by remember { mutableStateOf(false) }
    var generationDraft by remember { mutableStateOf<GenerationDraft?>(null) }
    var showProjectPrompts by remember { mutableStateOf(false) }
    val visitPrefs = remember { context.getSharedPreferences("project-visits", android.content.Context.MODE_PRIVATE) }
    val visitKey = origin+"/"+projectId
    var masterOutfitId by rememberSaveable(visitKey) { mutableStateOf(visitPrefs.getString(visitKey+"/master-outfit", "").orEmpty()) }
    LaunchedEffect(visitKey, masterOutfitId) { visitPrefs.edit().putString(visitKey+"/master-outfit", masterOutfitId).apply() }
    var step by rememberSaveable(visitKey) { mutableIntStateOf(if (initialStep in 0..4) initialStep else visitPrefs.getInt(visitKey+"/step", 0).takeIf { it in 0..2 } ?: 0) }
    val stepPager = rememberPagerState(initialPage = step.coerceIn(0, 2), pageCount = { 3 })
    LaunchedEffect(step) {
        if (step in 0..2 && stepPager.currentPage != step) stepPager.animateScrollToPage(step)
    }
    LaunchedEffect(stepPager) {
        snapshotFlow { stepPager.settledPage }.collect { page ->
            if (step in 0..2 && step != page) step = page
        }
    }
    val stepHistory = remember(projectId) { mutableStateListOf<Int>() }
    fun navigateTo(next: Int) {
        if (next != step) { stepHistory.add(step); step = next }
    }
    var edit by remember { mutableStateOf<JSONObject?>(null) }; var preview by remember { mutableStateOf<String?>(null) }
    var selectedBatch by rememberSaveable(visitKey) { mutableStateOf(visitPrefs.getInt(visitKey+"/batch", -1).takeIf { it >= 0 }) }
    var showCreateConcepts by rememberSaveable(visitKey) { mutableStateOf(visitPrefs.getBoolean(visitKey+"/create", true)) }
    val conceptLibrary = remember(origin) { ConceptLibraryRepository(context.applicationContext, origin) }
    var libraryPreviews by remember(origin) { mutableStateOf<Map<String, List<GalleryItem>>>(emptyMap()) }
    var libraryPreviewLoading by remember(origin) { mutableStateOf(false) }
    LaunchedEffect(origin, step, showCreateConcepts) {
        if (step != 2 || !showCreateConcepts) return@LaunchedEffect
        try {
            val cached = conceptLibrary.read()
            libraryPreviews = cached?.entries.orEmpty()
            if (cached?.fresh != true) {
                libraryPreviewLoading = true
                libraryPreviews = conceptLibrary.refresh().entries
            }
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (_: Exception) { /* Local results and cached thumbnails remain usable. */ }
        finally { libraryPreviewLoading = false }
    }
    LaunchedEffect(visitKey, step, selectedBatch, showCreateConcepts) {
        visitPrefs.edit().apply {
            if (step in 0..2) putInt(visitKey+"/step", step)
            putInt(visitKey+"/batch", selectedBatch ?: -1)
            putBoolean(visitKey+"/create", showCreateConcepts)
        }.apply()
    }
    var confirmation by remember { mutableStateOf<Pair<String, () -> Unit>?>(null) }
    var showSections by remember { mutableStateOf(false) }
    var showProjectMenu by remember { mutableStateOf(false) }
    BackHandler(enabled = !showSetups && generationDraft == null && detailConcept == null && preview == null && historyKey == null && !settings && !showProjectPrompts && edit == null && !showFilters && !showStyling && promptEdit == null && confirmation == null) {
        when {
            showSections -> showSections = false
            showProjectMenu -> showProjectMenu = false
            showSearch -> showSearch = false
            step >= 3 -> step = if (stepHistory.isNotEmpty()) stepHistory.removeAt(stepHistory.lastIndex) else visitPrefs.getInt(visitKey+"/step", 0).coerceIn(0, 2)
            else -> onBack()
        }
    }
    val titles = listOf("References", "Master", "Concepts", "Gallery", "History")
    val lists = titles.map { rememberLazyListState() }
    suspend fun loadProposals() {
        val requested = archiveFilter
        val rows = client.projectArray(origin, projectId, "concept-proposals" + if (requested == "active") "" else "?status=$requested")
        if (archiveFilter == requested) proposals = rows
    }
    LaunchedEffect(origin, projectId, archiveFilter) {
        archiveLoading = true
        try { loadProposals() }
        catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { error = e.message }
        finally { archiveLoading = false }
    }
    suspend fun refresh() {
        project = client.getProject(origin, projectId); presets = client.listPresets(origin); workflow = client.workflow(origin, projectId)
        concepts = client.projectArray(origin, projectId, "concepts"); loadProposals()
        val legacyMap = (proposals + concepts).filter { it.optString("bookmark_key").isNotBlank() }.associate {
            (it.optString("master_version_id")+":"+it.optInt("slot")) to it.getString("bookmark_key")
        }
        favouritePrefs.all.filterKeys { it.startsWith(origin+"/") }.forEach { (localKey, value) ->
            val old = (value as? Set<*>)?.filterIsInstance<String>()?.toSet() ?: emptySet()
            val migrated = old.filter { it in legacyMap }
            migrated.forEach { client.setBookmark(origin, legacyMap.getValue(it), true) }
            if (migrated.isNotEmpty()) favouritePrefs.edit().putStringSet(localKey, old - migrated.toSet()).apply()
        }
        jobs = client.listJobs(origin, projectId)
    }
    fun action(block: suspend () -> Unit) {
        if (busy) return
        busy = true; error = null
        scope.launch { try { block(); refresh() } catch (e: Exception) { error = e.message } finally { busy = false } }
    }
    fun generate(path: String, payload: JSONObject = JSONObject()) {
        val requestPayload = try {
            val styled = styledConceptPayload(path, payload, choices)
            if (path.startsWith("master/") && !path.endsWith("/outfit")) withMasterOutfit(styled, masterOutfitId, project?.assets.orEmpty()) else styled
        } catch (e: IllegalArgumentException) { error = e.message; return }
        if (requestPayload.has("choices")) choicesError(choices)?.let { error = it; showStyling = true; return }
        val purpose = when { path.startsWith("master/") -> "master"; path.startsWith("turnaround/") -> "turnaround"; else -> "concept" }
        val names = if (path == "concepts/generate" && !payload.optBoolean("custom")) {
            val slots = payload.optJSONArray("slots")?.let { values -> (0 until values.length()).map { values.getInt(it) }.toSet() }.orEmpty()
            val ids = payload.optJSONArray("proposal_ids")?.let { values -> (0 until values.length()).map { values.getString(it) }.toSet() }.orEmpty()
            proposals.filter { it.optInt("slot") in slots || it.optString("id") in ids }.map(::conceptLabel)
        } else emptyList()
        generationDraft = GenerationDraft(path, requestPayload, purpose, names)
    }
    fun reviewConceptBatch(ids: Set<String>) {
        val selected = proposals.filter { it.getString("id") in ids }
        if (selected.isEmpty()) return
        val payload = JSONObject()
        if (selected.first().optInt("run") == 0) payload.put("slots", JSONArray(selected.map { it.optInt("slot") }))
        else payload.put("proposal_ids", JSONArray(selected.map { it.getString("id") }))
        generate("concepts/generate", payload)
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris -> if (uris.isNotEmpty()) action { client.uploadAssets(origin, projectId, uris, context.contentResolver) } }
    LaunchedEffect(origin) {
        while (true) {
            val version = bookmarkVersion
            try {
                val saved = client.listBookmarks(origin)
                if (version == bookmarkVersion && !bookmarkSaving) {
                    favourites = saved
                    bookmarkLoaded = true
                    bookmarkError = null
                }
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { bookmarkError = "Bookmark sync failed: "+e.message }
            delay(2000)
        }
    }
    val projectLifecycle = androidx.lifecycle.compose.LocalLifecycleOwner.current
    LaunchedEffect(origin, projectId, projectLifecycle) {
        runCatching {
            stylingMenu = client.conceptOptions(origin, projectId)
            val outfits = stylingMenu.optJSONArray("outfit")
            if (outfits != null) {
                val allowed = (0 until outfits.length()).map { outfits.getJSONArray(it).getString(0) }
                if (choices.optString("outfit", "auto") !in allowed) saveChoices(JSONObject(choices.toString()).put("outfit", "auto"))
            }
        }.onFailure { error = it.message }
        runCatching { providers = client.listProviders(origin) }.onFailure { error = it.message }
        projectLifecycle.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) {
            var previousJobs: List<JobSummary>? = null
            suspend fun updateGeneration() {
                refresh()
                if (previousJobs != null && previousJobs != jobs) {
                    galleryFeed.refresh()
                    library.projects.refresh()
                    library.gallery.refresh()
                }
                previousJobs = jobs
            }
            while (true) {
                try {
                    updateGeneration()
                    GenerationEvents.subscribe(origin, projectId).collect { updateGeneration() }
                } catch (e: kotlinx.coroutines.CancellationException) { throw e }
                catch (_: Exception) { /* Poll below while SSE is unavailable. */ }
                // Keep jobs moving even on older servers or proxies that reject SSE.
                // Retry the stream after 30 seconds, without blocking the UI.
                repeat(10) {
                    delay(3000)
                    try { updateGeneration() }
                    catch (e: kotlinx.coroutines.CancellationException) { throw e }
                    catch (e: Exception) { error = e.message }
                }
            }
        }
    }
    val batches = concepts.map { it.optInt("run") }.distinct().sortedDescending()
    val activeBatch = selectedBatch?.takeIf { it in batches } ?: batches.firstOrNull()
    val batchConcepts = concepts.filter { it.optInt("run") == activeBatch }.sortedWith(compareBy<JSONObject> { it.optInt("slot") }.thenByDescending { it.optInt("revision") })
    val projectProgress = projectConceptProgress(concepts)
    fun progressOf(row: JSONObject) = projectProgress[conceptIdentity(row)] ?: ProjectConceptProgress()
    val collectionRows = (if (showCreateConcepts) proposals else batchConcepts).filter { matchesConceptArchive(it, archiveFilter) }
    val collections = conceptCollections(collectionRows)
    val effectiveCollection = collectionFilter.takeIf { it == UNASSIGNED_COLLECTION || collections.any { set -> set.id == it } }.orEmpty()
    val groupingByCollection = groupMode == "Bộ concept" && collections.isNotEmpty()
    fun visible(row: JSONObject) = matchesConceptArchive(row, archiveFilter) && matchesCollection(row, effectiveCollection) && (when (dislikeFilter) { "only" -> conceptIdentity(row) in dislikes; "all" -> true; else -> conceptIdentity(row) !in dislikes }) && matchesConcept(row, query) && (!favouritesOnly || conceptIdentity(row) in favourites) && (groupFilter == "All groups" || conceptGroup(row) == groupFilter) && progressOf(row).matches(progressFilter)
    fun section(row: JSONObject) = when {
        groupingByCollection -> conceptCollectionId(row) ?: UNASSIGNED_COLLECTION
        groupMode == "Bối cảnh" -> conceptGroup(row)
        else -> row.optString("family").ifBlank { conceptGroup(row) }
    }
    val visibleProposals = proposals.filter { visible(it) }.sortedBy { conceptOrder(it) }.groupBy { section(it) }.let { groups ->
        if (groupingByCollection) groups.entries.sortedWith(compareBy({ it.key == UNASSIGNED_COLLECTION }, { conceptCollectionName(it.value.first()).orEmpty() })).associate { it.key to it.value }
        else groups
    }
    val groupedResults = batchConcepts.groupBy { it.optInt("slot") }.mapValues { (_, rows) -> rows.sortedByDescending { it.optInt("revision") } }
    val groupOptions = listOf("All groups") + (proposals + batchConcepts).map { conceptGroup(it) }.distinct().sorted()
    val favouriteVisibleCount = if (showCreateConcepts) proposals.count { conceptIdentity(it) in favourites }
        else groupedResults.values.count { rows -> rows.any { conceptIdentity(it) in favourites } }
    val approved = workflow.realId("approved_master_id") != null; val detail = project
    Box(Modifier.fillMaxSize()) {
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            IconButton(onClick = {
                if (step >= 3) step = if (stepHistory.isNotEmpty()) stepHistory.removeAt(stepHistory.lastIndex) else visitPrefs.getInt(visitKey+"/step", 0).coerceIn(0, 2)
                else onBack()
            }) { Icon(DetailIcons.Back, "Back") }
            Box(Modifier.weight(1f)) {
                Column(Modifier.fillMaxWidth().clickable { showSections = true }.padding(vertical = 8.dp), horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                    Text(titles[step]+" ▾", style = MaterialTheme.typography.titleMedium)
                    Text(detail?.name ?: "Loading…", style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                DropdownMenu(expanded = showSections, onDismissRequest = { showSections = false }) {
                    titles.take(3).forEachIndexed { index, title ->
                        DropdownMenuItem(text = { Text(if (step == index) "✓ $title" else title) }, onClick = { showSections = false; navigateTo(index) })
                    }
                }
            }
            Box {
                IconButton(onClick = { showProjectMenu = true }) { Icon(DetailIcons.More, "More project options") }
                DropdownMenu(expanded = showProjectMenu, onDismissRequest = { showProjectMenu = false }) {
                    DropdownMenuItem(text = { Text("Settings") }, enabled = detail != null, onClick = { showProjectMenu = false; settings = true })
                    DropdownMenuItem(text = { Text("Saved setups") }, enabled = detail != null, onClick = { showProjectMenu = false; showSetups = true })
                    DropdownMenuItem(text = { Text("History") }, onClick = { showProjectMenu = false; navigateTo(4) })
                }
            }
        }
        if (step in 0..2) Text((step + 1).toString()+" / 3", Modifier.fillMaxWidth().padding(bottom = 4.dp), style = MaterialTheme.typography.labelSmall,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
        bookmarkError?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error, maxLines = 2) }
        error?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error, maxLines = 3) }
        notice?.let { Text(it, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.primary) }
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (detail == null) { CircularProgressIndicator(Modifier.padding(24.dp)); return@Column }
        @Composable
        fun StepContent(page: Int) {
            val step = page
            Column(Modifier.fillMaxSize()) {
        val purpose = when (step) { 2 -> "concept"; else -> "master" }
        val target = detail.generationTarget(purpose, presets)
        if (step == 2) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = showCreateConcepts, onClick = { showCreateConcepts = true; scope.launch { lists[2].scrollToItem(0) } }, label = { Text("Create new batch") })
                FilterChip(selected = !showCreateConcepts, onClick = { showCreateConcepts = false; scope.launch { lists[2].scrollToItem(0) } }, label = { Text("Previous batches") })
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                TextButton(onClick = { showStyling = true }) { Text("Styling") }
                TextButton(onClick = { showSearch = !showSearch }) { Text(if (query.isBlank()) "Search" else "Search •") }
                TextButton(onClick = { favouritesOnly = !favouritesOnly; scope.launch { lists[2].scrollToItem(0) } }, enabled = bookmarkLoaded) {
                    Text(if (!bookmarkLoaded) "☆ …" else (if (favouritesOnly) "★ " else "☆ ")+favouriteVisibleCount)
                }
                TextButton(onClick = { showFilters = true }) { Text(if (archiveFilter != "active" || effectiveCollection.isNotEmpty() || favouritesOnly || dislikeFilter != "hide" || groupFilter != "All groups" || progressFilter != "all") "Filters •" else "Filters") }
            }
            if (collections.isNotEmpty()) ConceptCollectionFilters(collections, effectiveCollection, collectionRows.any { conceptCollectionId(it) == null }) { selected ->
                collectionFilter = selected
                if (selected.isNotEmpty() && selected != UNASSIGNED_COLLECTION) groupMode = "Bộ concept"
                scope.launch { lists[2].scrollToItem(0) }
            }
            if (archiveFilter != "active") Text(if (archiveFilter == "archived") "Archived concepts" else "Active + archived concepts", Modifier.padding(horizontal = 16.dp), style = MaterialTheme.typography.labelSmall)
            if (archiveLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (showCreateConcepts && libraryPreviewLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (showSearch) OutlinedTextField(query, { query = it }, placeholder = { Text("Search concepts…") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp), trailingIcon = { TextButton(onClick = { query = ""; showSearch = false }) { Text("×") } })
        }

        if (step == 0) PhotoCollection(
            origin, detail.assets.map { CollectionPhoto(it.id, it.filename, it.selected) }, busy, Modifier.weight(1f),
            onChoose = { id -> detail.assets.find { it.id == id }?.let { asset -> action { client.updateAsset(origin, id, !asset.selected) } } },
            onDeleted = { action {} },
            projectId = projectId, projectName = detail.name,
        ) {
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Checkbox(detail.rightsConfirmed, enabled = !busy, onCheckedChange = { checked -> action { client.updateProject(origin, projectId, checked) } })
                Text("I have permission to use these images")
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { picker.launch("image/*") }, enabled = detail.rightsConfirmed && !busy, modifier = Modifier.weight(1f)) { Text("Add photos") }
                Button(onClick = { navigateTo(1) }, enabled = detail.rightsConfirmed && detail.assets.any { it.selected }, modifier = Modifier.weight(1f)) { Text("Master →") }
            }
            Text(detail.assets.count { it.selected }.toString()+" / "+detail.assets.size+" selected", style = MaterialTheme.typography.labelLarge)
        } else if (step == 1) {
            val masters = workflow.rows("masters")
            val masterPhotos = masters.filter { it.optJSONObject("job")?.optString("status") == "succeeded" }.flatMap { row ->
                row.optJSONObject("job")!!.outputs().map { id -> CollectionPhoto(id, "Master "+row.optInt("round")+"/"+row.optInt("variant"), workflow.realId("approved_master_id") == row.getString("id")) }
            }
            PhotoCollection(origin, masterPhotos, busy, Modifier.weight(1f), onChoose = { id ->
                masters.find { id in it.optJSONObject("job")?.outputs().orEmpty() }?.let { row ->
                    action {
                        if (workflow.realId("approved_master_id") != row.getString("id")) client.approveMaster(origin, projectId, row.getString("id"))
                        navigateTo(2)
                    }
                }
            }, onDeleted = { action {} }, photoInfo = gallery, onOpenProject = { navigateTo(0) }, projectId = projectId, projectName = detail.name, purpose = "master",
                pendingPhotos = masters.filter { isGenerating(it.optJSONObject("job")?.optString("status").orEmpty()) }.map { PendingPhoto(it.getString("id"), "Master ${it.optInt("round")}/${it.optInt("variant")} · Creating…") },
            ) {
                Text("Master collection", style = MaterialTheme.typography.titleLarge)
                MasterOutfitPicker(origin, detail.assets, masterOutfitId, enabled = !busy, menu = stylingMenu) { masterOutfitId = it }
                ServerChoice("Number of master images", masterCount.toString(), listOf("1", "2", "3", "4"), enabled = !busy,
                    labels = mapOf("1" to "1 image", "2" to "2 images", "3" to "3 images", "4" to "4 images")) { masterCount = it.toInt() }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { generate("master/generate", JSONObject().put("variants", masterCount).put("hairstyle", "reference")) }, enabled = !busy && detail.rightsConfirmed && detail.assets.any { it.selected }, modifier = Modifier.weight(1f)) { Text("Generate · $masterCount") }
                    Button(onClick = { navigateTo(2) }, enabled = approved, modifier = Modifier.weight(1f)) { Text("Concepts →") }
                }
                Text("Tap a photo to view; use ✓ to approve a master.", style = MaterialTheme.typography.bodySmall)
                masters.filter { it.optJSONObject("job")?.optString("status") in listOf("failed", "cancelled") }.forEach { row ->
                    val job = row.optJSONObject("job") ?: JSONObject()
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        if (isGenerating(job.optString("status"))) GenerationLoading()
                        Text("Master "+row.optInt("round")+"/"+row.optInt("variant")+" · "+job.optString("status"), style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        } else if (step == 2 && !showCreateConcepts) {
            ServerChoice("Batch", activeBatch?.toString().orEmpty(), batches.map { it.toString() }, enabled = batches.isNotEmpty(),
                labels = batches.associate { it.toString() to ("Batch #"+it+" · "+concepts.count { row -> row.optInt("run") == it }+" versions") }) { selectedBatch = it.toInt() }
            val visibleBatch = batchConcepts.filter { visible(it) }
            val batchPhotos = visibleBatch.flatMap { row ->
                val job = row.optJSONObject("job") ?: JSONObject()
                if (job.optString("status") != "succeeded") emptyList() else job.outputs().map { id ->
                    conceptGalleryPhoto(id, projectId, detail.name, row, gallery.find { it.id == id })
                }
            }.distinctBy { it.id }
            val stopped = visibleBatch.filter { it.optJSONObject("job")?.optString("status") in listOf("failed", "cancelled") }
            val grid = androidx.compose.runtime.key(activeBatch, query, favouritesOnly, groupFilter, progressFilter) { androidx.compose.foundation.lazy.grid.rememberLazyGridState() }
            PhotoGallery(origin, batchPhotos, Modifier.weight(1f), onOpenProject = { navigateTo(0) }, gridState = grid,
                onRefresh = { action {} }, bottomPadding = 96.dp,
                pendingPhotos = visibleBatch.filter { isGenerating(it.optJSONObject("job")?.optString("status").orEmpty()) }.map { PendingPhoto(it.getString("id"), conceptLabel(it) + " · Creating…") },
                statusItems = if (stopped.isEmpty()) null else {
                    {
                        stopped.forEach { row ->
                            val job = row.getJSONObject("job")
                            val failed = job.optString("status") == "failed"
                            item(key = "status-${row.getString("id")}", span = { androidx.compose.foundation.lazy.grid.GridItemSpan(maxLineSpan) }) {
                                Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
                                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text("${conceptLabel(row)} · v${row.optInt("revision")}", style = MaterialTheme.typography.titleSmall)
                                        Text(if (failed) "Failed" else "Cancelled",
                                            color = if (failed) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                                        job.realId("error_message")?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                                        TextButton(onClick = { navigateTo(4) }) { Text("Generation history") }
                                    }
                                }
                            }
                        }
                    }
                },
            ) { id -> galleryFeed.remove(id); action {} }
        } else if (step == 3) PhotoGallery(origin, gallery, Modifier.weight(1f), onOpenProject = { navigateTo(0) }, feed = galleryFeed, gridState = library.grid(projectId), searchProjectId = projectId,
            pendingPhotos = jobs.filter { isGenerating(it.status) }.map { PendingPhoto(it.id, "${it.purpose} · Creating…") },
        ) { id ->
            galleryFeed.remove(id)
            action {}
        } else LazyColumn(state = lists[step], modifier = Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            when (step) {
                2 -> {
                    if (showCreateConcepts) {
                    if (!approved) item { Text("Approve a master in step 2 first.") }
                    item {
                        TextButton(onClick = { showAdvancedCreate = !showAdvancedCreate }) { Text(if (showAdvancedCreate) "Less options ▴" else "More creation options ▾") }
                        if (showAdvancedCreate) {
                        OutlinedButton(onClick = { confirmation = "Suggest new concepts with AI? Charges may apply." to { action { client.suggestConcepts(origin, projectId); picked = emptySet() } } }, enabled = approved && !busy) { Text("Suggest concepts with AI") }
                        ServerChoice("Images from styling only", customCount.toString(), listOf("1", "2", "3", "4"), enabled = !busy) { customCount = it.toInt() }
                        OutlinedButton(onClick = { generate("concepts/generate", JSONObject().put("custom", true).put("count", customCount)) }, enabled = approved && !busy && overridesConcept(choices)) { Text("Generate from outfit & scene only") }
                    }
                        }
                    visibleProposals.forEach { (group, rows) ->
                    item(key = "proposal-group-"+group) {
                        val setId = if (groupingByCollection && group != UNASSIGNED_COLLECTION) group else null
                        val groupTitle = if (groupingByCollection) conceptCollectionName(rows.first()) ?: "Chưa có bộ" else group
                        val eligible = setId?.let { selectableCollection(proposals.filter { row -> matchesConceptArchive(row, archiveFilter) }, it, dislikes) }.orEmpty()
                        Column(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 4.dp)) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Text(groupTitle, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                                Text("${rows.size} concepts", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (setId != null) TextButton(enabled = !busy && eligible.isNotEmpty(), onClick = { picked = toggleCollectionSelection(picked, eligible) }) {
                                Text(if (picked.containsAll(eligible)) "Deselect set" else "Select set · ${eligible.size}")
                            }
                        }
                    }
                    items(rows, key = { "proposal-${it.getString("id")}" }) { row -> val id = row.getString("id")
                        val selected = id in picked
                        val state = progressOf(row)
                        val globalPhotos = libraryPreviews[conceptIdentity(row)].orEmpty()
                        val thumbnail = state.imageIds.firstOrNull() ?: globalPhotos.firstOrNull()?.id
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f) else MaterialTheme.colorScheme.surface),
                            border = androidx.compose.foundation.BorderStroke(1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)),
                        ) {
                            Row(Modifier.fillMaxWidth().clickable { detailConcept = row }.padding(start = 8.dp, end = 4.dp, top = 8.dp, bottom = 4.dp), verticalAlignment = androidx.compose.ui.Alignment.Top) {
                                Box(Modifier.padding(8.dp).size(88.dp)) {
                                    Surface(Modifier.fillMaxSize(), shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerHigh) {
                                        if (thumbnail != null) AsyncImage("$origin/api/assets/$thumbnail/content", "Concept preview", Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                                        else Box(contentAlignment = androidx.compose.ui.Alignment.Center) {
                                            if (state.active) GenerationLoading() else Icon(DetailIcons.Gallery, "No concept image yet", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                    Surface(Modifier.align(androidx.compose.ui.Alignment.BottomStart), shape = androidx.compose.foundation.shape.CircleShape, color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)) {
                                        Checkbox(selected, enabled = conceptIdentity(row) !in dislikes, onCheckedChange = { checked -> picked = if (checked) picked + id else picked - id }, modifier = Modifier.size(40.dp))
                                    }
                                }
                                Column(Modifier.weight(1f).padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text(conceptLabel(row), style = MaterialTheme.typography.titleMedium)
                                    if (archivedConcept(row)) Text("Archived" + row.optInt("replacement_slot").takeIf { it > 0 }?.let { " · Replaced by C${it.toString().padStart(3, '0')}" }.orEmpty(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.tertiary)
                                    if (!groupingByCollection) conceptCollectionName(row)?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary) }
                                    if (globalPhotos.isNotEmpty()) Text("${globalPhotos.size} images · ${globalPhotos.map { it.projectId }.distinct().size} projects", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                                    if (conceptIdentity(row) in dislikes) Text("Disliked", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
                                    row.optJSONObject("brief")?.optString("setting")?.takeIf { it.isNotBlank() }?.let {
                                        Text(it, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    val tags = conceptTags(row)
                                    if (tags.isNotEmpty()) Text(tags.take(3).joinToString("  ·  "), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Column {
                                IconToggleButton(checked = conceptIdentity(row) in favourites, onCheckedChange = { toggleFavourite(row) }, enabled = !bookmarkSaving) {
                                    Icon(if (conceptIdentity(row) in favourites) DetailIcons.StarFilled else DetailIcons.Star, "Bookmark concept", tint = if (conceptIdentity(row) in favourites) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                IconToggleButton(checked = conceptIdentity(row) in dislikes, onCheckedChange = { toggleDislike(row) }) {
                                    Icon(DetailIcons.Dislike, if (conceptIdentity(row) in dislikes) "Remove dislike" else "Dislike concept", tint = if (conceptIdentity(row) in dislikes) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                }
                            }
                            Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, bottom = 4.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                if (state.active) { GenerationLoading(); Spacer(Modifier.width(8.dp)) }
                                Text(state.label(), Modifier.weight(1f), style = MaterialTheme.typography.labelSmall, color = if (state.imageIds.isNotEmpty()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                                if (state.rows.isNotEmpty()) TextButton(onClick = { historyKey = conceptIdentity(row) }) { Text("Results") }
                                TextButton(onClick = { detailConcept = row }) { Text("Details") }
                            }

                        }

                    }
                    }
                    }
                }
                4 -> {
                    item { Text("Generation history", style = MaterialTheme.typography.titleLarge) }
                    items(jobs, key = { it.id }) { job -> Card { Column(Modifier.fillMaxWidth().padding(12.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            if (isGenerating(job.status)) GenerationLoading()
                            Text("${job.purpose} · ${job.status}", style = MaterialTheme.typography.titleMedium)
                        }
                        job.outputAssetIds.forEach { id -> ResultImage(origin, id) { preview = id } }; job.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        if (job.status in listOf("succeeded", "failed", "cancelled")) TextButton(onClick = { action { client.dismissJob(origin, job.id) } }, enabled = !busy) { Text("Move run to Trash") }
                        if (job.status in listOf("queued", "submitting", "running")) TextButton(onClick = { action { client.cancelJob(origin, job.id) } }) { Text("Cancel job") }
                        if (job.status in listOf("failed", "cancelled")) Row { TextButton(onClick = { confirmation = "Retry this generation? Provider charges may apply." to { action { client.retryJob(origin, job.id) } } }) { Text("Retry") } }
                    } } }
                }
            }
        }
            }
        }
        if (step in 0..2) HorizontalPager(
            state = stepPager,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            beyondViewportPageCount = 1,
            key = { it },
        ) { page -> StepContent(page) }
        else Box(Modifier.weight(1f).fillMaxWidth()) { StepContent(step) }
        if (step == 2 && showCreateConcepts && detail != null) Surface(
            modifier = Modifier.fillMaxWidth(), shadowElevation = 8.dp,
            color = MaterialTheme.colorScheme.surface,
        ) {
            Button(onClick = {
                reviewConceptBatch(picked)
            }, enabled = approved && !busy && picked.isNotEmpty(), modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp).heightIn(min = 48.dp)) {
                Text(if (picked.isEmpty()) "Select concepts to generate" else "Generate · ${picked.size} concepts")
            }
        }
    }
    if (step in 0..2) FloatingActionButton(
        onClick = { navigateTo(3) },
        modifier = Modifier.align(androidx.compose.ui.Alignment.BottomEnd).padding(end = 24.dp, bottom = if (step == 2 && showCreateConcepts) 96.dp else 24.dp),
        shape = androidx.compose.foundation.shape.CircleShape,
        containerColor = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary,
    ) { Icon(DetailIcons.Gallery, "Open project gallery") }
    }
    if (showFilters) AlertDialog(onDismissRequest = { showFilters = false }, title = { Text("Filter concepts") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            FilterChip(selected = favouritesOnly, onClick = { favouritesOnly = !favouritesOnly }, label = { Text("★ Favourites only ("+favouriteVisibleCount+")") })
            Text(favouriteVisibleCount.toString()+" available here · "+favourites.size+" saved on server", style = MaterialTheme.typography.bodySmall)
            ServerChoice("Catalog status", archiveFilter, listOf("active", "archived", "all"), enabled = true,
                labels = mapOf("active" to "Active", "archived" to "Archived", "all" to "All")) { archiveFilter = it; picked = emptySet(); collectionFilter = "" }
            ServerChoice("Disliked concepts", dislikeFilter, listOf("hide", "only", "all"), enabled = true,
                labels = mapOf("hide" to "Hide disliked", "only" to "Disliked only", "all" to "Show all")) { dislikeFilter = it }
            ServerChoice("Created in this project", progressFilter, listOf("all", "created", "uncreated", "active", "failed"), enabled = true,
                labels = mapOf("all" to "All concepts", "created" to "Has images", "uncreated" to "Not created", "active" to "Creating", "failed" to "Failed, no image")) { progressFilter = it }
            ServerChoice("Gom nhóm theo", groupMode, listOf("Bộ concept", "Tư thế / hoạt động", "Bối cảnh"), enabled = true) { groupMode = it }
            ServerChoice("Group", groupFilter, groupOptions, enabled = true) { groupFilter = it }
        }
    }, confirmButton = { TextButton(onClick = { showFilters = false; scope.launch { lists[2].scrollToItem(0) } }) { Text("Done") } }, dismissButton = { TextButton(onClick = { favouritesOnly = false; archiveFilter = "active"; collectionFilter = ""; dislikeFilter = "hide"; groupFilter = "All groups"; progressFilter = "all"; query = "" }) { Text("Reset") } })
    if (showSetups && project != null) SetupLibrarySheet(
        setupStore, GenerationSetup("", "", choices.toString(), generationTargets(project!!, presets, providers), masterCount, customCount), busy, error,
        onApply = { setup -> action {
            choicesError(JSONObject(setup.choices))?.let { throw IllegalArgumentException(it) }
            client.applyGenerationTargets(origin, projectId, setup.name, setup.steps)
            saveChoices(JSONObject(setup.choices)); masterCount = setup.masterCount; customCount = setup.customCount
            showSetups = false; notice = "Applied ${setup.name}"
        } }, onDismiss = { showSetups = false },
    )
    generationDraft?.let { draft ->
        val currentProject = project
        if (currentProject != null) {
            val initialTargets = generationTargets(currentProject, presets, providers)
            val masterImage = workflow.rows("masters").find { it.optString("id") == (if (draft.path.endsWith("/outfit")) draft.path.split("/").getOrNull(1) else workflow.realId("approved_master_id")) }?.optJSONObject("job")?.outputs()?.firstOrNull()
            GenerationReviewSheet(origin, draft, initialTargets, choices, stylingMenu, providers, masterImage, currentProject.assets.count { it.selected }, setupStore, referencePhotos = currentProject.assets,
                onEditMaster = { generationDraft = null; navigateTo(1) },
                onEditConcepts = { generationDraft = null; showCreateConcepts = true },
                onDismiss = { generationDraft = null },
                onConfirm = { reviewed, targets, styling ->
                    generationDraft = null
                    action {
                        if (targets != initialTargets) client.applyGenerationTargets(origin, projectId, "Mobile generation setup", targets)
                        if (reviewed.payload.has("choices")) saveChoices(styling)
                        if (reviewed.purpose == "master" && !reviewed.path.endsWith("/outfit")) {
                            masterCount = reviewed.payload.optInt("variants", masterCount)
                            masterOutfitId = reviewed.payload.optJSONObject("master_outfit")?.optString("outfit")?.let { "preset:$it" } ?: reviewed.payload.optString("outfit_reference_asset_id").takeUnless { it == "null" }.orEmpty()
                        }
                        if (reviewed.payload.optBoolean("custom")) customCount = reviewed.payload.optInt("count", customCount)
                        val queued = client.projectAction(origin, projectId, reviewed.path, JSONObject(reviewed.payload.toString()).put("confirmed", true))
                        if (reviewed.path == "concepts/generate") {
                            val created = queued.optJSONArray("concept_ids")
                            val firstId = created?.optString(0).orEmpty()
                            concepts = client.projectArray(origin, projectId, "concepts")
                            selectedBatch = concepts.find { it.optString("id") == firstId }?.optInt("run")
                            showCreateConcepts = false
                            navigateTo(2)
                        }
                        if (reviewed.path.endsWith("/outfit")) navigateTo(1)
                        notice = "Queued ${generationImageCount(reviewed)} images"
                        library.queueRevision++
                    }
                },
            )
        }
    }
    if (settings) ProjectSettingsDialog(project, providers, client, origin, projectId, presets = presets, onPrompts = { settings = false; showProjectPrompts = true }, onSaved = { settings = false; action {} }, onDismiss = { settings = false })
    confirmation?.let { (message, operation) -> AlertDialog(onDismissRequest = { confirmation = null }, title = { Text("Confirm") }, text = { Text(message) }, confirmButton = { TextButton(onClick = { confirmation = null; operation() }) { Text("Continue") } }, dismissButton = { TextButton(onClick = { confirmation = null }) { Text("Cancel") } }) }
    edit?.let { source -> ConceptEditor(source, { edit = null }) { title, brief ->
        edit = null
        if (source.has("job")) generate("concepts/${source.getString("id")}/regenerate", JSONObject().put("title", title).put("brief", brief))
        else {
            val payload = JSONObject().put("titles", JSONObject().put(source.optInt("slot").toString(), title)).put("briefs", JSONObject().put(source.optInt("slot").toString(), brief))
            if (source.optInt("run") == 0) payload.put("slots", JSONArray(listOf(source.optInt("slot")))) else payload.put("proposal_ids", JSONArray(listOf(source.getString("id"))))
            generate("concepts/generate", payload)
        }
    } }
    detailConcept?.let { row ->
        val photoRows = projectProgress[conceptIdentity(row)]?.rows.orEmpty()
        val detailPhotos = photoRows.flatMap { result ->
            val job = result.optJSONObject("job") ?: JSONObject()
            job.outputs().map { id -> conceptGalleryPhoto(id, projectId, project?.name.orEmpty(), result, gallery.find { it.id == id }) }
        }.distinctBy { it.id }
        val id = row.getString("id")
        ConceptDetail(origin, row, detailPhotos, id in picked,
            disliked = conceptIdentity(row) in dislikes,
            onToggleDislike = { toggleDislike(row) },
            onDismiss = { detailConcept = null },
            onChoose = {
                val adding = id !in picked
                picked = if (adding) picked + id else picked - id
                detailConcept = null
            },
            onEdit = { detailConcept = null; edit = row },
            onDeleted = { deleted -> galleryFeed.remove(deleted); action {} },
            onOpenProject = { destination -> detailConcept = null; onOpenProject(destination) },
        )
    }
    historyKey?.let { key ->
        AlertDialog(onDismissRequest = { historyKey = null }, title = { Text("Results in "+project?.name.orEmpty()) }, text = {
            LazyColumn(Modifier.heightIn(max = 500.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(projectProgress[key]?.rows.orEmpty(), key = { it.getString("id") }) { row ->
                    Column {
                        val job = row.optJSONObject("job") ?: JSONObject()
                        Text("Batch "+row.optInt("run")+" · v"+row.optInt("revision")+" · "+job.optString("status"), style = MaterialTheme.typography.labelLarge)
                        job.outputs().forEach { id -> ResultImage(origin, id) { preview = id } }
                        job.realId("error_message")?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }, confirmButton = { TextButton(onClick = { historyKey = null }) { Text("Close") } })
    }
    if (showProjectPrompts) {
        val purpose = if (step == 2) "concept" else "master"
        val target = project?.generationTarget(purpose, presets)
        val template = if (purpose == "master" && target?.provider == "bfl") "master_flux" else purpose
        ProjectPromptsDialog(client, origin, projectId, template) { showProjectPrompts = false }
    }
    if (showStyling) ConceptStylingDialog(choices, stylingMenu, { showStyling = false }) { next -> saveChoices(next); showStyling = false }
    promptEdit?.let { source -> PromptEditorDialog(source, { promptEdit = null }) { prompt ->
        promptEdit = null
        generate("concepts/"+source.getString("id")+"/regenerate", JSONObject().put("prompt", prompt))
    } }
    preview?.let { selected ->
        val conceptPhotos = concepts.flatMap { row ->
            val job = row.optJSONObject("job") ?: JSONObject()
            job.outputs().map { id -> GalleryItem(id, projectId, project?.name.orEmpty(), "concept", "$id.png",
                prompt = job.optString("prompt"), provider = job.optString("provider"), model = job.optString("model"), createdAt = job.optString("created_at")) }
        }
        val photos = (gallery + conceptPhotos).distinctBy { it.id }
        val ids = (photos.map { it.id } + project?.assets.orEmpty().map { it.id } + workflow.rows("masters").flatMap { it.optJSONObject("job")?.outputs().orEmpty() } + selected).distinct()
        ImageViewer(origin, selected, imageIds = ids, photos = photos, onOpenProject = { preview = null; navigateTo(0) }) { preview = null }
    }
}

@Composable
private fun BriefText(brief: JSONObject?) { if (brief != null) listOf("setting", "activity", "outfit", "pose", "lighting").forEach { key -> brief.optString(key).takeIf { it.isNotBlank() }?.let { Text("${key.replaceFirstChar { it.uppercase() }}: $it", style = MaterialTheme.typography.bodyMedium) } } }
@Composable
internal fun ResultImage(origin: String, id: String, onClick: () -> Unit) { AsyncImage("$origin/api/assets/$id/content", "Generated image", Modifier.fillMaxWidth().height(320.dp).clickable(onClick = onClick), contentScale = ContentScale.Fit) }
internal fun saveImage(context: android.content.Context, origin: String, id: String, filename: String, showToast: Boolean = true): Boolean {
    val request = DownloadManager.Request(Uri.parse("$origin/api/assets/$id/download?format=original")).setTitle(filename).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED).setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, filename)
    return try {
        val manager = context.getSystemService(DownloadManager::class.java) ?: error("Downloads unavailable")
        manager.enqueue(request)
        if (showToast) android.widget.Toast.makeText(context, "Saving to Downloads…", android.widget.Toast.LENGTH_SHORT).show()
        true
    } catch (e: Exception) {
        android.widget.Toast.makeText(context, "Save failed: "+e.message, android.widget.Toast.LENGTH_LONG).show()
        false
    }
}
@Composable
private fun ConceptEditor(source: JSONObject, onDismiss: () -> Unit, onGenerate: (String, JSONObject) -> Unit) {
    var title by remember(source) { mutableStateOf(source.optString("title", source.optString("mood"))) }
    val original = source.optJSONObject("brief") ?: JSONObject()
    var fields by remember(source) { mutableStateOf(original.keys().asSequence().associateWith { original.optString(it) }) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Edit concept") }, text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedTextField(title, { title = it }, label = { Text("Title") }, modifier = Modifier.fillMaxWidth())
        fields.forEach { (key, value) -> OutlinedTextField(value, { fields = fields + (key to it) }, label = { Text(key.replaceFirstChar { it.uppercase() }) }, modifier = Modifier.fillMaxWidth()) }
    } }, confirmButton = { TextButton(onClick = { onGenerate(title, JSONObject(fields)) }, enabled = title.isNotBlank()) { Text("Generate") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
private fun PromptEditorDialog(source: JSONObject, onDismiss: () -> Unit, onGenerate: (String) -> Unit) {
    var prompt by remember(source) { mutableStateOf(source.optJSONObject("job")?.optString("prompt").orEmpty()) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Edit full prompt") }, text = {
        OutlinedTextField(prompt, { prompt = it }, modifier = Modifier.fillMaxWidth().heightIn(max = 400.dp), minLines = 6, label = { Text("Prompt") })
    }, confirmButton = { TextButton(onClick = { onGenerate(prompt.trim()) }, enabled = prompt.isNotBlank()) { Text("Generate new version") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}
