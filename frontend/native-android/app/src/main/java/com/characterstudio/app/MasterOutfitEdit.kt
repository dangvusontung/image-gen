package com.characterstudio.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import org.json.JSONObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun MasterOutfitEditSheet(origin: String, project: ProjectDetail, masterAssetId: String, client: BackendClient, menu: JSONObject, onUploaded: suspend () -> Unit, onDismiss: () -> Unit, onReview: (JSONObject) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var selected by remember { mutableStateOf("") }
    var customOutfit by remember { mutableStateOf("") }
    val entries = menu.optJSONArray("outfit")
    val presets = (0 until (entries?.length() ?: 0)).map { entries!!.getJSONArray(it) }.filter { it.getString(0) !in listOf("auto", "master") }
    val preset = selected.takeIf { it.startsWith("preset:") }?.removePrefix("preset:")

    var uploaded by remember { mutableStateOf(emptyList<AssetSummary>()) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            busy = true; error = null
            try {
                val rows = client.uploadAssets(origin, project.id, listOf(uri), context.contentResolver, kind = "template")
                uploaded = uploaded + rows; selected = rows.first().id; onUploaded()
            } catch (e: Exception) { error = e.message } finally { busy = false }
        }
    }
    ModalBottomSheet(onDismissRequest = { if (!busy) onDismiss() }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().heightIn(max = androidx.compose.ui.platform.LocalConfiguration.current.screenHeightDp.dp * 0.9f).verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Change Master outfit · optional", style = MaterialTheme.typography.titleLarge)
            Text("Only change clothing. Keep the Master's identity, pose and background. Review and approve the new version separately.", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                AsyncImage("$origin/api/assets/$masterAssetId/content", "Source Master", Modifier.size(120.dp), contentScale = ContentScale.Fit)
                if (selected.isNotBlank() && preset == null) AsyncImage("$origin/api/assets/$selected/content", "Selected outfit", Modifier.size(120.dp), contentScale = ContentScale.Fit)
            }
            ServerChoice("Outfit preset", preset.orEmpty(), listOf("") + presets.map { it.getString(0) }, enabled = !busy, labels = mapOf("" to "Choose preset…") + presets.associate { it.getString(0) to it.getString(1) }) { selected = if (it.isEmpty()) "" else "preset:$it" }
            if (preset == "custom") OutlinedTextField(customOutfit, { customOutfit = it.take(600) }, label = { Text("Custom outfit") }, modifier = Modifier.fillMaxWidth())
            OutlinedButton(enabled = !busy && project.rightsConfirmed, onClick = { picker.launch("image/*") }) { Text("Pick outfit photo") }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                (project.assets + uploaded).distinctBy { it.id }.filter { it.kind in listOf("reference", "side_profile", "template") }.forEach { asset ->
                    Surface(onClick = { selected = asset.id }, enabled = !busy, shape = MaterialTheme.shapes.medium, border = BorderStroke(if (selected == asset.id) 2.dp else 1.dp, MaterialTheme.colorScheme.outline)) {
                        AsyncImage("$origin/api/assets/${asset.id}/content", "Outfit from ${asset.filename}", Modifier.size(88.dp).padding(4.dp), contentScale = ContentScale.Fit)
                    }
                }
            }
            Button(enabled = !busy && selected.isNotBlank() && (preset != "custom" || customOutfit.isNotBlank()) && project.rightsConfirmed, onClick = { onReview(masterOutfitEditPayload(selected, customOutfit)) }, modifier = Modifier.fillMaxWidth()) { Text("Review outfit change") }
        }
    }
}

internal fun masterOutfitEditPayload(selection: String, custom: String = ""): JSONObject = JSONObject().apply {
    require(selection.isNotBlank()) { "Choose an outfit source." }
    if (selection.startsWith("preset:")) {
        val preset = selection.removePrefix("preset:")
        require(preset.isNotBlank() && preset !in listOf("auto", "master")) { "Choose an outfit preset." }
        require(preset != "custom" || custom.isNotBlank()) { "Describe the custom outfit." }
        put("master_outfit", JSONObject().put("outfit", preset).put("custom_outfit", custom))
    } else put("outfit_reference_asset_id", selection)
}

internal fun masterVersionForImage(workflow: org.json.JSONObject, assetId: String): String? {
    val masters = workflow.optJSONArray("masters") ?: return null
    for (index in 0 until masters.length()) {
        val master = masters.getJSONObject(index)
        val job = master.optJSONObject("job") ?: continue
        if (job.optString("status") != "succeeded") continue
        val outputs = job.optJSONArray("output_asset_ids") ?: continue
        if ((0 until outputs.length()).any { outputs.optString(it) == assetId }) return master.getString("id")
    }
    return null
}

@Composable
internal fun MasterOutfitDetailDialog(origin: String, photo: GalleryItem, onDismiss: () -> Unit, onQueued: () -> Unit) {
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    var project by remember(photo.id) { mutableStateOf<ProjectDetail?>(null) }
    var versionId by remember(photo.id) { mutableStateOf<String?>(null) }
    var selection by remember(photo.id) { mutableStateOf<JSONObject?>(null) }
    var menu by remember(photo.id) { mutableStateOf(JSONObject()) }
    var loading by remember(photo.id) { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(origin, photo.id) {
        try {
            project = client.getProject(origin, photo.projectId)
            menu = client.conceptOptions(origin, photo.projectId)
            versionId = masterVersionForImage(client.workflow(origin, photo.projectId), photo.id)
            if (versionId == null) error = "This Master version is no longer available."
        } catch (e: kotlinx.coroutines.CancellationException) { throw e }
        catch (e: Exception) { error = e.message }
        finally { loading = false }
    }
    val detail = project
    if (loading || versionId == null || detail == null) {
        AlertDialog(onDismissRequest = onDismiss, title = { Text("Change Master outfit") }, text = {
            if (loading) CircularProgressIndicator() else Text(error ?: "Cannot load this Master.")
        }, confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } })
    } else if (selection == null) {
        MasterOutfitEditSheet(origin, detail, photo.id, client, menu,
            onUploaded = { project = client.getProject(origin, photo.projectId) }, onDismiss = onDismiss,
            onReview = { selection = it; error = null })
    } else {
        AlertDialog(onDismissRequest = { if (!busy) selection = null }, title = { Text("Review Master outfit change") }, text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    AsyncImage("$origin/api/assets/${photo.id}/content", "Source Master", Modifier.size(112.dp), contentScale = ContentScale.Fit)
                    if (selection?.has("master_outfit") == true) {
                        val choices = selection!!.getJSONObject("master_outfit")
                        val key = choices.optString("outfit")
                        val entries = menu.optJSONArray("outfit")
                        val label = (0 until (entries?.length() ?: 0)).map { entries!!.getJSONArray(it) }.find { it.getString(0) == key }?.getString(1) ?: key
                        Text(if (key == "custom") choices.optString("custom_outfit") else label, Modifier.weight(1f))
                    } else AsyncImage("$origin/api/assets/${selection?.optString("outfit_reference_asset_id")}/content", "Outfit source", Modifier.size(112.dp), contentScale = ContentScale.Fit)
                }
                Text("Create 1 new Master from ${if (selection?.has("master_outfit") == true) 1 else 2} images. Keep the original. Provider charges may apply; approve the result separately.")
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            }
        }, confirmButton = {
            TextButton(enabled = !busy, onClick = {
                busy = true; error = null
                scope.launch {
                    try {
                        client.projectAction(origin, photo.projectId, "master/$versionId/outfit", JSONObject(selection.toString()).put("confirmed", true))
                        onQueued()
                    } catch (e: kotlinx.coroutines.CancellationException) { throw e }
                    catch (e: Exception) { error = e.message }
                    finally { busy = false }
                }
            }) { Text("Generate new Master") }
        }, dismissButton = { TextButton(enabled = !busy, onClick = { selection = null; error = null }) { Text("Change outfit photo") } })
    }
}
