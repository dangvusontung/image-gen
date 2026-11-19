package com.characterstudio.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
internal fun PhotoGallery(origin: String, photos: List<GalleryItem>, modifier: Modifier = Modifier, onOpenProject: ((String) -> Unit)? = null, feed: PagedFeed<GalleryItem>? = null, gridState: LazyGridState = rememberLazyGridState(), onRefresh: (() -> Unit)? = null, bottomPadding: androidx.compose.ui.unit.Dp = 0.dp, pendingPhotos: List<PendingPhoto> = emptyList(), searchProjectId: String? = null, statusItems: (LazyGridScope.() -> Unit)? = null, onDeleted: (String) -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val curation = rememberPhotoCuration(origin)
    val repository = remember(origin, searchProjectId) { PhotoSearchRepository(context.applicationContext, origin, searchProjectId) }
    var showSearch by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var selectedTag by remember { mutableStateOf("") }
    var bestOnly by remember { mutableStateOf(false) }
    var indexedPhotos by remember { mutableStateOf<List<GalleryItem>?>(null) }
    var indexLoading by remember { mutableStateOf(false) }
    var indexTotal by remember { mutableIntStateOf(0) }
    var indexError by remember { mutableStateOf<String?>(null) }
    var indexRevision by remember { mutableIntStateOf(0) }
    var batchBusy by remember { mutableStateOf(false) }
    var selectionMode by remember { mutableStateOf(false) }
    var selectedIds by remember { mutableStateOf(setOf<String>()) }
    var selected by remember { mutableStateOf<String?>(null) }
    var viewerPhotos by remember { mutableStateOf<List<GalleryItem>>(emptyList()) }
    var visiblePhotos by remember { mutableStateOf(photos) }
    val filtering = showSearch || bestOnly
    val sourcePhotos = when {
        bestOnly && feed != null -> curation.best.map { it.photo }.filter { searchProjectId == null || it.projectId == searchProjectId }
        bestOnly -> photos.filter { curation.isBest(it.id) }
        showSearch && feed != null -> indexedPhotos ?: photos
        else -> photos
    }
    var tags by remember { mutableStateOf<List<String>>(emptyList()) }
    LaunchedEffect(sourcePhotos) {
        tags = withContext(Dispatchers.Default) { sourcePhotos.flatMap { it.tags }.filter { it.length <= 40 }.groupBy(::searchable).values.sortedByDescending { it.size }.take(12).map { it.first() } }
    }
    BackHandler(enabled = selectionMode) { if (!batchBusy) { selectionMode = false; selectedIds = emptySet() } }
    fun toggle(id: String) { if (batchBusy) return; selectedIds = if (id in selectedIds) selectedIds - id else selectedIds + id }
    fun open(photo: GalleryItem) { viewerPhotos = visiblePhotos; selected = photo.id }
    LaunchedEffect(sourcePhotos, query, selectedTag, showSearch) {
        if (showSearch && query.isNotBlank()) delay(250)
        visiblePhotos = withContext(Dispatchers.Default) { sourcePhotos.filter { matchesPhoto(it, if (showSearch) query else "", if (showSearch) selectedTag else "") } }
    }
    LaunchedEffect(showSearch, bestOnly, indexRevision, repository) {
        if (!showSearch || feed == null || bestOnly) return@LaunchedEffect
        indexLoading = true; indexError = null
        try {
            val cached = repository.read()
            if (cached != null) { indexedPhotos = cached.photos; indexTotal = cached.photos.size }
            if (cached?.fresh != true || indexRevision > 0) {
                indexedPhotos = repository.refresh { rows, total -> indexedPhotos = rows; indexTotal = total }.photos
            }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { indexError = e.message }
        finally { indexLoading = false }
    }
    LaunchedEffect(feed, gridState, filtering) {
        if (feed != null && !filtering) snapshotFlow { gridState.layoutInfo.visibleItemsInfo.lastOrNull()?.index to feed.items.size }.collect { (last, size) ->
            if (last != null && last >= size - 12 && feed.error == null) feed.loadMore()
        }
    }
    LaunchedEffect(query, selectedTag, bestOnly) { gridState.scrollToItem(0) }
    androidx.compose.material3.pulltorefresh.PullToRefreshBox(isRefreshing = feed?.refreshing == true, onRefresh = { if (showSearch) indexRevision++; if (onRefresh != null) onRefresh() else feed?.refresh() }, modifier = modifier) {
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Text(if (selectionMode) "${selectedIds.size} selected" else if (filtering) "${visiblePhotos.size} matches" else "${feed?.total ?: photos.size} photos", Modifier.weight(1f), style = MaterialTheme.typography.labelLarge)
            if (selectionMode) TextButton(enabled = !batchBusy, onClick = { selectedIds = visiblePhotos.map { it.id }.toSet() }) { Text("All shown") }
            else {
                FilterChip(selected = bestOnly, onClick = { bestOnly = !bestOnly }, label = { Text("Best") }, leadingIcon = { Icon(DetailIcons.Best, "Filter Best photos", Modifier.size(16.dp)) })
                IconButton(onClick = { showSearch = !showSearch; if (!showSearch) { query = ""; selectedTag = "" } }) { Icon(DetailIcons.Search, "Search tags and prompts") }
            }
            TextButton(enabled = !batchBusy, onClick = { selectionMode = !selectionMode; selectedIds = emptySet() }) { Text(if (selectionMode) "Done" else "Select") }
        }
        if (showSearch && !selectionMode) {
            OutlinedTextField(query, { query = it }, placeholder = { Text("Search tags, prompt or project…") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp), trailingIcon = { if (query.isNotBlank()) IconButton(onClick = { query = "" }) { Icon(DetailIcons.Close, "Clear search") } })
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                if (selectedTag.isNotBlank()) InputChip(selected = true, onClick = { selectedTag = "" }, label = { Text("$selectedTag ×") })
                tags.filterNot { searchable(it) == searchable(selectedTag) }.forEach { tag -> SuggestionChip(onClick = { selectedTag = tag }, label = { Text(tag) }) }
            }
            if (indexLoading) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text("Searching library · ${indexedPhotos?.size ?: 0} / $indexTotal photos", Modifier.padding(horizontal = 12.dp), style = MaterialTheme.typography.labelSmall)
            }
            indexError?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error); TextButton(onClick = { indexRevision++ }) { Text("Retry search") } }
        }
        feed?.error?.let { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error) }
        LazyVerticalGrid(
            columns = GridCells.Adaptive(110.dp), modifier = Modifier.weight(1f), state = gridState,
            contentPadding = PaddingValues(start = 2.dp, end = 2.dp, top = 2.dp, bottom = bottomPadding + 2.dp),
            horizontalArrangement = Arrangement.spacedBy(2.dp), verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            if (!filtering) statusItems?.invoke(this)
            if (visiblePhotos.isEmpty() && ((pendingPhotos.isEmpty() && statusItems == null) || filtering)) item(span = { GridItemSpan(maxLineSpan) }) {
                if (feed?.loading == true || indexLoading) CircularProgressIndicator(Modifier.padding(16.dp))
                else Text(if (bestOnly) "No Best photos here. Mark a photo with the trophy in image detail." else if (showSearch) "No matching images." else "No generated images yet. Pull down to refresh.", Modifier.padding(16.dp))
            }
            if (!filtering) items(pendingPhotos, key = { "pending-${it.id}" }) { GeneratingPhotoPlaceholder(it.label) }
            items(visiblePhotos, key = { it.id }) { photo ->
                Box {
                    AsyncImage("$origin/api/assets/${photo.id}/content", "${photo.projectName} · ${photo.purpose}", Modifier.fillMaxWidth().aspectRatio(1f).combinedClickable(onClick = { if (selectionMode) toggle(photo.id) else open(photo) }, onLongClick = { selectionMode = true; toggle(photo.id) }), contentScale = ContentScale.Crop)
                    if (curation.isBest(photo.id)) BestPhotoBadge(Modifier.align(androidx.compose.ui.Alignment.BottomStart).padding(4.dp))
                    if (selectionMode) Surface(Modifier.align(androidx.compose.ui.Alignment.TopEnd).padding(4.dp), shape = androidx.compose.foundation.shape.CircleShape, color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)) {
                        Checkbox(photo.id in selectedIds, enabled = !batchBusy, onCheckedChange = { toggle(photo.id) })
                    }
                }
            }
            if (!filtering && feed?.hasMore == true) item(span = { GridItemSpan(maxLineSpan) }) {
                if (feed.loading) CircularProgressIndicator(Modifier.padding(16.dp))
                else TextButton(onClick = { feed.loadMore() }) { Text(if (feed.error != null) "Retry loading more" else "Load more") }
            }
        }
        if (selectionMode) Surface(shadowElevation = 6.dp) {
            BatchPhotoActions(origin, visiblePhotos.filter { it.id in selectedIds }, onProcessed = { selectedIds = selectedIds - it }, onDeleted = { deleted -> indexedPhotos = indexedPhotos?.filterNot { it.id == deleted }; onDeleted(deleted) }, onBusyChange = { batchBusy = it })
        }
    }
    }
    selected?.let { id ->
        ImageViewer(origin, id, photo = viewerPhotos.find { it.id == id }, onOpenProject = onOpenProject?.let { open -> { projectId -> selected = null; open(projectId) } }, imageIds = viewerPhotos.map { it.id }, photos = viewerPhotos, onDeleted = { deleted -> indexedPhotos = indexedPhotos?.filterNot { it.id == deleted }; onDeleted(deleted); selected = null }) { selected = null }
    }
}
