package com.characterstudio.app

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun MasterOutfitEditSheet(origin: String, project: ProjectDetail, masterAssetId: String, client: BackendClient, onUploaded: suspend () -> Unit, onDismiss: () -> Unit, onReview: (String) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var selected by remember { mutableStateOf("") }
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
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Change Master outfit · optional", style = MaterialTheme.typography.titleLarge)
            Text("Only change clothing. Keep the Master's identity, pose and background. Review and approve the new version separately.", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                AsyncImage("$origin/api/assets/$masterAssetId/content", "Source Master", Modifier.size(120.dp), contentScale = ContentScale.Fit)
                if (selected.isNotBlank()) AsyncImage("$origin/api/assets/$selected/content", "Selected outfit", Modifier.size(120.dp), contentScale = ContentScale.Fit)
            }
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
            Button(enabled = !busy && selected.isNotBlank() && project.rightsConfirmed, onClick = { onReview(selected) }, modifier = Modifier.fillMaxWidth()) { Text("Review outfit change") }
        }
    }
}
