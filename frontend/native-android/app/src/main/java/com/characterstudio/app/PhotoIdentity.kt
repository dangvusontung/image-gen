package com.characterstudio.app

import org.json.JSONObject

internal data class PhotoIdentity(val title: String, val bookmarkKey: String? = null, val tags: List<String> = emptyList())

internal fun photoIdentity(photo: GalleryItem, concepts: List<JSONObject>, enhancements: List<JSONObject>): PhotoIdentity {
    fun owns(row: JSONObject): Boolean {
        val ids = row.optJSONObject("job")?.optJSONArray("output_asset_ids") ?: return false
        return (0 until ids.length()).any { ids.optString(it) == photo.id }
    }
    val concept = when (photo.purpose) {
        "concept" -> concepts.find(::owns)
        "enhance" -> enhancements.find(::owns)?.optString("concept_id")?.let { id -> concepts.find { it.optString("id") == id } }
        else -> null
    }
    val kind = when (photo.purpose) { "master" -> "Master"; "concept" -> "Concept"; "enhance" -> "Enhancement"; "turnaround" -> "Turnaround"; else -> "Photo" }
    if (concept == null) return PhotoIdentity(kind)
    val code = concept.optString("catalog_code").ifBlank { "#"+concept.optInt("slot") }
    return PhotoIdentity("$kind $code · ${conceptLabel(concept)}", conceptIdentity(concept), (photo.tags + conceptTags(concept) + conceptGroup(concept) + photoTags(concept.optJSONObject("job")?.optJSONObject("meta") ?: JSONObject())).distinct())
}

internal fun conceptGalleryPhoto(id: String, projectId: String, projectName: String, row: JSONObject, existing: GalleryItem? = null): GalleryItem {
    val job = row.optJSONObject("job") ?: JSONObject()
    val photo = existing ?: GalleryItem(id, projectId, projectName, "concept", "$id.png", prompt = job.optString("prompt"), provider = job.optString("provider"), model = job.optString("model"), createdAt = job.optString("created_at"))
    return photo.copy(tags = (photo.tags + conceptTags(row) + conceptGroup(row) + photoTags(job.optJSONObject("meta") ?: JSONObject())).distinct(), conceptKey = conceptIdentity(row))
}
