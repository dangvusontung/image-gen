package com.characterstudio.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.launch

@Composable
internal fun QueueScreen(session: LibrarySession, onBack: () -> Unit, onOpenProject: (String) -> Unit) {
    var tab by remember { mutableStateOf("Active") }
    var pending by remember { mutableStateOf<QueueJob?>(null) }
    var busy by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var viewing by remember { mutableStateOf<QueueJob?>(null) }
    val scope = rememberCoroutineScope()
    val client = remember { BackendClient() }
    val rows = session.queue.filter { when (tab) { "Active" -> isGenerating(it.status); "Failed" -> it.status in listOf("failed", "cancelled"); else -> true } }
    fun perform(job: QueueJob) {
        if (busy != null) return
        busy = job.id; error = null
        scope.launch {
            try {
                if (isGenerating(job.status)) client.cancelJob(session.origin, job.id) else client.retryJob(session.origin, job.id)
                session.refreshQueue(); session.queueRevision++
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { error = e.message }
            finally { busy = null }
        }
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(DetailIcons.Back, "Back") }
            Text("Generation queue", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
            IconButton(onClick = { session.queueRevision++ }) { Icon(DetailIcons.Retry, "Refresh queue") }
        }
        Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("Active", "Failed", "Recent").forEach { label -> FilterChip(selected = tab == label, onClick = { tab = label }, label = { Text(label) }) }
        }
        (error ?: session.queueError)?.let { Text(it, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error) }
        if (!session.queueLoaded && session.queueError == null) CircularProgressIndicator(Modifier.padding(24.dp))
        if (session.queueLoaded && rows.isEmpty()) Text(if (tab == "Active") "No jobs running." else "No jobs here.", Modifier.padding(24.dp))
        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (tab == "Recent") item { Text("Latest 200 jobs, plus active jobs", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            items(rows, key = { it.id }) { job ->
                Card {
                    Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Box(Modifier.width(88.dp)) {
                            if (isGenerating(job.status)) GeneratingPhotoPlaceholder(job.purpose)
                            else if (job.outputIds.isNotEmpty()) AsyncImage("${session.origin}/api/assets/${job.outputIds.first()}/content", "Job result", Modifier.size(88.dp).clickable { viewing = job }, contentScale = ContentScale.Crop)
                            else Surface(Modifier.size(88.dp), color = MaterialTheme.colorScheme.surfaceContainerHigh) { Box(contentAlignment = Alignment.Center) { Icon(DetailIcons.Info, job.status) } }
                        }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(job.projectName, Modifier.clickable { onOpenProject(job.projectId) }, style = MaterialTheme.typography.titleMedium)
                            Text("${job.purpose} · ${job.status}", style = MaterialTheme.typography.labelMedium)
                            Text(listOf(job.provider, job.model).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.labelSmall, maxLines = 2)
                            job.error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error, maxLines = 4) }
                            Row {
                                if (isGenerating(job.status) || job.status in listOf("failed", "cancelled")) TextButton(enabled = busy == null, onClick = { pending = job }) { Text(if (isGenerating(job.status)) "Cancel job" else "Retry") }
                                if (job.outputIds.isNotEmpty()) TextButton(onClick = { viewing = job }) { Text("View ${job.outputIds.size} images") }
                            }
                            if (busy == job.id) LinearProgressIndicator(Modifier.fillMaxWidth())
                        }
                    }
                }
            }
        }
    }
    pending?.let { job -> AlertDialog(onDismissRequest = { pending = null }, title = { Text(if (isGenerating(job.status)) "Cancel this job?" else "Retry generation?") }, text = { Text(if (isGenerating(job.status)) "The provider may already have started processing this job." else "A new generation will be queued using this job's settings. Provider charges may apply.") }, confirmButton = { TextButton(onClick = { pending = null; perform(job) }) { Text("Confirm") } }, dismissButton = { TextButton(onClick = { pending = null }) { Text("Keep") } }) }
    viewing?.let { job -> val photos = job.photos(); ImageViewer(session.origin, photos.first().id, photos = photos, imageIds = photos.map { it.id }, onOpenProject = { viewing = null; onOpenProject(it) }) { viewing = null } }
}
