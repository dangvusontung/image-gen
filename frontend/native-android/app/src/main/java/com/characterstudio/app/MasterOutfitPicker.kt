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

internal fun masterOutfitSource(assets: List<AssetSummary>, id: String): AssetSummary? = assets.find { it.id == id && it.selected && it.kind in listOf("reference", "side_profile") }
internal fun withMasterOutfit(payload: JSONObject, id: String, assets: List<AssetSummary>): JSONObject {
    require(id.isEmpty() || masterOutfitSource(assets, id) != null) { "Choose an outfit photo from the selected references." }
    return JSONObject(payload.toString()).apply { if (id.isEmpty()) remove("outfit_reference_asset_id") else put("outfit_reference_asset_id", id) }
}

@Composable
internal fun MasterOutfitPicker(origin: String, assets: List<AssetSummary>, selectedId: String, enabled: Boolean = true, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val source = masterOutfitSource(assets, selectedId)
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Master outfit", style = MaterialTheme.typography.titleSmall)
        Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (source != null) AsyncImage("$origin/api/assets/${source.id}/content", "Selected outfit source", Modifier.size(52.dp), contentScale = ContentScale.Fit)
            Text(if (selectedId.isEmpty()) "Use current Master settings" else source?.filename ?: "Outfit photo is no longer selected", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            TextButton(enabled = enabled, onClick = { expanded = !expanded }) { Text(if (expanded) "Hide" else "Choose photo") }
        }
        if (expanded) {
            Text("Copy clothing from one selected reference. Identity comes from the other references.", style = MaterialTheme.typography.bodySmall)
            TextButton(enabled = enabled, onClick = { onSelect(""); expanded = false }) { Text("Use current Master settings") }
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                assets.filter { it.selected && it.kind in listOf("reference", "side_profile") }.forEach { asset ->
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
