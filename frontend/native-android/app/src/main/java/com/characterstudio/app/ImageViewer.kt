package com.characterstudio.app

import androidx.compose.animation.core.animate
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ImageViewer(origin: String, id: String, photo: GalleryItem? = null, onOpenProject: ((String) -> Unit)? = null, onDeleted: ((String) -> Unit)? = null, imageIds: List<String> = listOf(id), photos: List<GalleryItem> = listOfNotNull(photo), selectedIds: Set<String> = emptySet(), onChoose: ((String) -> Unit)? = null, choosing: Boolean = false, onDismiss: () -> Unit) {
    val ids = imageIds.ifEmpty { listOf(id) }
    val pager = rememberPagerState(initialPage = ids.indexOf(id).coerceAtLeast(0), pageCount = { ids.size })
    val currentId = ids[pager.currentPage.coerceAtMost(ids.lastIndex)]
    val currentPhoto = photos.find { it.id == currentId }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val client = remember { BackendClient() }
    var scale by remember(currentId) { mutableFloatStateOf(1f) }
    var offset by remember(currentId) { mutableStateOf(Offset.Zero) }
    var controlsVisible by remember { mutableStateOf(true) }
    var zoomAnimation by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
    var confirmDelete by remember { mutableStateOf(false) }
    var deleting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showInfo by remember(currentId) { mutableStateOf(false) }
    val curation = rememberPhotoCuration(origin)
    var showEnhance by remember(currentId) { mutableStateOf(false) }
    var enhancementQueued by remember(currentId) { mutableStateOf(false) }
    var showMore by remember(currentId) { mutableStateOf(false) }
    var showRetry by remember(currentId) { mutableStateOf(false) }
    var saveFeedback by remember(currentId) { mutableStateOf(false) }
    val conceptCache = remember(origin) { mutableMapOf<String, List<org.json.JSONObject>>() }
    val enhancementCache = remember(origin) { mutableMapOf<String, List<org.json.JSONObject>>() }
    var identity by remember(currentId) { mutableStateOf(currentPhoto?.let { photoIdentity(it, emptyList(), emptyList()) }) }
    var bookmarks by remember(origin) { mutableStateOf(emptySet<String>()) }
    var bookmarksLoaded by remember(origin) { mutableStateOf(false) }
    var bookmarkSaving by remember { mutableStateOf(false) }
    LaunchedEffect(origin) {
        if (photos.none { it.purpose in listOf("concept", "enhance") }) return@LaunchedEffect
        try { bookmarks = client.listBookmarks(origin); bookmarksLoaded = true }
        catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { error = "Could not load bookmarks: "+e.message }
    }
    LaunchedEffect(currentId, currentPhoto) {
        val item = currentPhoto ?: return@LaunchedEffect
        if (item.purpose in listOf("concept", "enhance")) {
            try {
                val concepts = conceptCache[item.projectId] ?: client.projectArray(origin, item.projectId, "concepts").also { conceptCache[item.projectId] = it }
                val enhancements = if (item.purpose == "enhance") enhancementCache[item.projectId] ?: client.projectArray(origin, item.projectId, "enhancements").also { enhancementCache[item.projectId] = it } else emptyList()
                identity = photoIdentity(item, concepts, enhancements)
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { error = "Could not load concept details: "+e.message }
        }
    }
    val bestScope = currentPhoto?.let { bestPhotoScope(it, identity?.bookmarkKey ?: it.conceptKey) }
    Dialog(onDismissRequest = { if (!deleting) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        val dialogView = androidx.compose.ui.platform.LocalView.current
        SideEffect {
            (dialogView.parent as? androidx.compose.ui.window.DialogWindowProvider)?.window?.let { window ->
                androidx.core.view.WindowCompat.getInsetsController(window, dialogView).apply {
                    isAppearanceLightStatusBars = false
                    isAppearanceLightNavigationBars = false
                    systemBarsBehavior = androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                    if (controlsVisible) show(androidx.core.view.WindowInsetsCompat.Type.systemBars())
                    else hide(androidx.core.view.WindowInsetsCompat.Type.systemBars())
                }
            }
        }
        Surface(Modifier.fillMaxSize(), color = Color.Black, contentColor = Color.White) {
            Box(Modifier.fillMaxSize()) {
                HorizontalPager(state = pager, userScrollEnabled = scale == 1f && !deleting, modifier = Modifier.fillMaxSize()) { page ->
                val pageId = ids[page]
                Box(Modifier.fillMaxSize().clipToBounds()
                    .pointerInput(currentId) {
                        detectTapGestures(onTap = { controlsVisible = !controlsVisible }, onDoubleTap = { tap ->
                            zoomAnimation?.cancel()
                            val fromScale = scale
                            val fromOffset = offset
                            val targetScale = if (scale > 1f) 1f else 2.5f
                            val center = Offset(size.width / 2f, size.height / 2f)
                            val targetOffset = if (targetScale == 1f) Offset.Zero else (center - tap) * (targetScale - 1f)
                            zoomAnimation = scope.launch {
                                animate(0f, 1f, animationSpec = tween(280)) { progress, _ ->
                                    scale = fromScale + (targetScale - fromScale) * progress
                                    offset = fromOffset + (targetOffset - fromOffset) * progress
                                }
                            }
                        })
                    }
                    .pointerInput(currentId) {
                        awaitEachGesture {
                            awaitFirstDown(requireUnconsumed = false)
                            do {
                                val event = awaitPointerEvent()
                                if (event.changes.any { it.pressed && it.previousPressed } && (event.changes.count { it.pressed } > 1 || scale > 1f)) {
                                    zoomAnimation?.cancel()
                                    val centroid = event.calculateCentroid(useCurrent = false)
                                    val pan = event.calculatePan()
                                    val next = (scale * event.calculateZoom()).coerceIn(1f, 6f)
                                    val center = Offset(size.width / 2f, size.height / 2f)
                                    val ratio = next / scale
                                    val proposed = (offset + center - centroid) * ratio + centroid - center + pan
                                    offset = Offset(
                                        proposed.x.coerceIn(-size.width * (next - 1) / 2, size.width * (next - 1) / 2),
                                        proposed.y.coerceIn(-size.height * (next - 1) / 2, size.height * (next - 1) / 2),
                                    )
                                    scale = next
                                    event.changes.forEach { it.consume() }
                                }
                            } while (event.changes.any { it.pressed })
                        }
                    }) {
                    AsyncImage("$origin/api/assets/$pageId/content", "Full size image",
                        Modifier.fillMaxSize().graphicsLayer {
                            scaleX = scale; scaleY = scale; translationX = offset.x; translationY = offset.y
                        }, contentScale = ContentScale.Fit)
                }
                }
                if (controlsVisible && currentPhoto != null && scale <= 1f) Surface(
                    modifier = Modifier.align(androidx.compose.ui.Alignment.TopCenter).safeDrawingPadding().padding(horizontal = 12.dp, vertical = 8.dp),
                    shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
                    color = Color.Transparent, contentColor = Color.White,
                ) {
                    Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 6.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Column(Modifier.weight(1f).clickable(enabled = onOpenProject != null) { onOpenProject?.invoke(currentPhoto.projectId) }) {
                            Text(currentPhoto.projectName, style = MaterialTheme.typography.titleMedium.copy(shadow = androidx.compose.ui.graphics.Shadow(Color.Black, Offset.Zero, 6f)), maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                            Text(identity?.title ?: currentPhoto.purpose, style = MaterialTheme.typography.bodySmall.copy(shadow = androidx.compose.ui.graphics.Shadow(Color.Black, Offset.Zero, 6f)), maxLines = 2, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                        }
                        IconToggleButton(checked = curation.isBest(currentId), enabled = bestScope != null || curation.isBest(currentId), onCheckedChange = {
                            currentPhoto?.let { item ->
                                val key = curation.best.find { it.photo.id == currentId }?.scope ?: bestScope
                                if (key != null) curation.toggle(key, item.copy(conceptKey = identity?.bookmarkKey ?: item.conceptKey, tags = (item.tags + identity?.tags.orEmpty()).distinct()))
                            }
                        }) { Icon(DetailIcons.Best, if (curation.isBest(currentId)) "Remove Best" else "Mark as Best", tint = if (curation.isBest(currentId)) Color(0xFFFFD166) else Color.White) }
                        identity?.bookmarkKey?.let { key ->
                            IconToggleButton(checked = key in bookmarks, enabled = bookmarksLoaded && !bookmarkSaving, onCheckedChange = { desired ->
                                bookmarkSaving = true
                                scope.launch {
                                    try {
                                        client.setBookmark(origin, key, desired)
                                        bookmarks = if (desired) bookmarks + key else bookmarks - key
                                    } catch (e: kotlinx.coroutines.CancellationException) { throw e }
                                    catch (e: Exception) { error = "Could not save bookmark: "+e.message }
                                    finally { bookmarkSaving = false }
                                }
                            }) {
                                if (bookmarkSaving) CircularProgressIndicator(Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                                else Icon(if (key in bookmarks) DetailIcons.StarFilled else DetailIcons.Star, if (key in bookmarks) "Remove concept bookmark" else "Bookmark concept", tint = Color.White)
                            }
                        }
                    }
                }
                if (controlsVisible) Column(Modifier.align(androidx.compose.ui.Alignment.BottomCenter).safeDrawingPadding().padding(horizontal = 20.dp, vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                error?.let { Text(it, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error) }
                if (enhancementQueued) Surface(shape = MaterialTheme.shapes.medium, color = Color.White.copy(alpha = 0.95f), contentColor = Color.Black) {
                    Text("Enhancement queued", Modifier.padding(horizontal = 16.dp, vertical = 8.dp), style = MaterialTheme.typography.labelMedium)
                }
                if (saveFeedback) Surface(shape = MaterialTheme.shapes.medium, color = Color.White.copy(alpha = 0.95f), contentColor = Color.Black) {
                    Text("Saving to Downloads…", Modifier.padding(horizontal = 16.dp, vertical = 8.dp), style = MaterialTheme.typography.labelMedium)
                }
                Surface(shape = androidx.compose.foundation.shape.CircleShape, color = Color.Transparent, contentColor = Color.White) {
                Row(Modifier.padding(horizontal = 8.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                    IconButton(onClick = onDismiss, enabled = !deleting) { Icon(DetailIcons.Close, "Close") }
                    if (currentPhoto != null) IconButton(onClick = { showInfo = !showInfo }) { Icon(DetailIcons.Info, if (showInfo) "Hide information" else "Show information") }
                    if (currentPhoto?.purpose in listOf("concept", "enhance")) IconButton(onClick = { showEnhance = true }, enabled = !deleting) { Icon(DetailIcons.Enhance, "Enhance image") }
                    if (onChoose != null) IconButton(onClick = { onChoose(currentId) }, enabled = !deleting && !choosing) {
                        Icon(DetailIcons.Check, if (currentId in selectedIds) "Selected photo" else "Select photo", tint = if (currentId in selectedIds) MaterialTheme.colorScheme.primary else Color.White)
                    }
                    IconButton(onClick = {
                        if (saveImage(context, origin, currentId, currentPhoto?.filename ?: "$currentId.png", showToast = false)) {
                            saveFeedback = true
                            scope.launch { kotlinx.coroutines.delay(2000); saveFeedback = false }
                        }
                    }, enabled = !saveFeedback) { Icon(if (saveFeedback) DetailIcons.Check else DetailIcons.Download, "Save original") }
                    Box {
                        IconButton(onClick = { showMore = true }, enabled = !deleting) { Icon(DetailIcons.More, "More image actions") }
                        DropdownMenu(expanded = showMore, onDismissRequest = { showMore = false }) {
                            DropdownMenuItem(text = { Text("Reset zoom") }, onClick = { showMore = false; zoomAnimation?.cancel(); scale = 1f; offset = Offset.Zero })
                            if (currentPhoto?.purpose in listOf("concept", "enhance")) DropdownMenuItem(text = { Text("Retry generation") }, onClick = { showMore = false; showRetry = true })
                            if (onDeleted != null) DropdownMenuItem(text = { Text("Move to Trash") }, onClick = { showMore = false; confirmDelete = true })
                        }
                    }
                }
                }
                }
            }
        }
                if (currentPhoto != null && showInfo) {
                    ModalBottomSheet(
                        onDismissRequest = { showInfo = false },
                        sheetState = rememberModalBottomSheetState(),
                        containerColor = Color.White, contentColor = Color.Black,
                    ) {
                    Column(Modifier.fillMaxWidth().fillMaxHeight(0.85f).verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                            Text(currentPhoto.projectName + if (onOpenProject != null) " ↗" else "", Modifier.weight(1f).clickable(enabled = onOpenProject != null) { showInfo = false; onOpenProject?.invoke(currentPhoto.projectId) }.padding(vertical = 12.dp), style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                            Surface(color = Color(0xFFF1F3F2), shape = MaterialTheme.shapes.small) {
                                Text(currentPhoto.purpose, Modifier.padding(horizontal = 10.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall, color = Color.Black)
                            }
                        }
                        Text(listOfNotNull(
                            currentPhoto.provider.takeIf { it.isNotBlank() }, currentPhoto.model.takeIf { it.isNotBlank() },
                            if (currentPhoto.width > 0 && currentPhoto.height > 0) "${currentPhoto.width} × ${currentPhoto.height}" else null,
                            currentPhoto.createdAt.take(10).takeIf { it.isNotBlank() },
                        ).joinToString(" · "), style = MaterialTheme.typography.labelSmall)
                        if ((currentPhoto.tags + identity?.tags.orEmpty()).isNotEmpty()) Text((currentPhoto.tags + identity?.tags.orEmpty()).distinct().joinToString(" · "), style = MaterialTheme.typography.labelMedium)
                        MarkdownPrompt(currentPhoto.prompt.ifBlank { "No prompt available" }, Modifier.padding(vertical = 8.dp))
                    }
                    }
                }
        if (showEnhance && currentPhoto != null) PhotoEnhanceSheet(origin, currentPhoto, onQueued = {
            showEnhance = false
            enhancementQueued = true
            scope.launch { kotlinx.coroutines.delay(2500); enhancementQueued = false }
        }, onDismiss = { showEnhance = false })
        if (showRetry && currentPhoto != null) PhotoRetrySheet(origin, currentPhoto, onDeleted = { id ->
            showRetry = false
            if (onDeleted != null) onDeleted(id) else onDismiss()
        }) { showRetry = false }
        if (confirmDelete) AlertDialog(
            onDismissRequest = { confirmDelete = false }, title = { Text("Move photo to Trash?") },
            text = { Text("You can restore this photo from Trash.") },
            confirmButton = { TextButton(onClick = {
                confirmDelete = false; deleting = true
                scope.launch {
                    try { client.trashAsset(origin, currentId); ConceptLibraryRepository(context.applicationContext, origin).remove(currentId); onDeleted?.invoke(currentId) }
                    catch (e: kotlinx.coroutines.CancellationException) { throw e }
                    catch (e: Exception) { error = e.message }
                    finally { deleting = false }
                }
            }) { Text("Move to Trash") } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}

internal object DetailIcons {
    private fun vector(name: String, path: String): ImageVector = ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f)
        .addPath(PathParser().parsePathString(path).toNodes(), fill = SolidColor(Color.Black)).build()
    val Best = vector("Best", "M5,3h14v3h3v4a5,5 0,0 1,-5,5h-1a6,6 0,0 1,-3,2v3h4v2H7v-2h4v-3a6,6 0,0 1,-3,-2H7a5,5 0,0 1,-5,-5V6h3ZM4,8v2a3,3 0,0 0,2,2L5,8ZM19,8l-1,4a3,3 0,0 0,2,-2V8Z")
    val Enhance = vector("Enhance", "M4,18L16,6l4,4L8,22ZM14,8l2,2 1,-1 -2,-2ZM5,2l1.2,3.8L10,7 6.2,8.2 5,12 3.8,8.2 0,7 3.8,5.8ZM20,0l1,3 3,1 -3,1 -1,3 -1,-3 -3,-1 3,-1Z")
    val Search = vector("Search", "M10,2a8,8 0,1 0,4.9,14.3L21,22l1,-1 -5.7,-6.1A8,8 0,0 0,10,2M10,4a6,6 0,1 1,0,12a6,6 0,0 1,0,-12Z")
    val Dislike = vector("Dislike", "M15,3H5a2,2 0,0 0,-2,2v7a2,2 0,0 0,2,2h5l-1,5 2,2 6,-7V3ZM19,3h3v11h-3Z")
    val Close = vector("Close", "M18.3,5.7L12,12l6.3,6.3 -1.4,1.4L10.6,13.4 4.3,19.7 2.9,18.3 9.2,12 2.9,5.7 4.3,4.3 10.6,10.6 16.9,4.3Z")
    val Zoom = vector("Zoom", "M9,3a6,6 0,1 0,0,12a6,6 0,0 0,0,-12M9,5a4,4 0,1 1,0,8a4,4 0,0 1,0,-8M13,14l2,-2 7,7 -2,2ZM6,8h6v2H6Z")
    val Download = vector("Download", "M11,3h2v9l3,-3 1.4,1.4L12,16 6.6,10.4 8,9l3,3ZM4,17h2v3h12v-3h2v5H4Z")
    val Delete = vector("Delete", "M8,3h8v2h5v2H3V5h5ZM5,9h2v11h10V9h2v13H5ZM9,9h2v9H9ZM13,9h2v9h-2Z")
    val Check = vector("Select", "M9,16.2L4.8,12l-1.4,1.4L9,19 21,7l-1.4,-1.4Z")
    val Retry = vector("Retry", "M17.7,6.3A8,8 0,1 0,20,12h-2a6,6 0,1 1,-1.8,-4.2L13,11h9V2Z")
    val Info = vector("Info", "M12,2a10,10 0,1 0,0,20a10,10 0,0 0,0,-20M12,4a8,8 0,1 1,0,16a8,8 0,0 1,0,-16M11,10h2v7h-2ZM11,6h2v2h-2Z")
    val Back = vector("Back", "M20,11H7.8l5.6,-5.6L12,4l-8,8 8,8 1.4,-1.4L7.8,13H20Z")
    val More = vector("More", "M12,3a2,2 0,1 0,0,4a2,2 0,0 0,0,-4M12,10a2,2 0,1 0,0,4a2,2 0,0 0,0,-4M12,17a2,2 0,1 0,0,4a2,2 0,0 0,0,-4Z")
    val Gallery = vector("Gallery", "M3,3h18v18H3ZM5,5v14h14V5ZM6,17l4,-5 3,4 2,-3 3,4ZM15,6a2,2 0,1 0,0,4a2,2 0,0 0,0,-4Z")
    val Settings = vector("Settings", "M19.4,13a7,7 0,0 0,0,-2l2,-1.6 -2,-3.4 -2.4,1a8,8 0,0 0,-1.7,-1L15,3H9l-0.4,3a8,8 0,0 0,-1.7,1L4.5,6 2.5,9.4 4.6,11a7,7 0,0 0,0,2l-2.1,1.6 2,3.4 2.4,-1a8,8 0,0 0,1.7,1L9,21h6l0.3,-3a8,8 0,0 0,1.7,-1l2.4,1 2,-3.4ZM12,8a4,4 0,1 1,0,8a4,4 0,0 1,0,-8Z")
    val StarFilled = vector("Bookmarked", "M12,2l3.1,6.3 6.9,1 -5,4.9 1.2,6.8L12,17.8 5.8,21 7,14.2 2,9.3 8.9,8.3Z")
    val Star = vector("Bookmark", "M12,2l3.1,6.3 6.9,1 -5,4.9 1.2,6.8L12,17.8 5.8,21 7,14.2 2,9.3 8.9,8.3ZM12,6.5L10.2,10.2 6.1,10.8 9.1,13.7 8.4,17.8 12,15.9 15.6,17.8 14.9,13.7 17.9,10.8 13.8,10.2Z")
}
