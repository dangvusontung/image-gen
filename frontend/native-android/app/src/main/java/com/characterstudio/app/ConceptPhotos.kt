package com.characterstudio.app

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope

internal data class ConceptPhotoResults(val photos: List<GalleryItem>, val failedProjects: Int)

internal data class ConceptLibrarySnapshot(val entries: Map<String, List<GalleryItem>>, val savedAt: Long, val failedProjects: Int = 0) {
    val fresh get() = System.currentTimeMillis() - savedAt in 0 until 15 * 60 * 1000L
}

/** Shared index: one scan populates previews and all-project results for every concept. */
internal class ConceptLibraryRepository(private val context: android.content.Context, private val origin: String) {
    private val directory = java.io.File(context.cacheDir, "concept-library-v2")
    private val key = java.security.MessageDigest.getInstance("SHA-256").digest(origin.trimEnd('/').toByteArray()).joinToString("") { "%02x".format(it) }
    private val file = java.io.File(directory, "$key.json")
    companion object {
        private val memory = java.util.concurrent.ConcurrentHashMap<String, ConceptLibrarySnapshot>()
        private val locks = java.util.concurrent.ConcurrentHashMap<String, kotlinx.coroutines.sync.Mutex>()
    }
    suspend fun read(): ConceptLibrarySnapshot? {
        memory[key]?.let { return it }
        return kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            runCatching {
                val json = org.json.JSONObject(file.readText())
                val entries = json.getJSONObject("entries")
                ConceptLibrarySnapshot(entries.keys().asSequence().associateWith { decodeConceptPhotos(entries.getJSONObject(it).toString()).photos }, json.getLong("saved_at"), json.optInt("failed_projects"))
            }.getOrNull()?.also { memory[key] = it }
        }
    }
    suspend fun remove(assetId: String) {
        PhotoCurationState(context, origin).remove(assetId)
        PhotoSearchRepository.invalidate(context, origin)
        val lock = locks.getOrPut(key) { kotlinx.coroutines.sync.Mutex() }
        lock.lock()
        try {
            val cached = read()
            if (cached != null) memory[key] = cached.copy(entries = cached.entries.mapValues { (_, photos) -> photos.filterNot { it.id == assetId } }, savedAt = 0L)
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                file.delete()
                java.io.File(directory.parentFile, "concept-photos-v1").listFiles()?.forEach { it.delete() }
            }
        } finally { lock.unlock() }
    }
    suspend fun refresh(force: Boolean = false): ConceptLibrarySnapshot {
        val lock = locks.getOrPut(key) { kotlinx.coroutines.sync.Mutex() }
        lock.lock()
        try {
            val old = read()
            if (!force && old?.fresh == true) return old
            val client = BackendClient()
            val projects = client.listProjects(origin)
            val found = mutableListOf<Pair<String, GalleryItem>>()
            val failed = mutableSetOf<String>()
            coroutineScope {
                projects.chunked(4).forEach { batch ->
                    batch.map { project -> async {
                        try {
                            project.id to client.projectArray(origin, project.id, "concepts").flatMap { row ->
                                val job = row.optJSONObject("job")
                                val outputs = job?.optJSONArray("output_asset_ids")
                                if (job?.optString("status") != "succeeded" || outputs == null) emptyList() else
                                    (0 until outputs.length()).map { i ->
                                        val id = outputs.getString(i)
                                        conceptIdentity(row) to GalleryItem(id, project.id, project.name, "concept", "$id.png", prompt = job.optString("prompt"), provider = job.optString("provider"), model = job.optString("model"), createdAt = job.optString("created_at"), tags = (conceptTags(row) + listOfNotNull(conceptCollectionName(row)) + conceptGroup(row) + photoTags(job.optJSONObject("meta") ?: org.json.JSONObject())).distinct(), conceptKey = conceptIdentity(row))
                                    }
                            }
                        } catch (e: CancellationException) { throw e }
                        catch (_: Exception) { project.id to null }
                    } }.awaitAll().forEach { (id, rows) -> if (rows == null) failed += id else found.addAll(rows) }
                }
            }
            old?.entries?.forEach { (identity, photos) -> photos.filter { it.projectId in failed }.forEach { found += identity to it } }
            val snapshot = ConceptLibrarySnapshot(found.groupBy({ it.first }, { it.second }).mapValues { (_, photos) -> photos.distinctBy { it.id }.sortedByDescending { it.createdAt } }, if (failed.isEmpty()) System.currentTimeMillis() else 0L, failed.size)
            memory[key] = snapshot
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                runCatching {
                    directory.mkdirs()
                    val entries = org.json.JSONObject()
                    snapshot.entries.forEach { (identity, photos) -> entries.put(identity, org.json.JSONObject(encodeConceptPhotos(CachedConceptPhotos(photos, snapshot.savedAt)))) }
                    val temp = java.io.File(directory, "$key.tmp")
                    temp.writeText(org.json.JSONObject().put("saved_at", snapshot.savedAt).put("failed_projects", failed.size).put("entries", entries).toString())
                    if (!temp.renameTo(file)) temp.delete()
                }
            }
            return snapshot
        } finally { lock.unlock() }
    }
}
