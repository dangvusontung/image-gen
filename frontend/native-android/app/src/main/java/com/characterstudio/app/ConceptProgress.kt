package com.characterstudio.app

import org.json.JSONObject

internal data class ProjectConceptProgress(val rows: List<JSONObject> = emptyList()) {
    val imageIds: List<String> get() = rows.filter { it.optJSONObject("job")?.optString("status") == "succeeded" }
        .flatMap { row -> val ids = row.optJSONObject("job")?.optJSONArray("output_asset_ids"); (0 until (ids?.length() ?: 0)).map { ids!!.getString(it) } }.distinct()
    val active: Boolean get() = rows.any { it.optJSONObject("job")?.optString("status") in listOf("queued", "submitting", "running") }
    val failed: Boolean get() = rows.any { it.optJSONObject("job")?.optString("status") == "failed" }
    fun matches(filter: String): Boolean = when (filter) {
        "created" -> imageIds.isNotEmpty()
        "uncreated" -> rows.isEmpty()
        "active" -> active
        "failed" -> failed && !active && imageIds.isEmpty()
        else -> true
    }
    fun label(): String {
        if (rows.isEmpty()) return "Not created"
        val parts = mutableListOf<String>()
        if (imageIds.isNotEmpty()) parts.add("Created · ${imageIds.size} images")
        if (active) parts.add("Creating…")
        if (parts.isEmpty()) parts.add(if (failed) "Failed" else "Cancelled / no image")
        return parts.joinToString(" · ")
    }
}

internal fun projectConceptProgress(rows: List<JSONObject>): Map<String, ProjectConceptProgress> = rows.groupBy { conceptIdentity(it) }
    .mapValues { (_, versions) -> ProjectConceptProgress(versions.sortedWith(compareByDescending<JSONObject> { it.optInt("run") }.thenByDescending { it.optInt("revision") })) }
