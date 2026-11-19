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
import org.json.JSONObject
import java.util.UUID

internal fun imageCountLabel(count: Int) = "$count " + if (count == 1) "image" else "images"

internal data class GenerationDraft(val path: String, val payload: JSONObject, val purpose: String, val concepts: List<String>)

internal fun generationImageCount(draft: GenerationDraft): Int = when {
    draft.purpose == "master" -> draft.payload.optInt("variants", 1)
    draft.payload.optBoolean("custom") -> draft.payload.optInt("count", 1)
    draft.path == "concepts/generate" -> maxOf(draft.payload.optJSONArray("slots")?.length() ?: 0, draft.payload.optJSONArray("proposal_ids")?.length() ?: 0)
    else -> 1
}.coerceAtLeast(1)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun GenerationReviewSheet(origin: String, draft: GenerationDraft, initialTargets: Map<String, GenerationTarget>, choices: JSONObject, menu: JSONObject, providers: List<ProviderSummary>, masterId: String?, referenceCount: Int, setupStore: GenerationSetupStore, referencePhotos: List<AssetSummary> = emptyList(), onEditMaster: () -> Unit, onEditConcepts: () -> Unit, onDismiss: () -> Unit, onConfirm: (GenerationDraft, Map<String, GenerationTarget>, JSONObject) -> Unit) {
    var targets by remember { mutableStateOf(initialTargets) }
    var styling by remember { mutableStateOf(JSONObject(choices.toString())) }
    var payload by remember { mutableStateOf(JSONObject(draft.payload.toString())) }
    var showTarget by remember { mutableStateOf(false) }
    var showSaved by remember { mutableStateOf(false) }
    var showStyling by remember { mutableStateOf(false) }
    var setupName by remember { mutableStateOf("") }
    var saved by remember { mutableStateOf(false) }
    var selectedSetup by remember { mutableStateOf("") }
    var setups by remember { mutableStateOf(setupStore.list()) }
    var validation by remember { mutableStateOf<String?>(null) }
    val target = targets.getValue(draft.purpose)
    val provider = providers.find { it.name == target.provider }
    val modelSizes = provider?.sizes?.get(target.model).orEmpty()
    val editingOutfit = draft.path.endsWith("/outfit")
    val editableStyling = draft.purpose == "concept" && payload.optString("prompt_mode") != "saved" && !payload.has("prompt")
    fun updateTarget(value: GenerationTarget) { targets = targets + (draft.purpose to value); validation = null; saved = false }
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().heightIn(max = androidx.compose.ui.platform.LocalConfiguration.current.screenHeightDp.dp * 0.9f)) {
        Column(Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Review generation", style = MaterialTheme.typography.headlineSmall)
            Text("${imageCountLabel(generationImageCount(draft.copy(payload = payload)))} · ${draft.purpose}", style = MaterialTheme.typography.titleMedium)
            if (editingOutfit) Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (masterId != null) AsyncImage("$origin/api/assets/$masterId/content", "Source Master", Modifier.size(112.dp), contentScale = ContentScale.Fit)
                AsyncImage("$origin/api/assets/${payload.optString("outfit_reference_asset_id")}/content", "Outfit source", Modifier.size(112.dp), contentScale = ContentScale.Fit)
                Text("Only change outfit. A new Master version will need approval.", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            }
            else if (draft.purpose == "master") Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("$referenceCount selected reference images", style = MaterialTheme.typography.bodyMedium)
                MasterOutfitPicker(origin, referencePhotos, payload.optJSONObject("master_outfit")?.optString("outfit")?.let { "preset:$it" } ?: payload.optString("outfit_reference_asset_id").takeUnless { it == "null" }.orEmpty(), menu = menu) { id -> payload = withMasterOutfit(payload, id, referencePhotos); validation = null }
            }
            else Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (masterId != null) AsyncImage("$origin/api/assets/$masterId/content", "Approved master", Modifier.size(72.dp), contentScale = ContentScale.Fit)
                Column {
                    Text("Approved master", style = MaterialTheme.typography.titleSmall)
                    TextButton(onClick = onEditMaster) { Text("Change master") }
                }
            }
            if (draft.concepts.isNotEmpty()) {
                Text(draft.concepts.joinToString("\n"), style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = onEditConcepts) { Text("Change concepts") }
            }
            if ((draft.purpose == "master" && !editingOutfit) || payload.optBoolean("custom")) {
                val key = if (draft.purpose == "master") "variants" else "count"
                ServerChoice("Image count", payload.optInt(key, 1).toString(), listOf("1", "2", "3", "4"), enabled = true) { payload = JSONObject(payload.toString()).put(key, it.toInt()) }
            }
            HorizontalDivider()
            if (editableStyling) {
                Text(stylingSummary(styling, menu), style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { showStyling = true }) { Text("Edit styling") }
            } else if (draft.purpose == "concept") Text("Uses the saved or explicitly edited prompt.", style = MaterialTheme.typography.bodySmall)
            Text("${target.provider} / ${target.model} · ${target.size.ifBlank { "Provider default size" }}", style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = { showTarget = !showTarget }) { Text(if (showTarget) "Hide model settings" else "Change model & size") }
            if (showTarget) {
            ServerChoice("Provider", target.provider, providers.filter { it.selectable }.map { it.name }, enabled = providers.isNotEmpty()) { name ->
                val next = providers.first { it.name == name }
                val model = next.models.firstOrNull().orEmpty()
                updateTarget(GenerationTarget(name, model, next.defaultSizes[model].orEmpty()))
            }
            ServerChoice("Model", target.model, provider?.models.orEmpty(), enabled = provider != null) { model -> updateTarget(target.copy(model = model, size = provider?.defaultSizes?.get(model).orEmpty())) }
            ServerChoice("Size", target.size, listOf("") + modelSizes, labels = mapOf("" to "Provider default"), enabled = modelSizes.isNotEmpty()) { size -> updateTarget(target.copy(size = size)) }
            }
            HorizontalDivider()
            TextButton(onClick = { showSaved = !showSaved }) { Text(if (showSaved) "Hide saved setups" else "Load / save a setup") }
            if (showSaved) {
            ServerChoice("Saved setup", selectedSetup, listOf("") + setups.map { it.id }, enabled = true, labels = mapOf("" to "Choose a setup…") + setups.associate { it.id to it.name }) { id ->
                selectedSetup = id
                setups.find { it.id == id }?.let { setup ->
                    targets = initialTargets + setup.steps
                    styling = JSONObject(setup.choices)
                    if (draft.purpose == "master" && !editingOutfit) payload = JSONObject(payload.toString()).put("variants", setup.masterCount)
                    if (payload.optBoolean("custom")) payload = JSONObject(payload.toString()).put("count", setup.customCount)
                    validation = null
                }
            }
            OutlinedTextField(setupName, { setupName = it.take(80); saved = false }, modifier = Modifier.fillMaxWidth(), label = { Text("Save these settings as…") }, singleLine = true)
            TextButton(enabled = setupName.isNotBlank(), onClick = {
                setupStore.save(GenerationSetup(UUID.randomUUID().toString(), setupName.trim(), styling.toString(), targets, payload.optInt("variants", 1), payload.optInt("count", 1)))
                setups = setupStore.list(); setupName = ""; saved = true
            }) { Text(if (saved) "Setup saved" else "Save setup") }
            }
            }
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            validation?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text("Provider charges may apply. Generation starts only after confirmation.", style = MaterialTheme.typography.bodySmall)
            Button(onClick = {
                validation = if (editableStyling) choicesError(styling) else null
                if (provider?.selectable != true || target.model !in provider.models) validation = "Choose an available provider and model."
                if (target.size.isNotBlank() && modelSizes.isNotEmpty() && target.size !in modelSizes) validation = "Choose a supported image size."
                val outfitId = payload.optString("outfit_reference_asset_id").takeUnless { it == "null" }.orEmpty()
                if (draft.purpose == "master" && !editingOutfit && outfitId.isNotEmpty() && masterOutfitSource(referencePhotos, outfitId) == null) validation = "Choose an outfit photo from the selected references."
                if (validation == null) {
                    val body = JSONObject(payload.toString())
                    if (editableStyling) body.put("choices", JSONObject(styling.toString()))
                    if (draft.purpose == "concept") {
                        if (target.size.isNotBlank()) body.put("size", target.size) else body.remove("size")
                    }
                    onConfirm(draft.copy(payload = body), targets, styling)
                }
            }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Generate ${imageCountLabel(generationImageCount(draft.copy(payload = payload)))}") }
        }
        }
    }
    if (showStyling) ConceptStylingDialog(styling, menu, { showStyling = false }) { styling = it; showStyling = false }
}
