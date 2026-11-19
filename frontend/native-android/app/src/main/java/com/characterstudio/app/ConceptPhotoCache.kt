package com.characterstudio.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

internal data class CachedConceptPhotos(val photos: List<GalleryItem>, val savedAt: Long) {
    val fresh get() = System.currentTimeMillis() - savedAt in 0 until 5 * 60 * 1000L
}

/** Separate entries per backend and canonical concept; images use Coil's disk cache. */
internal class ConceptPhotoCache(context: Context, origin: String, identity: String) {
    private val directory = File(context.cacheDir, "concept-photos-v1")
    private val digest = MessageDigest.getInstance("SHA-256").digest("${origin.trimEnd('/')}\n$identity".toByteArray()).joinToString("") { "%02x".format(it) }
    private val file = File(directory, "$digest.json")

    suspend fun read(): CachedConceptPhotos? = withContext(Dispatchers.IO) {
        runCatching { decodeConceptPhotos(file.readText()) }.getOrNull()
    }

    suspend fun write(photos: List<GalleryItem>, savedAt: Long = System.currentTimeMillis()) = withContext(Dispatchers.IO) {
        runCatching {
            directory.mkdirs()
            val temporary = File(directory, "$digest.tmp")
            temporary.writeText(encodeConceptPhotos(CachedConceptPhotos(photos, savedAt)))
            if (!temporary.renameTo(file)) temporary.delete()
            directory.listFiles()?.filter { it.extension == "json" }?.sortedByDescending { it.lastModified() }?.drop(64)?.forEach { it.delete() }
        }
        Unit
    }
}

internal fun encodeConceptPhotos(snapshot: CachedConceptPhotos): String {
    val rows = JSONArray()
    snapshot.photos.forEach { p ->
        rows.put(JSONObject().put("id", p.id).put("project_id", p.projectId).put("project_name", p.projectName)
            .put("purpose", p.purpose).put("filename", p.filename).put("prompt", p.prompt).put("provider", p.provider)
            .put("model", p.model).put("width", p.width).put("height", p.height).put("created_at", p.createdAt).put("tags", JSONArray(p.tags)).put("concept_key", p.conceptKey ?: JSONObject.NULL))
    }
    return JSONObject().put("saved_at", snapshot.savedAt).put("photos", rows).toString()
}

internal fun decodeConceptPhotos(json: String): CachedConceptPhotos {
    val snapshot = JSONObject(json)
    val rows = snapshot.getJSONArray("photos")
    return CachedConceptPhotos((0 until rows.length()).map { index ->
        val p = rows.getJSONObject(index)
        GalleryItem(p.getString("id"), p.getString("project_id"), p.getString("project_name"), p.getString("purpose"), p.getString("filename"),
            p.optString("prompt"), p.optString("provider"), p.optString("model"), p.optInt("width"), p.optInt("height"), p.optString("created_at"), p.optJSONArray("tags")?.let { tags -> (0 until tags.length()).map { tags.getString(it) } }.orEmpty(), p.optString("concept_key").takeUnless { it.isBlank() || it == "null" })
    }, snapshot.getLong("saved_at"))
}
