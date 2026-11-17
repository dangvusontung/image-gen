package com.characterstudio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject

internal fun defaultConceptChoices() = JSONObject().put("style", "auto").put("outfit", "bikini")
    .put("footwear", "barefoot").put("top", "auto").put("scene", "auto").put("lighting", "auto")
    .put("glasses", false).put("custom_outfit", "").put("custom_footwear", "").put("custom_scene", "").put("activity", "")

internal fun choicesError(choices: JSONObject): String? {
    for (key in listOf("outfit", "footwear", "scene")) {
        if (choices.optString(key) == "custom" && choices.optString("custom_$key").isBlank()) return "Enter a custom $key description."
    }
    return null
}

internal fun overridesConcept(choices: JSONObject): Boolean = choices.optBoolean("glasses") ||
    choices.optString("activity").isNotBlank() || listOf("style", "outfit", "footwear", "top", "scene", "lighting")
        .any { choices.optString(it, "auto") != "auto" }

internal fun styledConceptPayload(path: String, payload: JSONObject, choices: JSONObject): JSONObject {
    val result = JSONObject(payload.toString())
    // Saved prompts are immutable and cannot be combined with styling overrides.
    // An explicitly edited full prompt is also sent as-is, matching the web editor.
    if (path.startsWith("concepts/") && result.optString("prompt_mode") != "saved" && !result.has("prompt")) {
        result.put("choices", JSONObject(choices.toString()))
    }
    return result
}

internal fun stylingSummary(choices: JSONObject, menu: JSONObject): String = listOf("outfit", "footwear", "scene").map { key ->
    val options = menu.optJSONArray(key)
    val selected = choices.optString(key, "auto")
    (0 until (options?.length() ?: 0)).map { options!!.getJSONArray(it) }
        .find { it.optString(0) == selected }?.optString(1) ?: selected
}.joinToString(" · ") + if (choices.optBoolean("glasses")) " · Glasses" else ""

@Composable
internal fun ConceptStylingDialog(saved: JSONObject, menu: JSONObject, onDismiss: () -> Unit, onSave: (JSONObject) -> Unit) {
    var draft by remember { mutableStateOf(JSONObject(saved.toString())) }
    var validation by remember { mutableStateOf<String?>(null) }
    fun change(key: String, value: Any) { draft = JSONObject(draft.toString()).put(key, value); validation = null }
    val labels = mapOf("style" to "Style", "outfit" to "Outfit", "footwear" to "Footwear", "top" to "Top", "scene" to "Scene", "lighting" to "Lighting")
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Outfit, footwear & scene") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Applies to new batches and regeneration with the current prompt. Saved prompts keep their original styling.")
            labels.forEach { (key, label) ->
                val options = menu.optJSONArray(key)
                val entries = (0 until (options?.length() ?: 0)).map { options!!.getJSONArray(it) }
                ServerChoice(label, draft.optString(key, "auto"), entries.map { it.getString(0) }, enabled = options != null,
                    labels = entries.associate { it.getString(0) to it.getString(1) }) { value ->
                    change(key, value)
                    if (key == "outfit") change("top", "auto")
                }
                if (key in listOf("outfit", "footwear", "scene") && draft.optString(key) == "custom") {
                    val custom = "custom_$key"
                    val limit = if (key == "footwear") 400 else 600
                    OutlinedTextField(draft.optString(custom), { change(custom, it.take(limit)) }, label = { Text("Custom $key") }, modifier = Modifier.fillMaxWidth())
                }
            }
            Row { Checkbox(draft.optBoolean("glasses"), onCheckedChange = { change("glasses", it) }); Text("Glasses", Modifier.padding(top = 12.dp)) }
            OutlinedTextField(draft.optString("activity"), { change("activity", it.take(400)) }, label = { Text("Activity (optional)") }, modifier = Modifier.fillMaxWidth())
            OutlinedButton(onClick = { draft = defaultConceptChoices().put("outfit", "auto").put("footwear", "auto"); validation = null }) { Text("Use each concept's original styling") }
            validation?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(onClick = { validation = choicesError(draft); if (validation == null) onSave(draft) }) { Text("Apply") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}
