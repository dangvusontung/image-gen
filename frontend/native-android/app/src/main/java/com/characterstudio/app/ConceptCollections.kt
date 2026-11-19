package com.characterstudio.app

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject

internal const val UNASSIGNED_COLLECTION = "__unassigned"
internal data class ConceptCollectionSummary(val id: String, val name: String, val count: Int)

internal fun conceptCollectionId(row: JSONObject): String? = row.optString("collection_id").takeUnless { it.isBlank() || it == "null" }
internal fun conceptCollectionName(row: JSONObject): String? = conceptCollectionId(row)?.let { id -> row.optString("collection_name").takeUnless { it.isBlank() || it == "null" } ?: id }
internal fun conceptCollections(rows: List<JSONObject>): List<ConceptCollectionSummary> = rows.filter { conceptCollectionId(it) != null }
    .groupBy { conceptCollectionId(it)!! }.map { (id, items) -> ConceptCollectionSummary(id, conceptCollectionName(items.first())!!, items.map(::conceptIdentity).distinct().size) }.sortedBy { it.name }

internal fun matchesCollection(row: JSONObject, filter: String): Boolean = when (filter) {
    "" -> true
    UNASSIGNED_COLLECTION -> conceptCollectionId(row) == null
    else -> conceptCollectionId(row) == filter
}

internal fun selectableCollection(rows: List<JSONObject>, collectionId: String, dislikes: Set<String>): Set<String> =
    rows.filter { conceptCollectionId(it) == collectionId && conceptIdentity(it) !in dislikes }.map { it.getString("id") }.toSet()

internal fun toggleCollectionSelection(selected: Set<String>, eligible: Set<String>): Set<String> =
    if (eligible.isNotEmpty() && selected.containsAll(eligible)) selected - eligible else selected + eligible

@Composable
internal fun ConceptCollectionFilters(collections: List<ConceptCollectionSummary>, selected: String, hasUnassigned: Boolean, onSelect: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = selected.isEmpty(), onClick = { onSelect("") }, label = { Text("All sets") })
        collections.forEach { collection -> FilterChip(selected = selected == collection.id, onClick = { onSelect(collection.id) }, label = { Text("${collection.name} · ${collection.count}") }) }
        if (hasUnassigned) FilterChip(selected = selected == UNASSIGNED_COLLECTION, onClick = { onSelect(UNASSIGNED_COLLECTION) }, label = { Text("Chưa có bộ") })
    }
}

internal fun archivedConcept(row: JSONObject): Boolean = if (row.has("archived")) row.optBoolean("archived")
    else row.optInt("run") == 0 && row.has("display_number") && row.isNull("display_number")
internal fun matchesConceptArchive(row: JSONObject, filter: String): Boolean = filter == "all" || archivedConcept(row) == (filter == "archived")
