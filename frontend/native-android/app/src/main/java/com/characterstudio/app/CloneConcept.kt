package com.characterstudio.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
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
internal fun CloneConceptSheet(origin: String, project: ProjectDetail, masters: List<JSONObject>, approvedId: String?, client: BackendClient, onUploaded: suspend () -> Unit, onDismiss: () -> Unit, onReview: (JSONObject) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val ready = masters.filter { it.optJSONObject("job")?.optString("status") == "succeeded" }
    var masterId by remember { mutableStateOf(approvedId?.takeIf { id -> ready.any { it.optString("id") == id } } ?: ready.firstOrNull()?.optString("id").orEmpty()) }
    var referenceId by remember { mutableStateOf("") }
    var keepOutfit by remember { mutableStateOf(false) }
    var uploaded by remember { mutableStateOf(emptyList<AssetSummary>()) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val masterImage = ready.find { it.optString("id") == masterId }?.optJSONObject("job")?.optJSONArray("output_asset_ids")?.optString(0)
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            busy = true; error = null
            try {
                val rows = client.uploadAssets(origin, project.id, listOf(uri), context.contentResolver, kind = "template")
                uploaded = uploaded + rows; referenceId = rows.first().id; onUploaded()
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { error = e.message } finally { busy = false }
        }
    }
    ModalBottomSheet(onDismissRequest = { if (!busy) onDismiss() }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().heightIn(max = androidx.compose.ui.platform.LocalConfiguration.current.screenHeightDp.dp * 0.9f).verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Clone concept from photo", style = MaterialTheme.typography.titleLarge)
            Text("Master supplies identity and rendering style. The reference supplies pose, composition, scene and lighting.", style = MaterialTheme.typography.bodySmall)
            ServerChoice("Master", masterId, ready.map { it.getString("id") }, enabled = !busy && ready.isNotEmpty(), labels = ready.associate { it.getString("id") to "Master ${it.optInt("round")}/${it.optInt("variant")}" }) { masterId = it }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (!masterImage.isNullOrBlank()) AsyncImage("$origin/api/assets/$masterImage/content", "Master identity", Modifier.size(112.dp), contentScale = ContentScale.Fit)
                if (referenceId.isNotBlank()) AsyncImage("$origin/api/assets/$referenceId/content", "Concept reference", Modifier.size(112.dp), contentScale = ContentScale.Fit)
            }
            OutlinedButton(enabled = !busy && project.rightsConfirmed, onClick = { picker.launch("image/*") }) { Text("Pick reference photo") }
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                (project.assets + uploaded).distinctBy { it.id }.forEach { asset ->
                    Surface(onClick = { referenceId = asset.id }, enabled = !busy, border = BorderStroke(if (referenceId == asset.id) 2.dp else 1.dp, if (referenceId == asset.id) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline), shape = MaterialTheme.shapes.medium) {
                        AsyncImage("$origin/api/assets/${asset.id}/content", "Use reference ${asset.filename}", Modifier.size(88.dp).padding(4.dp), contentScale = ContentScale.Fit)
                    }
                }
            }
            Row { Checkbox(keepOutfit, enabled = !busy, onCheckedChange = { keepOutfit = it }); Text("Keep Master outfit (otherwise copy reference outfit)", Modifier.padding(top = 12.dp)) }
            Button(enabled = !busy && project.rightsConfirmed && masterId.isNotBlank() && referenceId.isNotBlank(), onClick = {
                onReview(JSONObject().put("master_version_id", masterId).put("reference_asset_id", referenceId).put("keep_master_outfit", keepOutfit))
            }, modifier = Modifier.fillMaxWidth()) { Text("Review clone concept") }
        }
    }
}
