package com.characterstudio.app

import android.app.DownloadManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
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
internal fun ProjectScreen(origin: String, projectId: String, onBack: () -> Unit, initialStep: Int = 0) {
    val client = remember { BackendClient() }; val scope = rememberCoroutineScope(); val context = LocalContext.current
    var project by remember { mutableStateOf<ProjectDetail?>(null) }
    var workflow by remember { mutableStateOf(JSONObject()) }
    var concepts by remember { mutableStateOf(emptyList<JSONObject>()) }; var proposals by remember { mutableStateOf(emptyList<JSONObject>()) }
    var gallery by remember { mutableStateOf(emptyList<GalleryItem>()) }; var jobs by remember { mutableStateOf(emptyList<JobSummary>()) }
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
    var progressFilter by rememberSaveable(projectId) { mutableStateOf("all") }
    var historyKey by remember { mutableStateOf<String?>(null) }
    var groupFilter by rememberSaveable(projectId) { mutableStateOf("All groups") }
    var groupMode by rememberSaveable(projectId) { mutableStateOf("Tư thế / hoạt động") }
    var versions by remember { mutableStateOf(emptyMap<Int, String>()) }
    val stylingPrefs = remember { context.getSharedPreferences("concept-styling", android.content.Context.MODE_PRIVATE) }
    val stylingKey = origin+"/"+projectId
    var choices by remember(stylingKey) { mutableStateOf(runCatching {
        val defaults = defaultConceptChoices()
        val saved = JSONObject(stylingPrefs.getString(stylingKey, "{}").orEmpty())
        saved.keys().forEach { defaults.put(it, saved.get(it)) }; defaults
    }.getOrElse { defaultConceptChoices() }) }
    var stylingMenu by remember { mutableStateOf(JSONObject()) }
    var showStyling by remember { mutableStateOf(false) }
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
    var showProjectPrompts by remember { mutableStateOf(false) }
    var step by rememberSaveable(projectId) { mutableIntStateOf(initialStep) }; var picked by remember { mutableStateOf(setOf<String>()) }
    val stepHistory = remember(projectId) { mutableStateListOf<Int>() }
    fun navigateTo(next: Int) {
        if (next != step) { stepHistory.add(step); step = next }
    }
    var edit by remember { mutableStateOf<JSONObject?>(null) }; var preview by remember { mutableStateOf<String?>(null) }
    var selectedBatch by rememberSaveable(projectId) { mutableStateOf<Int?>(null) }
    var showCreateConcepts by rememberSaveable(projectId) { mutableStateOf(true) }
    var confirmation by remember { mutableStateOf<Pair<String, () -> Unit>?>(null) }
    BackHandler(enabled = preview == null && historyKey == null && !settings && !showProjectPrompts && edit == null && !showFilters && !showStyling && promptEdit == null && confirmation == null) {
        when {
            showSearch -> showSearch = false
            stepHistory.isNotEmpty() -> step = stepHistory.removeAt(stepHistory.lastIndex)
            else -> onBack()
        }
    }
    val titles = listOf("1. References", "2. Master", "3. Concepts", "4. Gallery", "5. History")
    val lists = titles.map { rememberLazyListState() }
    suspend fun refresh() {
        project = client.getProject(origin, projectId); presets = client.listPresets(origin); workflow = client.workflow(origin, projectId)
        concepts = client.projectArray(origin, projectId, "concepts"); proposals = client.projectArray(origin, projectId, "concept-proposals")
        val legacyMap = (proposals + concepts).filter { it.optString("bookmark_key").isNotBlank() }.associate {
            (it.optString("master_version_id")+":"+it.optInt("slot")) to it.getString("bookmark_key")
        }
        favouritePrefs.all.filterKeys { it.startsWith(origin+"/") }.forEach { (localKey, value) ->
            val old = (value as? Set<*>)?.filterIsInstance<String>()?.toSet() ?: emptySet()
            val migrated = old.filter { it in legacyMap }
            migrated.forEach { client.setBookmark(origin, legacyMap.getValue(it), true) }
            if (migrated.isNotEmpty()) favouritePrefs.edit().putStringSet(localKey, old - migrated.toSet()).apply()
        }
        gallery = client.listGallery(origin, projectId); jobs = client.listJobs(origin, projectId)
    }
    fun action(block: suspend () -> Unit) {
        if (busy) return
        busy = true; error = null
        scope.launch { try { block(); refresh() } catch (e: Exception) { error = e.message } finally { busy = false } }
    }
    fun generate(path: String, payload: JSONObject = JSONObject()) {
        val requestPayload = styledConceptPayload(path, payload, choices)
        if (requestPayload.has("choices")) choicesError(choices)?.let { error = it; showStyling = true; return }
        val purpose = when { path.startsWith("master/") -> "master"; path.startsWith("turnaround/") -> "turnaround"; else -> "concept" }
        val target = project?.generationTarget(purpose, presets)
        confirmation = ("Use "+target?.provider+" / "+target?.model+" · "+target?.size+" to generate images? Provider charges may apply.") to { action {
            client.projectAction(origin, projectId, path, requestPayload.put("confirmed", true)); notice = "Queued. Results update automatically."
        } }
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
    LaunchedEffect(projectId) {
        runCatching {
            stylingMenu = client.conceptOptions(origin, projectId)
            val outfits = stylingMenu.optJSONArray("outfit")
            if (outfits != null) {
                val allowed = (0 until outfits.length()).map { outfits.getJSONArray(it).getString(0) }
                if (choices.optString("outfit", "auto") !in allowed) saveChoices(JSONObject(choices.toString()).put("outfit", "auto"))
            }
        }.onFailure { error = it.message }
        runCatching { providers = client.listProviders(origin) }.onFailure { error = it.message }
        while (true) { try { refresh() } catch (e: Exception) { error = e.message }; delay(3000) }
    }
    val batches = concepts.map { it.optInt("run") }.distinct().sortedDescending()
    val activeBatch = selectedBatch?.takeIf { it in batches } ?: batches.firstOrNull()
    val batchConcepts = concepts.filter { it.optInt("run") == activeBatch }.sortedWith(compareBy<JSONObject> { it.optInt("slot") }.thenByDescending { it.optInt("revision") })
    val projectProgress = projectConceptProgress(concepts)
    fun progressOf(row: JSONObject) = projectProgress[conceptIdentity(row)] ?: ProjectConceptProgress()
    fun visible(row: JSONObject) = matchesConcept(row, query) && (!favouritesOnly || conceptIdentity(row) in favourites) && (groupFilter == "All groups" || conceptGroup(row) == groupFilter) && progressOf(row).matches(progressFilter)
    fun section(row: JSONObject) = if (groupMode == "Bối cảnh") conceptGroup(row) else row.optString("family").ifBlank { conceptGroup(row) }
    val visibleProposals = proposals.filter { visible(it) }.sortedBy { conceptOrder(it) }.groupBy { section(it) }
    val groupedResults = batchConcepts.groupBy { it.optInt("slot") }.mapValues { (_, rows) -> rows.sortedByDescending { it.optInt("revision") } }
    val visibleResults = groupedResults.values.filter { rows -> rows.any { visible(it) } }.groupBy { section(it.first()) }
    val groupOptions = listOf("All groups") + (proposals + batchConcepts).map { conceptGroup(it) }.distinct().sorted()
    val favouriteVisibleCount = if (showCreateConcepts) proposals.count { conceptIdentity(it) in favourites }
        else groupedResults.values.count { rows -> rows.any { conceptIdentity(it) in favourites } }
    val approved = workflow.realId("approved_master_id") != null; val detail = project
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("←") }
            Text(detail?.name ?: "Loading…", modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            TextButton(onClick = { navigateTo(3) }) { Text("Photos") }
            TextButton(onClick = { settings = true }, enabled = detail != null) { Text("Settings") }
        }
        ScrollableTabRow(selectedTabIndex = step, edgePadding = 8.dp) { titles.forEachIndexed { i, title -> Tab(selected = step == i, onClick = { navigateTo(i) }, text = { Text(title) }) } }
        bookmarkError?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error, maxLines = 2) }
        error?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error, maxLines = 3) }
        notice?.let { Text(it, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.primary) }
        if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (detail == null) { CircularProgressIndicator(Modifier.padding(24.dp)); return@Column }
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
                TextButton(onClick = { showFilters = true }) { Text(if (favouritesOnly || groupFilter != "All groups" || progressFilter != "all") "Filters •" else "Filters") }
            }
            if (showSearch) OutlinedTextField(query, { query = it }, placeholder = { Text("Search concepts…") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp), trailingIcon = { TextButton(onClick = { query = ""; showSearch = false }) { Text("×") } })
        }

        LazyColumn(state = lists[step], modifier = Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            when (step) {
                0 -> {
                    item {
                        Row { Checkbox(detail.rightsConfirmed, enabled = !busy, onCheckedChange = { checked -> action { client.updateProject(origin, projectId, checked) } }); Text("I have permission to use these images", Modifier.padding(top = 12.dp)) }
                        Button(onClick = { picker.launch("image/*") }, enabled = detail.rightsConfirmed && !busy, modifier = Modifier.fillMaxWidth()) { Text("Upload reference photos") }
                        Text("${detail.assets.count { it.selected }} of ${detail.assets.size} photos selected")
                        Button(onClick = { navigateTo(1) }, enabled = detail.rightsConfirmed && detail.assets.any { it.selected }, modifier = Modifier.fillMaxWidth()) { Text("Continue → Master") }
                    }
                    items(detail.assets, key = { it.id }) { asset -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            AsyncImage("$origin/api/assets/${asset.id}/content", asset.filename, Modifier.size(88.dp).clickable { preview = asset.id }, contentScale = ContentScale.Crop)
                            Column(Modifier.weight(1f)) { Text(asset.filename, maxLines = 2, overflow = TextOverflow.Ellipsis); Text(asset.kind); Row { Checkbox(asset.selected, enabled = !busy, onCheckedChange = { checked -> action { client.updateAsset(origin, asset.id, checked) } }); Text("Use photo", Modifier.padding(top = 12.dp)) } }
                        }
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                            TextButton(onClick = { saveImage(context, origin, asset.id, asset.filename) }) { Text("Save") }
                            TextButton(onClick = { confirmation = "Delete this reference photo?" to { action { client.deleteAsset(origin, asset.id) } } }) { Text("Delete") }
                        }
                    } } }
                }
                1 -> {
                    item {
                        Text("Create and approve your character", style = MaterialTheme.typography.titleLarge)
                        Text("${detail.provider} / ${detail.model}")
                        Button(onClick = { generate("master/generate", JSONObject().put("variants", 1).put("hairstyle", "reference")) }, enabled = !busy && detail.rightsConfirmed && detail.assets.any { it.selected }, modifier = Modifier.fillMaxWidth()) { Text("Generate master") }
                        Button(onClick = { navigateTo(2) }, enabled = approved, modifier = Modifier.fillMaxWidth()) { Text("Continue → Concepts") }
                    }
                    items(workflow.rows("masters"), key = { it.getString("id") }) { row -> val job = row.optJSONObject("job") ?: JSONObject()
                        Card { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("Master ${row.optInt("round")}/${row.optInt("variant")} · ${job.optString("status")}")
                            job.outputs().forEach { id -> ResultImage(origin, id) { preview = id } }
                            if (job.optString("status") == "succeeded") Button(onClick = { action { client.approveMaster(origin, projectId, row.getString("id")) } }, enabled = !busy && workflow.realId("approved_master_id") != row.getString("id")) { Text(if (workflow.realId("approved_master_id") == row.getString("id")) "Approved" else "Approve this master") }
                        } }
                    }
                }
                2 -> {
                    if (showCreateConcepts) {
                    item {
                        if (!approved) Text("Approve a master in step 2 first.")

                        Button(onClick = {
                            val selected = proposals.filter { it.getString("id") in picked }; val payload = JSONObject()
                            if (selected.firstOrNull()?.optInt("run") == 0) payload.put("slots", JSONArray(selected.map { it.optInt("slot") })) else payload.put("proposal_ids", JSONArray(selected.map { it.getString("id") }))
                            generate("concepts/generate", payload)
                        }, enabled = approved && !busy && picked.isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text("Generate selected (${picked.size})") }
                    }
                    item {
                        TextButton(onClick = { showAdvancedCreate = !showAdvancedCreate }) { Text(if (showAdvancedCreate) "Less options ▴" else "More creation options ▾") }
                        if (showAdvancedCreate) {
                        OutlinedButton(onClick = { confirmation = "Suggest new concepts with AI? Charges may apply." to { action { client.suggestConcepts(origin, projectId); picked = emptySet() } } }, enabled = approved && !busy) { Text("Suggest concepts with AI") }
                        ServerChoice("Images from styling only", customCount.toString(), listOf("1", "2", "3", "4"), enabled = !busy) { customCount = it.toInt() }
                        OutlinedButton(onClick = { generate("concepts/generate", JSONObject().put("custom", true).put("count", customCount)) }, enabled = approved && !busy && overridesConcept(choices)) { Text("Generate from outfit & scene only") }
                    }
                        }
                    visibleProposals.forEach { (group, rows) ->
                    item(key = "proposal-group-"+group) { Text(group, style = MaterialTheme.typography.titleLarge) }
                    items(rows, key = { "proposal-${it.getString("id")}" }) { row -> val id = row.getString("id")
                        var expanded by remember(id) { mutableStateOf(false) }
                        Card { Column(Modifier.fillMaxWidth().padding(12.dp)) {
                            Row { Checkbox(id in picked, onCheckedChange = { checked -> picked = if (checked) picked + id else picked - id }); Text(conceptLabel(row), Modifier.weight(1f).padding(top = 12.dp), style = MaterialTheme.typography.titleMedium); TextButton(onClick = { toggleFavourite(row) }, enabled = !bookmarkSaving) { Text(if (conceptIdentity(row) in favourites) "★" else "☆") } }
                            if (row.optString("catalog_code").isNotBlank()) Text("${row.optString("catalog_code")} · #${conceptOrder(row)} · ${row.optString("family")}", style = MaterialTheme.typography.labelSmall)
                            if (conceptTags(row).isNotEmpty()) Text(conceptTags(row).joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                            val state = progressOf(row)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Text(state.label(), modifier = Modifier.weight(1f), style = MaterialTheme.typography.labelMedium, color = if (state.imageIds.isNotEmpty()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                                if (state.rows.isNotEmpty()) TextButton(onClick = { historyKey = conceptIdentity(row) }) { Text("View results") }
                            }
                            Text(row.optJSONObject("brief")?.optString("setting").orEmpty(), maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall)
                            Row { TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Less" else "Details") }; TextButton(onClick = { edit = row }) { Text("Edit") } }
                            if (expanded) { Text(row.optString("title")); BriefText(row.optJSONObject("brief")) }
                        } }
                    }
                    }
                    }
                    if (!showCreateConcepts) {
                    item {
                        Text("Concept batches", style = MaterialTheme.typography.titleLarge)
                        ServerChoice("Batch", activeBatch?.toString().orEmpty(), batches.map { it.toString() }, enabled = batches.isNotEmpty(), labels = batches.associate { it.toString() to ("Batch #"+it+" · "+concepts.count { row -> row.optInt("run") == it }+" versions") }) { selectedBatch = it.toInt() }

                        if (batches.isEmpty()) Text("No generated batches yet. Choose Create new batch to start.")
                    }
                    item { Text("Batch #$activeBatch · ${batchConcepts.size} versions", style = MaterialTheme.typography.titleLarge) }
                    visibleResults.forEach { (group, slots) ->
                    item(key = "result-group-"+group) { Text(group, style = MaterialTheme.typography.titleLarge) }
                    items(slots, key = { "slot-"+it.first().optInt("slot") }) { revisions ->
                        val slot = revisions.first().optInt("slot")
                        val row = revisions.find { it.getString("id") == versions[slot] } ?: revisions.first()
                        val job = row.optJSONObject("job") ?: JSONObject()
                        var expanded by remember(row.getString("id")) { mutableStateOf(false) }
                        val canRerun = !busy && approved && job.optString("status") !in listOf("queued", "submitting", "running")
                        Card { Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("${conceptLabel(row)} · Run ${row.optInt("run")} / ${row.optInt("slot")} · v${row.optInt("revision")}", style = MaterialTheme.typography.titleMedium)
                            if (row.optString("catalog_code").isNotBlank()) Text("${row.optString("catalog_code")} · #${conceptOrder(row)} · ${row.optString("family")}", style = MaterialTheme.typography.labelSmall)
                            job.outputs().forEach { id -> ResultImage(origin, id) { preview = id } }
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                TextButton(onClick = { toggleFavourite(row) }) { Text(if (conceptIdentity(row) in favourites) "★" else "☆") }
                                Text(job.optString("status")+" · v"+row.optInt("revision"), modifier = Modifier.padding(top = 12.dp), style = MaterialTheme.typography.bodySmall)
                                TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Close ▴" else "Actions ▾") }
                            }
                            if (expanded) {
                            if (job.optString("status") in listOf("succeeded", "failed", "cancelled")) TextButton(onClick = { action { client.dismissJob(origin, job.getString("id")) } }, enabled = !busy) { Text("Move run to Trash") }
                            ServerChoice("Version", row.getString("id"), revisions.map { it.getString("id") }, enabled = revisions.size > 1,
                                labels = revisions.associate { it.getString("id") to ("v"+it.optInt("revision")+" · "+it.optJSONObject("job")?.optString("status")) }) { versions = versions + (slot to it) }
                            TextButton(onClick = { toggleFavourite(row) }) { Text(if (conceptIdentity(row) in favourites) "★ Favourite" else "☆ Favourite") }
                            job.optJSONObject("meta")?.optJSONObject("concept_choices")?.let { savedStyling ->
                                Text("Image styling: "+stylingSummary(savedStyling, stylingMenu), style = MaterialTheme.typography.bodySmall)
                                TextButton(onClick = { saveChoices(savedStyling); showStyling = true }) { Text("Reuse this image's styling") }
                            }
                            BriefText(row.optJSONObject("brief"))
                            job.realId("error_message")?.let { Text(it, color = MaterialTheme.colorScheme.error, maxLines = 4) }
                            OutlinedButton(onClick = { generate("concepts/"+row.getString("id")+"/regenerate", JSONObject().put("prompt_mode", "saved")) }, enabled = canRerun && !job.realId("prompt").isNullOrBlank()) { Text("Regenerate · saved prompt") }
                            OutlinedButton(onClick = { generate("concepts/"+row.getString("id")+"/regenerate", JSONObject().put("prompt_mode", "current")) }, enabled = canRerun) { Text("Regenerate · current prompt") }
                            OutlinedButton(onClick = { promptEdit = row }, enabled = canRerun) { Text("Edit full prompt & generate") }
                            OutlinedButton(onClick = { edit = row }, enabled = canRerun) { Text("Edit description & generate") }
                            if (job.optString("status") == "succeeded") Button(onClick = { confirmation = "Enhance this concept using the configured provider? Charges may apply." to { action { client.enhance(origin, projectId, row.getString("id")); notice = "Enhancement queued. View results in Gallery." } } }, enabled = !busy) { Text("Enhance image") }
                            }
                        } }
                    }
                    }
                }
                    }
                3 -> {
                    item { Text("Gallery (${gallery.size})", style = MaterialTheme.typography.titleLarge); Text("Masters, concepts and enhancements. Tap any image for a full screen preview.") }
                    if (gallery.isEmpty()) item { Text("No generated images yet.") }
                    items(gallery, key = { it.id }) { image -> Card { Column(Modifier.padding(12.dp)) {
                        ResultImage(origin, image.id) { preview = image.id }; Text(image.purpose, style = MaterialTheme.typography.titleMedium); Text(image.filename, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        OutlinedButton(onClick = { saveImage(context, origin, image.id, image.filename) }) { Text("Save original") }
                        TextButton(onClick = { action { client.trashAsset(origin, image.id) } }, enabled = !busy) { Text("Move image to Trash") }
                    } } }
                }
                4 -> {
                    item { Text("Generation history", style = MaterialTheme.typography.titleLarge) }
                    items(jobs, key = { it.id }) { job -> Card { Column(Modifier.fillMaxWidth().padding(12.dp)) {
                        Text("${job.purpose} · ${job.status}", style = MaterialTheme.typography.titleMedium); job.outputAssetIds.forEach { id -> ResultImage(origin, id) { preview = id } }; job.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        if (job.status in listOf("succeeded", "failed", "cancelled")) TextButton(onClick = { action { client.dismissJob(origin, job.id) } }, enabled = !busy) { Text("Move run to Trash") }
                        if (job.status in listOf("queued", "submitting", "running")) TextButton(onClick = { action { client.cancelJob(origin, job.id) } }) { Text("Cancel job") }
                        if (job.status in listOf("failed", "cancelled")) Row { TextButton(onClick = { confirmation = "Retry this generation? Provider charges may apply." to { action { client.retryJob(origin, job.id) } } }) { Text("Retry") } }
                    } } }
                }
            }
        }
    }
    if (showFilters) AlertDialog(onDismissRequest = { showFilters = false }, title = { Text("Filter concepts") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            FilterChip(selected = favouritesOnly, onClick = { favouritesOnly = !favouritesOnly }, label = { Text("★ Favourites only ("+favouriteVisibleCount+")") })
            Text(favouriteVisibleCount.toString()+" available here · "+favourites.size+" saved on server", style = MaterialTheme.typography.bodySmall)
            ServerChoice("Created in this project", progressFilter, listOf("all", "created", "uncreated", "active", "failed"), enabled = true,
                labels = mapOf("all" to "All concepts", "created" to "Has images", "uncreated" to "Not created", "active" to "Creating", "failed" to "Failed, no image")) { progressFilter = it }
            ServerChoice("Gom nhóm theo", groupMode, listOf("Tư thế / hoạt động", "Bối cảnh"), enabled = true) { groupMode = it }
            ServerChoice("Group", groupFilter, groupOptions, enabled = true) { groupFilter = it }
        }
    }, confirmButton = { TextButton(onClick = { showFilters = false; scope.launch { lists[2].scrollToItem(0) } }) { Text("Done") } }, dismissButton = { TextButton(onClick = { favouritesOnly = false; groupFilter = "All groups"; progressFilter = "all"; query = "" }) { Text("Reset") } })
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
    preview?.let { ImageViewer(origin, it) { preview = null } }
}

@Composable
private fun BriefText(brief: JSONObject?) { if (brief != null) listOf("setting", "activity", "outfit", "pose", "lighting").forEach { key -> brief.optString(key).takeIf { it.isNotBlank() }?.let { Text("${key.replaceFirstChar { it.uppercase() }}: $it", style = MaterialTheme.typography.bodyMedium) } } }
@Composable
internal fun ResultImage(origin: String, id: String, onClick: () -> Unit) { AsyncImage("$origin/api/assets/$id/content", "Generated image", Modifier.fillMaxWidth().height(320.dp).clickable(onClick = onClick), contentScale = ContentScale.Fit) }
@Composable
internal fun ImageViewer(origin: String, id: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    Dialog(onDismissRequest = onDismiss, properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)) { Surface(Modifier.fillMaxSize()) { Column(Modifier.safeDrawingPadding().padding(16.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { TextButton(onClick = onDismiss) { Text("Close") }; TextButton(onClick = { saveImage(context, origin, id, "$id.png") }) { Text("Save original") } }
        AsyncImage("$origin/api/assets/$id/content", "Full size image", Modifier.weight(1f).fillMaxWidth(), contentScale = ContentScale.Fit)
    } } }
}
internal fun saveImage(context: android.content.Context, origin: String, id: String, filename: String) {
    val request = DownloadManager.Request(Uri.parse("$origin/api/assets/$id/download?format=original")).setTitle(filename).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED).setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, filename)
    context.getSystemService(DownloadManager::class.java)?.enqueue(request)
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
