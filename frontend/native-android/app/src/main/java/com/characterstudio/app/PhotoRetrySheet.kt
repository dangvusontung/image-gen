package com.characterstudio.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject

internal data class PhotoRetryPlan(val path: String, val payload: JSONObject)

internal class PhotoRetrySubmission {
    var queued by mutableStateOf(false)
        private set
    suspend fun submit(remove: Boolean, queue: suspend () -> Unit, trash: suspend () -> Unit) {
        if (!queued) { queue(); queued = true }
        if (remove) trash()
    }
}

internal fun photoRetryPlan(photo: GalleryItem, source: JSONObject, mode: String, edited: String, choices: JSONObject): PhotoRetryPlan {
    require(mode in listOf("saved", "current", "edit"))
    val payload = JSONObject().put("confirmed", true)
    source.optJSONObject("job")?.optJSONObject("settings")?.optString("size")?.takeIf { it.isNotBlank() && it != "null" }?.let { payload.put("size", it) }
    val path = if (photo.purpose == "concept") {
        when (mode) {
            "saved" -> payload.put("prompt_mode", "saved")
            "current" -> { payload.put("prompt_mode", "current"); if (source.optJSONObject("job")?.optJSONObject("meta")?.optBoolean("image_clone") != true) { choicesError(choices)?.let { error(it) }; payload.put("choices", choices) } }
            "edit" -> { require(edited.isNotBlank() && edited.length <= 50000); payload.put("prompt", edited.trim()) }
        }
        "concepts/${source.getString("id")}/regenerate"
    } else {
        require(photo.purpose == "enhance")
        payload.put("confirm_reference_subset", true)
        source.optJSONObject("job")?.optJSONObject("meta")?.optString("from_enhancement_id")?.takeIf { it.isNotBlank() && it != "null" }?.let { payload.put("from_enhancement_id", it) }
        if (mode != "current") {
            val prompt = if (mode == "saved") photo.prompt else edited.trim()
            require(prompt.isNotBlank() && prompt.length <= 8000) { "Enhancement prompt must contain 1–8000 characters." }
            payload.put("prompt", prompt)
        }
        "concepts/${source.getString("concept_id")}/enhance"
    }
    return PhotoRetryPlan(path, payload)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PhotoRetrySheet(origin: String, photo: GalleryItem, onDeleted: (String) -> Unit, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val client = remember { BackendClient() }
    var mode by remember(photo.id) { mutableStateOf("saved") }
    var edited by remember(photo.id) { mutableStateOf(photo.prompt) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var removeCurrent by remember(photo.id) { mutableStateOf(false) }
    val submission = remember(photo.id) { PhotoRetrySubmission() }
    ModalBottomSheet(onDismissRequest = { if (!busy) onDismiss() }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().heightIn(max = 620.dp).verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Retry generation", style = MaterialTheme.typography.titleLarge)
            listOf(
                Triple("saved", "Saved prompt", "Use the exact prompt that created this image."),
                Triple("current", "Current prompt", if (photo.purpose == "concept") "Use the latest concept description and your current styling." else "Use the current enhancement prompt template."),
                Triple("edit", "Edit prompt", "Edit the full prompt before generating a new version."),
            ).forEach { (value, title, description) ->
                Row(Modifier.fillMaxWidth().clickable(enabled = !busy && !submission.queued) { mode = value }, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    RadioButton(selected = mode == value, onClick = { mode = value }, enabled = !busy && !submission.queued)
                    Column { Text(title, style = MaterialTheme.typography.titleSmall); Text(description, style = MaterialTheme.typography.bodySmall) }
                }
            }
            if (mode == "edit") OutlinedTextField(edited, { edited = it }, label = { Text("Prompt") }, modifier = Modifier.fillMaxWidth().heightIn(max = 220.dp), minLines = 4, enabled = !busy && !submission.queued)
            Row(Modifier.fillMaxWidth().clickable(enabled = !busy) { removeCurrent = !removeCurrent }, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Checkbox(checked = removeCurrent, onCheckedChange = { removeCurrent = it }, enabled = !busy)
                Column {
                    Text("Delete current image", style = MaterialTheme.typography.titleSmall)
                    Text("Move to Trash after the new generation is queued.", style = MaterialTheme.typography.bodySmall)
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text(if (submission.queued) "Generation already queued. You can retry moving the current image to Trash." else "Creates a new image. Provider charges may apply.", style = MaterialTheme.typography.bodySmall)
            Button(modifier = Modifier.fillMaxWidth(), enabled = !busy && (mode != "edit" || edited.isNotBlank()), onClick = {
                busy = true; error = null
                scope.launch {
                    try {
                        submission.submit(removeCurrent, queue = {
                        val rows = client.projectArray(origin, photo.projectId, if (photo.purpose == "concept") "concepts" else "enhancements")
                        val source = rows.find { row ->
                            val outputs = row.optJSONObject("job")?.optJSONArray("output_asset_ids")
                            outputs != null && (0 until outputs.length()).any { outputs.optString(it) == photo.id }
                        } ?: error("The source generation is unavailable. Refresh the gallery and try again.")
                        val choices = defaultConceptChoices()
                        val saved = JSONObject(context.getSharedPreferences("concept-styling", android.content.Context.MODE_PRIVATE).getString(origin+"/"+photo.projectId, "{}").orEmpty())
                        saved.keys().forEach { choices.put(it, saved.get(it)) }
                        val plan = photoRetryPlan(photo, source, mode, edited, choices)
                        client.projectAction(origin, photo.projectId, plan.path, plan.payload)
                        }, trash = { client.trashAsset(origin, photo.id); ConceptLibraryRepository(context.applicationContext, origin).remove(photo.id) })
                        android.widget.Toast.makeText(context, "Generation queued", android.widget.Toast.LENGTH_LONG).show()
                        if (removeCurrent) onDeleted(photo.id) else onDismiss()
                    } catch (e: CancellationException) { throw e }
                    catch (e: Exception) { error = (if (submission.queued) "Generation queued; image was not deleted. " else "") + (e.message ?: "Could not retry this image.") }
                    finally { busy = false }
                }
            }) {
                if (busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                else Text(if (submission.queued) { if (removeCurrent) "Retry deleting image" else "Done" } else "Generate again")
            }
        }
    }
}
