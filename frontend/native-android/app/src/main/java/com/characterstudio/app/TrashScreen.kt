package com.characterstudio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
fun TrashScreen(origin: String, onBack: () -> Unit) {
    val client = remember { BackendClient() }
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirmation by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(origin) {
        runCatching { client.listTrash(origin) }.onSuccess { rows = it }.onFailure { error = it.message }
        loading = false
    }
    fun change(row: JSONObject, restore: Boolean) {
        if (busy) return
        busy = true
        scope.launch {
            runCatching {
                client.trashAction(origin, row.getString("kind"), row.getString("id"), restore)
                client.listTrash(origin)
            }.onSuccess { rows = it; confirmation = null; error = null }.onFailure { error = it.message; confirmation = null }
            busy = false
        }
    }
    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        TextButton(onClick = onBack) { Text("← Projects") }
        Text("Trash", style = MaterialTheme.typography.headlineMedium)
        Text("Runs and images are kept here until you permanently delete them. Restore to return them to the original lists.")
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (loading) CircularProgressIndicator()
        else if (rows.isEmpty()) Text("Trash is empty.")
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(rows, key = { it.getString("kind")+it.getString("id") }) { row ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(row.getString("project_name")+" · "+row.getString("kind"), style = MaterialTheme.typography.titleMedium)
                        Text(row.getString("title"))
                        row.optString("error_message").takeUnless { it.isBlank() || it == "null" }?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        val images = row.optJSONArray("asset_ids")
                        if (images != null && images.length() > 0) ResultImage(origin, images.getString(0)) { }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { change(row, true) }, enabled = !busy) { Text("Restore") }
                            TextButton(onClick = { confirmation = row }, enabled = !busy) { Text("Delete forever") }
                        }
                    }
                }
            }
        }
    }
    confirmation?.let { row -> AlertDialog(
        onDismissRequest = { if (!busy) confirmation = null },
        title = { Text("Delete permanently?") },
        text = { Text("${row.getString("title")} — image files will be removed and cannot be restored.") },
        confirmButton = { TextButton(onClick = { change(row, false) }, enabled = !busy) { Text("Delete forever") } },
        dismissButton = { TextButton(onClick = { confirmation = null }, enabled = !busy) { Text("Keep") } },
    ) }
}
