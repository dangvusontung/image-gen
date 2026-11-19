package com.characterstudio.app

import androidx.compose.animation.core.animate
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import kotlinx.coroutines.launch

private class CompareZoom {
    var scale by mutableFloatStateOf(1f)
    var offset by mutableStateOf(Offset.Zero)
    fun reset() { scale = 1f; offset = Offset.Zero }
}

@Composable
internal fun ComparePhotos(origin: String, photos: List<GalleryItem>, onChoose: ((String) -> Unit)? = null, onDismiss: () -> Unit) {
    val zoom = remember { CompareZoom() }
    val scope = rememberCoroutineScope()
    var animation by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
    var preview by remember { mutableStateOf<String?>(null) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Surface(Modifier.fillMaxSize(), color = Color.Black, contentColor = Color.White) {
            Column(Modifier.fillMaxSize().safeDrawingPadding()) {
                Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onDismiss) { Icon(DetailIcons.Close, "Close comparison") }
                    Column(Modifier.weight(1f)) {
                        Text("Compare ${photos.size} images", style = MaterialTheme.typography.titleMedium)
                        Text("Zoom and pan are linked", style = MaterialTheme.typography.labelSmall)
                    }
                    TextButton(onClick = { animation?.cancel(); zoom.reset() }) { Text("Reset", color = Color.White) }
                }
                val rows = if (photos.size == 2) photos.map { listOf(it) } else photos.chunked(2)
                rows.forEach { row ->
                    Row(Modifier.weight(1f).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                        row.forEach { photo ->
                            Column(Modifier.weight(1f).fillMaxHeight()) {
                                Box(Modifier.weight(1f).fillMaxWidth().clipToBounds()
                                    .pointerInput(photo.id) {
                                        detectTapGestures(onDoubleTap = { tap ->
                                            animation?.cancel()
                                            val from = zoom.scale
                                            val start = zoom.offset
                                            val target = if (from > 1f) 1f else 2.5f
                                            val end = if (target == 1f) Offset.Zero else Offset((0.5f - tap.x / size.width) * (target - 1), (0.5f - tap.y / size.height) * (target - 1))
                                            animation = scope.launch { animate(0f, 1f, animationSpec = tween(250)) { t, _ -> zoom.scale = from + (target - from) * t; zoom.offset = start + (end - start) * t } }
                                        })
                                    }
                                    .pointerInput(photo.id) {
                                        detectTransformGestures { centroid, pan, scale, _ ->
                                            animation?.cancel()
                                            val next = (zoom.scale * scale).coerceIn(1f, 6f)
                                            val ratio = next / zoom.scale
                                            val center = Offset(centroid.x / size.width - 0.5f, centroid.y / size.height - 0.5f)
                                            val offset = (zoom.offset - center) * ratio + center + Offset(pan.x / size.width, pan.y / size.height)
                                            val limit = (next - 1f) / 2f
                                            zoom.offset = Offset(offset.x.coerceIn(-limit, limit), offset.y.coerceIn(-limit, limit))
                                            zoom.scale = next
                                        }
                                    }) {
                                    AsyncImage("$origin/api/assets/${photo.id}/content", "Comparison image", Modifier.fillMaxSize().graphicsLayer { scaleX = zoom.scale; scaleY = zoom.scale; translationX = zoom.offset.x * size.width; translationY = zoom.offset.y * size.height }, contentScale = ContentScale.Fit)
                                }
                                Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Text("${photo.projectName} · ${photo.purpose}", Modifier.weight(1f), style = MaterialTheme.typography.labelSmall, maxLines = 1)
                                    TextButton(onClick = { preview = photo.id }) { Text("View", color = Color.White) }
                                    if (onChoose != null) TextButton(onClick = { onChoose(photo.id); onDismiss() }) { Text("Approve", color = Color.White) }
                                }
                            }
                        }
                        if (row.size == 1 && photos.size > 2) Spacer(Modifier.weight(1f))
                    }
                }
            }
        }
        preview?.let { id -> ImageViewer(origin, id, photos = photos, imageIds = photos.map { it.id }) { preview = null } }
    }
}
