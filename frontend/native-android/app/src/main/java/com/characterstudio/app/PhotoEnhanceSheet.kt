package com.characterstudio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PhotoEnhanceSheet(origin: String, photo: GalleryItem, onQueued: () -> Unit, onDismiss: () -> Unit) {
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    var plan by remember { mutableStateOf<PhotoRetryPlan?>(null) }
    var details by remember { mutableStateOf<JSONObject?>(null) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var queued by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var revision by remember { mutableIntStateOf(0) }
    LaunchedEffect(photo.id, revision) {
        loading = true; error = null
        try {
            val concepts = client.projectArray(origin, photo.projectId, "concepts")
            val enhancements = if (photo.purpose == "enhance") client.projectArray(origin, photo.projectId, "enhancements") else emptyList()
            val resolved = batchEnhancePlan(photo, concepts, enhancements)
            details = client.enhancementPlan(origin, photo.projectId, resolved)
            plan = resolved
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { error = e.message }
        finally { loading = false }
    }
    androidx.activity.compose.BackHandler(enabled = busy) {}
    ModalBottomSheet(onDismissRequest = { if (!busy) onDismiss() }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Enhance image", style = MaterialTheme.typography.headlineSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                AsyncImage("$origin/api/assets/${photo.id}/content", "Image to enhance", Modifier.size(96.dp), contentScale = ContentScale.Fit)
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(photo.projectName, style = MaterialTheme.typography.titleMedium)
                    Text(if (photo.purpose == "enhance") "Enhance this version again" else "Create an enhanced version", style = MaterialTheme.typography.bodyMedium)
                }
            }
            if (loading || busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            details?.let { info ->
                Text("${info.optString("provider")} / ${info.optString("model")}", style = MaterialTheme.typography.bodyMedium)
                Text("Size · ${info.optString("size")}", style = MaterialTheme.typography.labelLarge)
                if (info.has("estimated_cost_usd") && !info.isNull("estimated_cost_usd")) Text("Estimated cost · $${info.optDouble("estimated_cost_usd")}", style = MaterialTheme.typography.labelLarge)
                info.optString("warning").takeUnless { it.isBlank() || it == "null" }?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if (!loading && plan == null) TextButton(onClick = { revision++ }) { Text("Retry loading settings") }
            Text("Uses the enhancement settings of this project. Provider charges may apply.", style = MaterialTheme.typography.bodySmall)
            Button(enabled = !loading && !busy && !queued && plan != null, modifier = Modifier.fillMaxWidth(), onClick = {
                val request = plan ?: return@Button
                busy = true; error = null
                scope.launch {
                    try {
                        client.projectAction(origin, photo.projectId, request.path, JSONObject(request.payload.toString()))
                        queued = true
                        onQueued()
                    } catch (e: CancellationException) { throw e }
                    catch (e: Exception) { error = e.message }
                    finally { busy = false }
                }
            }) { Text(if (queued) "Queued" else "Queue enhancement") }
        }
    }
}
