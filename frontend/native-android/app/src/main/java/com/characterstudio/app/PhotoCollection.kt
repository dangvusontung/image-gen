package com.characterstudio.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage

internal data class CollectionPhoto(val id: String, val label: String, val selected: Boolean)

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
internal fun PhotoCollection(
    origin: String, photos: List<CollectionPhoto>, busy: Boolean, modifier: Modifier = Modifier,
    onChoose: (String) -> Unit, onDeleted: (String) -> Unit,
    photoInfo: List<GalleryItem> = emptyList(), onOpenProject: ((String) -> Unit)? = null,
    projectId: String = "", projectName: String = "", purpose: String = "reference",
    pendingPhotos: List<PendingPhoto> = emptyList(),
    header: @Composable () -> Unit,
) {
    val curation = rememberPhotoCuration(origin)
    var bestOnly by remember { mutableStateOf(false) }
    val shownPhotos = if (bestOnly) photos.filter { curation.isBest(it.id) } else photos
    var viewingMetadata by remember { mutableStateOf<List<GalleryItem>>(emptyList()) }
    var batchBusy by remember { mutableStateOf(false) }
    var selectionMode by remember { mutableStateOf(false) }
    var selectedIds by remember { mutableStateOf(setOf<String>()) }
    BackHandler(enabled = selectionMode) { if (!batchBusy) { selectionMode = false; selectedIds = emptySet() } }
    fun toggle(id: String) { if (batchBusy) return; selectedIds = if (id in selectedIds) selectedIds - id else selectedIds + id }
    val metadata = photos.map { entry -> photoInfo.find { it.id == entry.id } ?: GalleryItem(entry.id, projectId, projectName, purpose, if (purpose == "reference") entry.label else "${entry.id}.png") }
    var preview by remember { mutableStateOf<String?>(null) }
    Column(modifier) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(if (selectionMode) "${selectedIds.size} selected" else "${shownPhotos.size} photos", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
        if (!selectionMode) FilterChip(selected = bestOnly, onClick = { bestOnly = !bestOnly }, label = { Text("Best") })
        if (selectionMode) TextButton(enabled = !batchBusy, onClick = { selectedIds = shownPhotos.map { it.id }.toSet() }) { Text("All loaded") }
        TextButton(enabled = !batchBusy, onClick = { selectionMode = !selectionMode; selectedIds = emptySet() }) { Text(if (selectionMode) "Done" else "Select / compare") }
    }
    LazyVerticalGrid(
        columns = GridCells.Adaptive(110.dp), modifier = Modifier.weight(1f),
        contentPadding = PaddingValues(start = 8.dp, end = 8.dp, top = 8.dp, bottom = 96.dp), horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) { Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { header() } }
        if (shownPhotos.isEmpty() && (pendingPhotos.isEmpty() || bestOnly)) item(span = { GridItemSpan(maxLineSpan) }) { Text(if (bestOnly) "No Best photos yet. Mark one with the trophy in image detail." else "No photos yet.", Modifier.padding(16.dp)) }
        if (!bestOnly) items(pendingPhotos, key = { "pending-${it.id}" }) { GeneratingPhotoPlaceholder(it.label) }
        items(shownPhotos, key = { it.id }) { photo ->
            Box(Modifier.fillMaxWidth().aspectRatio(1f).combinedClickable(onClick = { if (selectionMode) toggle(photo.id) else { viewingMetadata = metadata.filter { item -> shownPhotos.any { it.id == item.id } }; preview = photo.id } }, onLongClick = { selectionMode = true; toggle(photo.id) })) {
                AsyncImage("$origin/api/assets/${photo.id}/content", photo.label, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                if (curation.isBest(photo.id)) BestPhotoBadge(Modifier.align(Alignment.BottomStart).padding(4.dp))
                Surface(Modifier.align(Alignment.TopEnd).padding(4.dp), shape = androidx.compose.foundation.shape.CircleShape, color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f)) {
                    Checkbox(if (selectionMode) photo.id in selectedIds else photo.selected, onCheckedChange = { if (selectionMode) toggle(photo.id) else onChoose(photo.id) }, enabled = !busy && !batchBusy)
                }
            }
        }
    }
    if (selectionMode) Surface(shadowElevation = 6.dp) {
        BatchPhotoActions(origin, metadata.filter { it.id in selectedIds }, onProcessed = { selectedIds = selectedIds - it }, onDeleted = onDeleted, onChoose = if (purpose == "master") onChoose else null, onBusyChange = { batchBusy = it })
    }
    }
    preview?.let { id ->
        ImageViewer(origin, id, imageIds = viewingMetadata.map { it.id }, photos = viewingMetadata, onOpenProject = onOpenProject?.let { open -> { projectId -> preview = null; open(projectId) } }, selectedIds = photos.filter { it.selected }.map { it.id }.toSet(),
            onChoose = { chosen -> if (purpose == "master") preview = null; onChoose(chosen) }, choosing = busy,
            onDeleted = { deleted -> onDeleted(deleted); preview = null }) { preview = null }
    }
}
