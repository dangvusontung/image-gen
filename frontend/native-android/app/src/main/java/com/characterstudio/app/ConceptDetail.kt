package com.characterstudio.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import org.json.JSONObject
import kotlinx.coroutines.launch

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
internal fun ConceptDetail(origin: String, row: JSONObject, photos: List<GalleryItem>, selected: Boolean, disliked: Boolean, onToggleDislike: () -> Unit, onDismiss: () -> Unit, onChoose: () -> Unit, onEdit: () -> Unit, onDeleted: (String) -> Unit, onOpenProject: (String) -> Unit) {
    val curation = rememberPhotoCuration(origin)
    var bestOnly by remember { mutableStateOf(false) }
    var viewingPhotos by remember { mutableStateOf<List<GalleryItem>>(emptyList()) }
    var imageSelection by remember { mutableStateOf(false) }
    var selectedImages by remember { mutableStateOf(setOf<String>()) }
    var batchBusy by remember { mutableStateOf(false) }
    fun toggleImage(id: String) { if (!batchBusy) selectedImages = if (id in selectedImages) selectedImages - id else selectedImages + id }
    var allProjects by remember { mutableStateOf(false) }
    var allPhotos by remember { mutableStateOf<List<GalleryItem>?>(null) }
    var loading by remember { mutableStateOf(false) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var retry by remember { mutableIntStateOf(0) }
    val context = androidx.compose.ui.platform.LocalContext.current
    val libraryCache = remember(origin) { ConceptLibraryRepository(context.applicationContext, origin) }
    val photoCache = remember(origin, conceptIdentity(row)) { ConceptPhotoCache(context.applicationContext, origin, conceptIdentity(row)) }
    LaunchedEffect(allProjects, retry) {
        if (!allProjects) return@LaunchedEffect
        loadError = null
        if (allPhotos == null && retry == 0) {
            val library = libraryCache.read()
            val cached = if (library != null) CachedConceptPhotos(library.entries[conceptIdentity(row)].orEmpty(), library.savedAt) else photoCache.read()
            if (cached != null) {
                allPhotos = cached.photos
                if (cached.fresh) return@LaunchedEffect
            }
        } else if (retry == 0) return@LaunchedEffect
        loading = true
        try {
            val index = libraryCache.refresh(force = retry > 0)
            val result = ConceptPhotoResults(index.entries[conceptIdentity(row)].orEmpty(), index.failedProjects)
            allPhotos = if (result.failedProjects == 0) result.photos else (result.photos + allPhotos.orEmpty()).distinctBy { it.id }
            if (result.failedProjects == 0) photoCache.write(result.photos)
            if (result.failedProjects > 0) loadError = "Could not load ${result.failedProjects} projects."
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { loadError = e.message ?: "Could not load images" }
        finally { loading = false }
    }
    val sourcePhotos = if (allProjects) (allPhotos.orEmpty() + photos).distinctBy { it.id } else photos
    val visiblePhotos = if (bestOnly) sourcePhotos.filter { curation.isBest(it.id) } else sourcePhotos
    val scope = rememberCoroutineScope()
    var preview by remember { mutableStateOf<String?>(null) }
    Dialog(onDismissRequest = { if (!batchBusy) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().safeDrawingPadding()) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    IconButton(enabled = !batchBusy, onClick = onDismiss) { Icon(DetailIcons.Back, "Back") }
                    Text("Concept details", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                    IconToggleButton(checked = disliked, onCheckedChange = { onToggleDislike() }) {
                        Icon(DetailIcons.Dislike, if (disliked) "Remove dislike" else "Dislike concept", tint = if (disliked) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    TextButton(enabled = !batchBusy, onClick = onEdit) { Text("Edit") }
                }
                LazyVerticalGrid(columns = GridCells.Fixed(2), modifier = Modifier.weight(1f), contentPadding = PaddingValues(16.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item(span = { GridItemSpan(maxLineSpan) }) {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text(conceptLabel(row), style = MaterialTheme.typography.headlineSmall)
                            if (archivedConcept(row)) Text("Archived concept", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.tertiary)
                            conceptCollectionName(row)?.let { name ->
                                Surface(shape = MaterialTheme.shapes.small, color = MaterialTheme.colorScheme.primaryContainer) {
                                    Text("Bộ · $name", Modifier.padding(horizontal = 12.dp, vertical = 6.dp), style = MaterialTheme.typography.labelLarge)
                                }
                            }
                            if (disliked) Text("Disliked · tap 👎 again to undo", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.error)
                            val tags = conceptTags(row)
                            if (tags.isNotEmpty()) Text(tags.joinToString(" · "), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("Prompt", style = MaterialTheme.typography.titleSmall)
                            val brief = row.optJSONObject("brief")
                            val prompt = brief?.keys()?.asSequence()?.mapNotNull { key ->
                                brief.optString(key).takeIf { it.isNotBlank() && it != "null" }?.let { "**${key.replaceFirstChar { it.uppercase() }}**\n\n$it" }
                            }?.joinToString("\n\n").orEmpty()
                            MarkdownPrompt(prompt.ifBlank { row.optString("title").ifBlank { "No prompt available" } })
                            HorizontalDivider()
                            Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Text(if (imageSelection) "${selectedImages.size} selected" else "Generated images · ${visiblePhotos.size}", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                                TextButton(enabled = !batchBusy, onClick = { imageSelection = !imageSelection; selectedImages = emptySet() }) { Text(if (imageSelection) "Done" else "Select") }
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                FilterChip(selected = !allProjects, enabled = !batchBusy, onClick = { allProjects = false; selectedImages = emptySet() }, label = { Text("This project") })
                                FilterChip(selected = bestOnly, enabled = !batchBusy, onClick = { bestOnly = !bestOnly; selectedImages = emptySet() }, label = { Text("Best") })
                                FilterChip(selected = allProjects, enabled = !batchBusy, onClick = { allProjects = true; selectedImages = emptySet() }, label = { Text("All projects") })
                            }
                            if (allProjects) TextButton(onClick = { retry++ }, enabled = !loading) { Text(if (loading) "Updating…" else "Refresh images") }
                            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                            loadError?.takeIf { allProjects }?.let { message ->
                                Text(message, color = MaterialTheme.colorScheme.error)
                                TextButton(onClick = { retry++ }) { Text("Retry") }
                            }
                            if (visiblePhotos.isEmpty() && !loading) Text(if (bestOnly) "No Best photos for this concept yet." else "No images generated for this concept yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    items(visiblePhotos, key = { it.id }) { photo ->
                        Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainer) {
                            Column {
                                Box {
                                    AsyncImage("$origin/api/assets/${photo.id}/content", "Generated concept image", Modifier.fillMaxWidth().aspectRatio(1f).combinedClickable(onClick = { if (imageSelection) toggleImage(photo.id) else { viewingPhotos = visiblePhotos; preview = photo.id } }, onLongClick = { imageSelection = true; toggleImage(photo.id) }), contentScale = ContentScale.Crop)
                                    if (curation.isBest(photo.id)) BestPhotoBadge(Modifier.align(androidx.compose.ui.Alignment.BottomStart).padding(4.dp))
                                    if (imageSelection) Surface(Modifier.align(androidx.compose.ui.Alignment.TopEnd).padding(4.dp), shape = androidx.compose.foundation.shape.CircleShape, color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)) {
                                        Checkbox(photo.id in selectedImages, enabled = !batchBusy, onCheckedChange = { toggleImage(photo.id) })
                                    }
                                }
                                if (allProjects) Text(photo.projectName, Modifier.padding(horizontal = 8.dp, vertical = 6.dp), maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis, style = MaterialTheme.typography.labelMedium)
                            }
                        }
                    }
                }
                if (imageSelection) Surface(shadowElevation = 6.dp) {
                    BatchPhotoActions(origin, visiblePhotos.filter { it.id in selectedImages }, onProcessed = { selectedImages = selectedImages - it }, onDeleted = { deleted ->
                        allPhotos = allPhotos?.filterNot { it.id == deleted }; onDeleted(deleted)
                    }, onBusyChange = { batchBusy = it })
                }
                else Surface(shadowElevation = 6.dp) {
                    Button(onClick = onChoose, enabled = !disliked || selected, modifier = Modifier.fillMaxWidth().padding(16.dp)) { Text(if (selected) "Deselect concept" else "Select concept") }
                }
            }
        }
        preview?.let { id ->
            ImageViewer(origin, id, imageIds = viewingPhotos.map { it.id }, photos = viewingPhotos, onOpenProject = { projectId -> preview = null; onOpenProject(projectId) }, onDeleted = { deleted ->
                preview = null
                allPhotos = allPhotos?.filterNot { it.id == deleted }
                allPhotos?.let { remaining -> scope.launch { photoCache.write(remaining, savedAt = 0) } }
                onDeleted(deleted)
            }) { preview = null }
        }
    }
}
