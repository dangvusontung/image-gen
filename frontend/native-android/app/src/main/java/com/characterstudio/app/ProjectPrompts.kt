package com.characterstudio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

@Composable
internal fun ProjectPromptsDialog(client: BackendClient, origin: String, projectId: String, initialName: String, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var name by remember { mutableStateOf(initialName) }
    var body by remember { mutableStateOf("") }
    var source by remember { mutableStateOf("") }
    var projects by remember { mutableStateOf(emptyList<ProjectSummary>()) }
    var copyFrom by remember { mutableStateOf("") }
    var allPrompts by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var changed by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    val names = listOf("master", "master_flux", "concept", "concept_proposal", "enhance")
    val labels = mapOf("master" to "Master", "master_flux" to "Master (FLUX)", "concept" to "Concept", "concept_proposal" to "Concept suggestions", "enhance" to "Enhancement")
    suspend fun reload() {
        val prompt = client.getPrompt(origin, projectId, name)
        body = prompt.getString("body"); source = prompt.optString("source"); changed = false
    }
    fun update(success: String, block: suspend () -> Unit) {
        if (busy || loading) return
        busy = true; error = null; message = null
        scope.launch {
            try { block(); reload(); message = success } catch (e: Exception) { error = e.message }
            finally { busy = false }
        }
    }
    LaunchedEffect(origin, projectId) {
        runCatching { client.listProjects(origin) }.onSuccess { projects = it.filter { p -> p.id != projectId } }.onFailure { error = it.message }
    }
    LaunchedEffect(name) {
        loading = true; error = null; message = null
        try { reload() } catch (e: Exception) { error = e.message; body = "" }
        finally { loading = false }
    }
    AlertDialog(onDismissRequest = { if (!busy) onDismiss() }, title = { Text("Project prompts") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ServerChoice("Step", name, names, enabled = !busy && !loading && !changed, labels = labels) { name = it }
            if (changed) Text("Save or reset your edits before switching steps.", style = MaterialTheme.typography.bodySmall)
            if (loading || busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            Text("Source: $source", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(body, { body = it; changed = true }, label = { Text("Prompt") }, minLines = 5, maxLines = 10, enabled = !busy && !loading, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { update("Prompt saved on backend.") { client.savePrompt(origin, projectId, name, body) } }, enabled = changed && body.isNotBlank() && !busy && !loading) { Text("Save") }
                TextButton(onClick = { update("Using backend default prompt.") { client.savePrompt(origin, projectId, name, null) } }, enabled = !busy && !loading) { Text("Use default") }
            }
            HorizontalDivider()
            ServerChoice("Copy prompts from", copyFrom, listOf("") + projects.map { it.id }, enabled = !busy && !loading,
                labels = mapOf("" to "Choose a project…") + projects.associate { it.id to it.name }) { copyFrom = it }
            Row { Checkbox(allPrompts, onCheckedChange = { allPrompts = it }, enabled = !busy); Text("Copy all step prompts", Modifier.padding(top = 12.dp)) }
            OutlinedButton(onClick = { update("Prompts copied and saved on backend.") { client.copyPrompts(origin, projectId, copyFrom, names = if (allPrompts) null else listOf(name)) } }, enabled = copyFrom.isNotBlank() && !busy && !loading && !changed, modifier = Modifier.fillMaxWidth()) { Text(if (allPrompts) "Copy all prompts" else "Copy this step's prompt") }
            Text("Copying changes this project's prompts only. Provider settings and photos stay unchanged.", style = MaterialTheme.typography.bodySmall)
            message?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(onClick = onDismiss, enabled = !busy) { Text("Done") } })
}
