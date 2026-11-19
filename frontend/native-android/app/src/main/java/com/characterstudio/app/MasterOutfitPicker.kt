package com.characterstudio.app

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import org.json.JSONObject

internal fun masterOutfitSource(assets: List<AssetSummary>, id: String): AssetSummary? = assets.find { it.id == id && (it.kind == "template" || (it.selected && it.kind in listOf("reference", "side_profile"))) }
internal fun withMasterOutfit(payload: JSONObject, id: String, assets: List<AssetSummary>): JSONObject {
    if (id.startsWith("preset:")) return JSONObject(payload.toString()).apply {
        remove("outfit_reference_asset_id")
        put("master_outfit", JSONObject().put("outfit", id.removePrefix("preset:")))
    }
    require(id.isEmpty() || masterOutfitSource(assets, id) != null) { "Choose an outfit photo from the selected references." }
    return JSONObject(payload.toString()).apply { remove("master_outfit"); if (id.isEmpty()) remove("outfit_reference_asset_id") else put("outfit_reference_asset_id", id) }
}

@Composable
internal fun MasterOutfitPicker(origin: String, assets: List<AssetSummary>, selectedId: String, enabled: Boolean = true, menu: JSONObject = JSONObject(), onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val presets = menu.optJSONArray("outfit")
    val outfitOptions = (0 until (presets?.length() ?: 0)).map { presets!!.getJSONArray(it) }.filter { it.getString(0) !in listOf("auto", "master", "custom") }
    val presetKey = selectedId.removePrefix("preset:")
    val presetLabel = outfitOptions.find { it.getString(0) == presetKey }?.getString(1)
    val source = masterOutfitSource(assets, selectedId)
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Master outfit", style = MaterialTheme.typography.titleSmall)
        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (source != null) AsyncImage("$origin/api/assets/${source.id}/content", "Selected outfit source", Modifier.size(52.dp), contentScale = ContentScale.Fit)
            Text(if (selectedId.isEmpty()) "Use current Master settings" else presetLabel ?: source?.filename ?: "Outfit source is unavailable", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            TextButton(enabled = enabled, onClick = { expanded = !expanded }) { Text(if (expanded) "Hide" else "Choose photo") }
        }
        ServerChoice("Outfit preset", if (selectedId.startsWith("preset:")) presetKey else "", listOf("") + outfitOptions.map { it.getString(0) }, enabled = enabled && outfitOptions.isNotEmpty(), labels = mapOf("" to "Choose preset…") + outfitOptions.associate { it.getString(0) to it.getString(1) }) { onSelect(if (it.isEmpty()) "" else "preset:$it") }
        if (expanded) {
            Text("Copy clothing from a selected reference or uploaded template. Identity comes from the other references.", style = MaterialTheme.typography.bodySmall)
            TextButton(enabled = enabled, onClick = { onSelect(""); expanded = false }) { Text("Use current Master settings") }
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                assets.filter { (it.kind == "template" || (it.selected && it.kind in listOf("reference", "side_profile"))) }.forEach { asset ->
                    Surface(onClick = { onSelect(asset.id); expanded = false }, enabled = enabled, shape = MaterialTheme.shapes.medium, border = BorderStroke(if (asset.id == selectedId) 2.dp else 1.dp, if (asset.id == selectedId) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
                        Column(Modifier.width(88.dp).padding(4.dp)) {
                            AsyncImage("$origin/api/assets/${asset.id}/content", "Use outfit from ${asset.filename}", Modifier.size(80.dp), contentScale = ContentScale.Fit)
                            Text(asset.filename, style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
        }
    }
}
