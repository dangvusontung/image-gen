package com.characterstudio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject

internal fun batchEnhancePlan(photo: GalleryItem, concepts: List<JSONObject>, enhancements: List<JSONObject>): PhotoRetryPlan {
    fun owns(row: JSONObject): Boolean = row.optJSONObject("job")?.optJSONArray("output_asset_ids")?.let { ids -> (0 until ids.length()).any { ids.optString(it) == photo.id } } == true
    val payload = JSONObject().put("confirm_reference_subset", true)
    val conceptId = when (photo.purpose) {
        "concept" -> concepts.find(::owns)?.getString("id") ?: error("Could not find the concept for ${photo.filename}")
        "enhance" -> enhancements.find(::owns)?.let { payload.put("from_enhancement_id", it.getString("id")); it.getString("concept_id") } ?: error("Could not find the enhancement for ${photo.filename}")
        else -> error("Only concept and enhanced images can be enhanced")
    }
    return PhotoRetryPlan("concepts/$conceptId/enhance", payload)
}

/** Successful items are removed from selection so retrying failures cannot repeat them. */
@Composable
internal fun BatchPhotoActions(origin: String, photos: List<GalleryItem>, onProcessed: (Set<String>) -> Unit, onDeleted: (String) -> Unit, onChoose: ((String) -> Unit)? = null, onBusyChange: (Boolean) -> Unit = {}) {
    val context = LocalContext.current
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    var operation by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var progress by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var compare by remember { mutableStateOf(false) }
    androidx.activity.compose.BackHandler(enabled = busy) {}
    val eligible = photos.isNotEmpty() && photos.all { it.purpose in listOf("concept", "enhance") }
    fun run(kind: String, snapshot: List<GalleryItem>) {
        if (busy) return
        busy = true; onBusyChange(true); progress = 0; message = null
        scope.launch {
            val done = mutableSetOf<String>()
            val failures = mutableListOf<String>()
            val concepts = mutableMapOf<String, List<JSONObject>>()
            val enhancements = mutableMapOf<String, List<JSONObject>>()
            try {
                snapshot.forEach { photo ->
                    try {
                        when (kind) {
                            "save" -> check(saveImage(context, origin, photo.id, photo.filename, showToast = false)) { "Download could not be started" }
                            "trash" -> { client.trashAsset(origin, photo.id); ConceptLibraryRepository(context.applicationContext, origin).remove(photo.id) }
                            "enhance" -> {
                                val rows = concepts.getOrPut(photo.projectId) { client.projectArray(origin, photo.projectId, "concepts") }
                                val enhanced = if (photo.purpose == "enhance") enhancements.getOrPut(photo.projectId) { client.projectArray(origin, photo.projectId, "enhancements") } else emptyList()
                                val plan = batchEnhancePlan(photo, rows, enhanced)
                                client.projectAction(origin, photo.projectId, plan.path, plan.payload)
                            }
                        }
                        done += photo.id
                    } catch (e: CancellationException) { throw e }
                    catch (e: Exception) { failures += "${photo.filename}: ${e.message}" }
                    progress++
                }
                if (kind == "trash") done.forEach(onDeleted)
                onProcessed(done)
                message = if (failures.isEmpty()) when (kind) { "save" -> "${done.size} downloads started"; "trash" -> "${done.size} images moved to Trash"; else -> "${done.size} enhancements queued" }
                    else "${done.size} completed · ${failures.size} failed. ${failures.first()}"
            } finally { busy = false; onBusyChange(false) }
        }
    }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            TextButton(enabled = !busy && photos.size in 2..4, onClick = { compare = true }) { Text("Compare") }
            TextButton(enabled = !busy && photos.isNotEmpty(), onClick = { run("save", photos.toList()) }) { Text("Save") }
            TextButton(enabled = !busy && eligible, onClick = { operation = "enhance" }) { Text("Enhance") }
            TextButton(enabled = !busy && photos.isNotEmpty(), onClick = { operation = "trash" }) { Text("Trash") }
        }
        if (photos.size == 1 || photos.size > 4) Text("Select 2–4 images to compare", style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(horizontal = 12.dp))
        if (busy) { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Processing $progress / ${photos.size}", style = MaterialTheme.typography.labelSmall) }
        message?.let { Text(it, Modifier.padding(8.dp), style = MaterialTheme.typography.bodySmall) }
    }
    operation?.let { kind ->
        val snapshot = remember(kind) { photos.toList() }
        AlertDialog(onDismissRequest = { operation = null }, title = { Text(if (kind == "trash") "Move ${snapshot.size} images to Trash?" else "Enhance ${snapshot.size} images?") }, text = { Text(if (kind == "trash") "Images can be restored from Trash." else "Queue one enhancement for each selected image, using its project's enhancement settings. Provider charges may apply.") }, confirmButton = { TextButton(onClick = { operation = null; run(kind, snapshot) }) { Text(if (kind == "trash") "Move to Trash" else "Queue enhancements") } }, dismissButton = { TextButton(onClick = { operation = null }) { Text("Cancel") } })
    }
    if (compare && photos.size in 2..4) ComparePhotos(origin, photos, onChoose = onChoose) { compare = false }
}
