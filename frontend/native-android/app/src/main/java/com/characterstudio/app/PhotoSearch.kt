package com.characterstudio.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

internal fun photoTags(meta: JSONObject): List<String> {
    val tags = mutableListOf<String>()
    for (key in listOf("tags", "concept_tags")) {
        val values = meta.optJSONArray(key)
        for (i in 0 until (values?.length() ?: 0)) tags += values!!.optString(i)
    }
    meta.optJSONObject("concept_choices")?.let { choices ->
        listOf("style", "outfit", "footwear", "scene", "lighting").forEach { key ->
            val value = choices.optString(key)
            if (value == "custom") tags += choices.optString("custom_$key") else tags += value.replace('_', ' ')
        }
    }
    (meta.optJSONObject("brief") ?: meta.optJSONObject("concept_brief"))?.let { brief ->
        listOf("setting", "activity", "outfit", "lighting").forEach { tags += brief.optString(it) }
    }
    return tags.map { it.trim() }.filter { it.isNotBlank() && it !in listOf("auto", "null") && it.length <= 60 }.distinct()
}

internal fun matchesPhoto(photo: GalleryItem, query: String, tag: String = ""): Boolean {
    val tags = photo.tags.map(::searchable)
    if (tag.isNotBlank() && searchable(tag) !in tags) return false
    if (query.isBlank()) return true
    val text = searchable(listOf(photo.projectName, photo.purpose, photo.filename, photo.prompt, photo.tags.joinToString(" ")).joinToString(" "))
    return searchable(query).replace('#', ' ').trim().split(Regex("\\s+")).filter { it.isNotBlank() }.all { it in text }
}

internal data class PhotoSearchSnapshot(val photos: List<GalleryItem>, val savedAt: Long) {
    val fresh get() = System.currentTimeMillis() - savedAt in 0 until 5 * 60 * 1000L
}

internal class PhotoSearchRepository(private val context: Context, private val origin: String, private val projectId: String?) {
    private val memoryKey = "$origin|${projectId.orEmpty()}"
    private val directory = File(context.cacheDir, "gallery-search-v1/${digest(origin)}")
    private val file = File(directory, "${digest(projectId ?: "all")}.json")
    companion object {
        private val memory = java.util.concurrent.ConcurrentHashMap<String, PhotoSearchSnapshot>()
        private fun cache(key: String, value: PhotoSearchSnapshot) {
            memory[key] = value
            memory.entries.sortedByDescending { it.value.savedAt }.drop(6).forEach { memory.remove(it.key) }
        }
        private fun digest(value: String) = MessageDigest.getInstance("SHA-256").digest(value.toByteArray()).joinToString("") { "%02x".format(it) }
        suspend fun invalidate(context: Context, origin: String) = withContext(Dispatchers.IO) {
            memory.keys.filter { it.startsWith("$origin|") }.forEach { memory.remove(it) }
            File(context.cacheDir, "gallery-search-v1/${digest(origin)}").listFiles()?.forEach { it.delete() }
        }
    }
    suspend fun read(): PhotoSearchSnapshot? {
        memory[memoryKey]?.let { return it }
        return withContext(Dispatchers.IO) { runCatching { decodeConceptPhotos(file.readText()).let { PhotoSearchSnapshot(it.photos, it.savedAt) } }.getOrNull()?.also { cache(memoryKey, it) } }
    }
    suspend fun refresh(onProgress: (List<GalleryItem>, Int) -> Unit): PhotoSearchSnapshot {
        val client = BackendClient()
        val taxonomy = ConceptLibraryRepository(context, origin).read()?.entries?.values?.flatten()?.associateBy { it.id }.orEmpty()
        val result = mutableListOf<GalleryItem>()
        var offset = 0
        var total: Int
        do {
            val page = client.galleryPage(origin, offset, projectId, limit = 100)
            total = page.total
            result += page.items.map { photo -> taxonomy[photo.id]?.let { extra -> photo.copy(tags = (photo.tags + extra.tags).distinct(), conceptKey = extra.conceptKey) } ?: photo }
            offset += page.items.size
            if (offset % 500 == 0 || offset >= total || page.items.isEmpty()) onProgress(result.distinctBy { it.id }, total)
            if (page.items.isEmpty()) break
        } while (offset < total)
        val snapshot = PhotoSearchSnapshot(result.distinctBy { it.id }, System.currentTimeMillis())
        cache(memoryKey, snapshot)
        withContext(Dispatchers.IO) {
            runCatching {
                directory.mkdirs()
                val temp = File(directory, "${file.name}.tmp")
                temp.writeText(encodeConceptPhotos(CachedConceptPhotos(snapshot.photos, snapshot.savedAt)))
                if (!temp.renameTo(file)) temp.delete()
                directory.listFiles()?.filter { it.extension == "json" }?.sortedByDescending { it.lastModified() }?.drop(12)?.forEach { it.delete() }
            }
        }
        return snapshot
    }
}
