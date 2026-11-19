package com.characterstudio.app

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

internal data class GenerationSetup(val id: String, val name: String, val choices: String, val steps: Map<String, GenerationTarget>, val masterCount: Int, val customCount: Int)
internal val generationSteps = listOf("master", "turnaround", "concept", "enhance")

internal fun generationTargets(project: ProjectDetail, presets: List<StepPreset>, providers: List<ProviderSummary>): Map<String, GenerationTarget> = generationSteps.associateWith { step ->
    val target = project.generationTarget(step, presets)
    target.copy(size = target.size.ifBlank { providers.find { it.name == target.provider }?.defaultSizes?.get(target.model).orEmpty() })
}

internal fun encodeSetups(setups: List<GenerationSetup>): String = JSONArray().apply {
    setups.forEach { setup ->
        val steps = JSONObject()
        setup.steps.forEach { (key, value) -> steps.put(key, JSONObject().put("provider", value.provider).put("model", value.model).put("size", value.size)) }
        put(JSONObject().put("id", setup.id).put("name", setup.name).put("choices", JSONObject(setup.choices)).put("steps", steps).put("master_count", setup.masterCount).put("custom_count", setup.customCount))
    }
}.toString()

internal fun decodeSetups(json: String): List<GenerationSetup> {
    val rows = JSONArray(json)
    return (0 until rows.length()).map { index ->
        val row = rows.getJSONObject(index)
        val steps = row.getJSONObject("steps")
        GenerationSetup(row.getString("id"), row.getString("name"), row.getJSONObject("choices").toString(), steps.keys().asSequence().associateWith { key ->
            val value = steps.getJSONObject(key)
            GenerationTarget(value.getString("provider"), value.getString("model"), value.optString("size"))
        }, row.optInt("master_count", 1).coerceIn(1, 4), row.optInt("custom_count", 1).coerceIn(1, 4))
    }
}

internal class GenerationSetupStore(context: Context, private val origin: String) {
    private val prefs = context.getSharedPreferences("generation-setups-v1", Context.MODE_PRIVATE)
    fun list(): List<GenerationSetup> = runCatching { decodeSetups(prefs.getString(origin, "[]") ?: "[]") }.getOrDefault(emptyList())
    fun save(setup: GenerationSetup) { prefs.edit().putString(origin, encodeSetups((list().filterNot { it.id == setup.id } + setup).sortedBy { it.name.lowercase() })).apply() }
    fun remove(id: String) { prefs.edit().putString(origin, encodeSetups(list().filterNot { it.id == id })).apply() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun SetupLibrarySheet(store: GenerationSetupStore, current: GenerationSetup, busy: Boolean, error: String?, onApply: (GenerationSetup) -> Unit, onDismiss: () -> Unit) {
    var rows by remember { mutableStateOf(store.list()) }
    var name by remember { mutableStateOf("") }
    var saved by remember { mutableStateOf(false) }
    ModalBottomSheet(onDismissRequest = { if (!busy) onDismiss() }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 20.dp, end = 20.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Saved setups", style = MaterialTheme.typography.headlineSmall)
            Text("Outfit, scene, model and size for every step. Saved on this phone.", style = MaterialTheme.typography.bodyMedium)
            OutlinedTextField(name, { name = it.take(80); saved = false }, label = { Text("Name this setup") }, modifier = Modifier.fillMaxWidth(), singleLine = true, enabled = !busy)
            Button(onClick = { store.save(current.copy(id = UUID.randomUUID().toString(), name = name.trim())); rows = store.list(); saved = true; name = "" }, enabled = name.isNotBlank() && !busy) { Text("Save current setup") }
            if (saved) Text("Setup saved", color = MaterialTheme.colorScheme.primary)
            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            rows.forEach { setup ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(setup.name, style = MaterialTheme.typography.titleMedium)
                        Text(stylingSummary(JSONObject(setup.choices), JSONObject()), style = MaterialTheme.typography.bodySmall)
                        setup.steps.forEach { (step, target) -> Text("$step · ${target.provider} / ${target.model} · ${target.size.ifBlank { "Default" }}", style = MaterialTheme.typography.labelSmall) }
                        Row {
                            TextButton(enabled = !busy, onClick = { onApply(setup) }) { Text("Apply to project") }
                            TextButton(enabled = !busy, onClick = { store.remove(setup.id); rows = store.list() }) { Text("Delete") }
                        }
                    }
                }
            }
            if (rows.isEmpty()) Text("Save a setup to reuse it in another project.")
        }
    }
}
