package com.characterstudio.app

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private class BackendHttpException(val status: Int, message: String) : IllegalStateException(message)

class BackendClient {
    private var legacyProjectServer: String? = null
    private var legacyProjects = emptyList<ProjectSummary>()
    suspend fun getPrompt(origin: String, projectId: String, name: String): JSONObject = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/prompts/${Uri.encode(name)}?project_id=${Uri.encode(projectId)}")
    }

    suspend fun savePrompt(origin: String, projectId: String, name: String, body: String?): JSONObject = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/prompts/${Uri.encode(name)}?project_id=${Uri.encode(projectId)}", "PUT", JSONObject().put("body", body ?: JSONObject.NULL))
    }

    suspend fun copyPrompts(origin: String, projectId: String, sourceProjectId: String, includeConfiguration: Boolean = false, names: List<String>? = null) = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("source_project_id", sourceProjectId).put("include_configuration", includeConfiguration)
        if (names != null) payload.put("prompt_names", JSONArray(names))
        request("${normalize(origin)}/api/projects/$projectId/prompts/copy", "POST", payload.toString())
        Unit
    }
    suspend fun listBookmarks(origin: String): Set<String> = withContext(Dispatchers.IO) {
        jsonStringList(requestJson("${normalize(origin)}/api/concept-bookmarks"), "keys").toSet()
    }

    suspend fun setBookmark(origin: String, key: String, bookmarked: Boolean) = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/concept-bookmarks/${Uri.encode(key)}", "PUT", JSONObject().put("bookmarked", bookmarked))
        Unit
    }
    suspend fun conceptOptions(origin: String, id: String): JSONObject = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$id/concept-options")
    }
    suspend fun listPresets(origin: String): List<StepPreset> = withContext(Dispatchers.IO) {
        val rows = JSONArray(request("${normalize(origin)}/api/presets"))
        (0 until rows.length()).map { i ->
            val row = rows.getJSONObject(i)
            val steps = row.optJSONObject("steps") ?: JSONObject()
            StepPreset(row.getString("id"), row.getString("name"), steps.keys().asSequence().associateWith { key ->
                val target = steps.getJSONObject(key)
                GenerationTarget(target.getString("provider"), target.getString("model"), target.optString("size").takeUnless { it == "null" }.orEmpty())
            })
        }
    }
    suspend fun suggestConcepts(origin: String, id: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/projects/$id/concept-proposals", "POST")
        Unit
    }
    suspend fun projectArray(origin: String, id: String, path: String): List<JSONObject> = withContext(Dispatchers.IO) {
        val rows = JSONArray(request("${normalize(origin)}/api/projects/$id/$path"))
        buildList { for (i in 0 until rows.length()) add(rows.getJSONObject(i)) }
    }

    internal suspend fun enhancementPlan(origin: String, projectId: String, plan: PhotoRetryPlan): JSONObject = withContext(Dispatchers.IO) {
        val query = plan.payload.optString("from_enhancement_id").takeIf { it.isNotBlank() }?.let { "?from_enhancement_id=${Uri.encode(it)}" }.orEmpty()
        requestJson("${normalize(origin)}/api/projects/$projectId/${plan.path}-plan$query")
    }

    suspend fun projectAction(origin: String, id: String, path: String, payload: JSONObject = JSONObject()): JSONObject = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$id/$path", "POST", payload)
    }
    private val http = OkHttpClient.Builder()
        .callTimeout(20, TimeUnit.SECONDS)
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .build()

    suspend fun check(origin: String): Result<Int> = withContext(Dispatchers.IO) {
        runCatching {
            val base = normalize(origin)
            val health = JSONObject(request("$base/health"))
            require(health.optString("status") == "ok") { "The server did not return a healthy status" }
            val projects = request("$base/api/projects")
            JSONArray(projects).length()
        }
    }

    suspend fun listProjects(origin: String): List<ProjectSummary> = withContext(Dispatchers.IO) {
        val body = JSONArray(request("${normalize(origin)}/api/projects"))
        buildList {
            for (index in 0 until body.length()) add(body.getJSONObject(index).toProjectSummary())
        }
    }

    internal suspend fun projectPage(origin: String, offset: Int, query: String, sort: String): FeedPage<ProjectSummary> = withContext(Dispatchers.IO) {
        if (legacyProjectServer != origin) {
            try {
                val body = requestJson("${normalize(origin)}/api/projects/page?offset=$offset&limit=24&q=${Uri.encode(query)}&sort=$sort")
                val items = body.getJSONArray("items")
                return@withContext FeedPage((0 until items.length()).map { items.getJSONObject(it).toProjectSummary() }, body.getInt("total"))
            } catch (e: BackendHttpException) {
                if (e.status != 404) throw e
                legacyProjectServer = origin
            }
        }
        // Older backends return the full list. Keep it for subsequent local pages.
        if (offset == 0) legacyProjects = listProjects(origin)
        val filtered = legacyProjects.filter { it.name.contains(query, true) || it.description.orEmpty().contains(query, true) }
        val sorted = when (sort) {
            "name_asc" -> filtered.sortedBy { it.name.lowercase(java.util.Locale.ROOT) }
            "name_desc" -> filtered.sortedByDescending { it.name.lowercase(java.util.Locale.ROOT) }
            "photos" -> filtered.sortedByDescending { it.assetCount }
            "active" -> filtered.sortedByDescending { it.activeJobs }
            else -> filtered
        }
        FeedPage(sorted.drop(offset).take(24), sorted.size)
    }

    internal suspend fun galleryPage(origin: String, offset: Int, projectId: String? = null, limit: Int = 48): FeedPage<GalleryItem> = withContext(Dispatchers.IO) {
        val suffix = projectId?.let { "&project_id=${Uri.encode(it)}" }.orEmpty()
        val body = requestJson("${normalize(origin)}/api/gallery?offset=$offset&limit=$limit$suffix")
        val items = body.getJSONArray("items")
        FeedPage((0 until items.length()).map { items.getJSONObject(it).toGalleryItem() }, body.getInt("total"))
    }

    suspend fun createProject(origin: String, name: String, description: String?): ProjectSummary = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("name", name).apply {
            if (!description.isNullOrBlank()) put("description", description)
        }
        requestJson("${normalize(origin)}/api/projects", "POST", payload).toProjectSummary()
    }

    suspend fun deleteProject(origin: String, id: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/projects/$id", "DELETE")
    }

    suspend fun updateProject(origin: String, id: String, rightsConfirmed: Boolean) = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$id", "PATCH", JSONObject().put("rights_confirmed", rightsConfirmed))
    }

    suspend fun updateProjectSettings(origin: String, id: String, name: String, description: String, provider: String, model: String, presetId: String?, workflowMode: String) = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$id", "PATCH", JSONObject()
            .put("name", name.trim()).put("description", description.trim()).put("provider", provider.trim()).put("model", model.trim())
            .put("preset_id", presetId ?: JSONObject.NULL).put("workflow_mode", workflowMode))
    }

    suspend fun listProviders(origin: String): List<ProviderSummary> = withContext(Dispatchers.IO) {
        val body = JSONArray(request("${normalize(origin)}/api/providers"))
        buildList { for (index in 0 until body.length()) add(body.getJSONObject(index).toProviderSummary()) }
            .filter { it.name != "mock" }
    }

    suspend fun getProject(origin: String, id: String): ProjectDetail = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$id").toProjectDetail()
    }

    suspend fun updateAsset(origin: String, assetId: String, selected: Boolean) = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/assets/$assetId", "PATCH", JSONObject().put("selected", selected))
    }

    suspend fun deleteAsset(origin: String, assetId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/assets/$assetId", "DELETE")
    }

    suspend fun uploadAssets(origin: String, projectId: String, uris: List<Uri>, resolver: ContentResolver, kind: String = "reference"): List<AssetSummary> = withContext(Dispatchers.IO) {
        val multipart = okhttp3.MultipartBody.Builder().setType(okhttp3.MultipartBody.FORM)
            .addFormDataPart("kind", kind)
        uris.forEach { uri ->
            val filename = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) else null
            } ?: "image-${System.currentTimeMillis()}.jpg"
            val content = resolver.openInputStream(uri)?.use { it.readBytes() } ?: error("Cannot read $filename")
            multipart.addFormDataPart("files", filename, content.toRequestBody((resolver.getType(uri) ?: "application/octet-stream").toMediaType()))
        }
        val response = http.newCall(
            Request.Builder().url("${normalize(origin)}/api/projects/$projectId/assets").post(multipart.build()).build()
        ).execute()
        response.use {
            if (!it.isSuccessful) error("Server returned HTTP ${it.code}")
            val body = JSONArray(it.body?.string().orEmpty())
            buildList { for (index in 0 until body.length()) add(body.getJSONObject(index).toAssetSummary()) }
        }
    }

    suspend fun generateMaster(origin: String, projectId: String): List<String> = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("variants", 1).put("confirmed", true).put("hairstyle", "reference")
        val body = requestJson("${normalize(origin)}/api/projects/$projectId/master/generate", "POST", payload)
        buildList {
            val ids = body.optJSONArray("job_ids") ?: JSONArray()
            for (index in 0 until ids.length()) add(ids.getString(index))
        }
    }

    suspend fun generateTurnaround(origin: String, projectId: String): List<String> = withContext(Dispatchers.IO) {
        val payload = JSONObject().put("confirmed", true)
        val body = requestJson("${normalize(origin)}/api/projects/$projectId/turnaround/generate", "POST", payload)
        jsonStringList(body, "job_ids")
    }

    suspend fun generateConcepts(origin: String, projectId: String): List<String> = withContext(Dispatchers.IO) {
        val body = requestJson("${normalize(origin)}/api/projects/$projectId/concepts/generate", "POST", JSONObject().put("confirmed", true))
        jsonStringList(body, "job_ids")
    }

    suspend fun approveMaster(origin: String, projectId: String, versionId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/projects/$projectId/master/$versionId/approve", "POST")
    }

    suspend fun approveTurnaround(origin: String, projectId: String, versionId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/projects/$projectId/turnaround/$versionId/approve", "POST", JSONObject().put("adopt_master", false).toString())
    }

    suspend fun workflow(origin: String, projectId: String): JSONObject = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$projectId/workflow")
    }

    suspend fun listJobs(origin: String, projectId: String): List<JobSummary> = withContext(Dispatchers.IO) {
        val body = JSONArray(request("${normalize(origin)}/api/projects/$projectId/jobs?limit=20"))
        buildList {
            for (index in 0 until body.length()) {
                val job = body.getJSONObject(index)
                val outputs = job.optJSONArray("output_asset_ids") ?: JSONArray()
                add(JobSummary(job.getString("id"), job.getString("purpose"), job.getString("status"), job.optString("error_message").takeIf { it.isNotBlank() && it != "null" }, buildList { for (outputIndex in 0 until outputs.length()) add(outputs.getString(outputIndex)) }))
            }
        }
    }

    internal suspend fun queueJobs(origin: String, activeOnly: Boolean): List<QueueJob> = withContext(Dispatchers.IO) {
        val status = if (activeOnly) "&status=queued,submitting,running" else ""
        val rows = JSONArray(request("${normalize(origin)}/api/jobs?limit=200$status"))
        (0 until rows.length()).map { index ->
            val job = rows.getJSONObject(index)
            QueueJob(job.getString("id"), job.getString("project_id"), job.optString("project_name"), job.getString("purpose"), job.getString("status"),
                job.optString("error_message").takeUnless { it.isBlank() || it == "null" }, jsonStringList(job, "output_asset_ids"), job.optString("prompt"), job.optString("provider"), job.optString("model"), job.optString("created_at"))
        }
    }

    suspend fun applyGenerationTargets(origin: String, projectId: String, name: String, steps: Map<String, GenerationTarget>) {
        val existing = listPresets(origin).find { it.steps == steps }
        val presetId = existing?.id ?: withContext(Dispatchers.IO) {
            val config = JSONObject()
            steps.forEach { (step, target) -> config.put(step, JSONObject().put("provider", target.provider).put("model", target.model).put("size", target.size.ifBlank { null } ?: JSONObject.NULL)) }
            requestJson("${normalize(origin)}/api/presets", "POST", JSONObject().put("name", name.take(120)).put("steps", config)).getString("id")
        }
        withContext(Dispatchers.IO) { requestJson("${normalize(origin)}/api/projects/$projectId", "PATCH", JSONObject().put("preset_id", presetId)) }
    }

    suspend fun cancelJob(origin: String, jobId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/jobs/$jobId/cancel", "POST")
    }

    suspend fun retryJob(origin: String, jobId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/jobs/$jobId/retry", "POST")
    }

    suspend fun listTrash(origin: String): List<JSONObject> = withContext(Dispatchers.IO) {
        val rows = JSONArray(request("${normalize(origin)}/api/trash"))
        (0 until rows.length()).map { rows.getJSONObject(it) }
    }

    suspend fun trashAsset(origin: String, assetId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/trash/assets/$assetId", "POST")
    }

    suspend fun trashAction(origin: String, kind: String, id: String, restore: Boolean) = withContext(Dispatchers.IO) {
        val suffix = if (restore) "/restore" else ""
        request("${normalize(origin)}/api/trash/$kind/$id$suffix", if (restore) "POST" else "DELETE")
    }

    suspend fun dismissJob(origin: String, jobId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/jobs/$jobId", "DELETE")
    }

    suspend fun deleteTurnaround(origin: String, projectId: String, versionId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/projects/$projectId/turnaround/$versionId", "DELETE")
    }

    suspend fun dropTurnaroundView(origin: String, projectId: String, versionId: String, angle: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/projects/$projectId/turnaround/$versionId/views/$angle", "DELETE")
    }

    suspend fun listGallery(origin: String, projectId: String? = null): List<GalleryItem> = withContext(Dispatchers.IO) {
        val suffix = projectId?.let { "?project_id=$it" } ?: ""
        val items = requestJson("${normalize(origin)}/api/gallery$suffix").optJSONArray("items") ?: JSONArray()
        buildList { for (index in 0 until items.length()) add(items.getJSONObject(index).toGalleryItem()) }
    }

    suspend fun listConcepts(origin: String, projectId: String): List<ConceptSummary> = withContext(Dispatchers.IO) {
        val items = JSONArray(request("${normalize(origin)}/api/projects/$projectId/concepts"))
        buildList { for (index in 0 until items.length()) add(items.getJSONObject(index).toConceptSummary()) }
    }

    suspend fun enhance(origin: String, projectId: String, conceptId: String) = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$projectId/concepts/$conceptId/enhance", "POST", JSONObject().put("confirm_reference_subset", true))
    }

    private fun request(url: String, method: String = "GET", body: String? = null): String {
        val requestBody = body?.toRequestBody("application/json".toMediaType())
            ?: if (method != "GET" && method != "HEAD") ByteArray(0).toRequestBody("application/json".toMediaType()) else null
        val response = http.newCall(Request.Builder().url(url).method(method, requestBody).build()).execute()
        response.use {
            val content = it.body?.string().orEmpty()
            if (!it.isSuccessful) {
                val message = runCatching { JSONObject(content).optJSONObject("error")?.optString("message")
                    ?: JSONObject(content).optString("detail") }.getOrNull()
                throw BackendHttpException(it.code, message?.takeIf { value -> value.isNotBlank() } ?: "Server returned HTTP ${it.code}")
            }
            return content
        }
    }

    private fun requestJson(url: String, method: String = "GET", payload: JSONObject? = null): JSONObject =
        JSONObject(request(url, method, payload?.toString()))

    private fun jsonStringList(body: JSONObject, key: String): List<String> {
        val values = body.optJSONArray(key) ?: JSONArray()
        return buildList { for (index in 0 until values.length()) add(values.getString(index)) }
    }

    private fun normalize(value: String): String {
        val trimmed = value.trim().removeSuffix("/")
        require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            "Use a URL starting with http:// or https://"
        }
        require(!trimmed.substringAfter("://").contains("/")) {
            "Use only the server origin, without a path"
        }
        return trimmed
    }
}

data class ProjectSummary(
    val id: String,
    val name: String,
    val description: String?,
    val assetCount: Int,
    val completedJobs: Int,
    val activeJobs: Int,
    val thumbnailAssetId: String? = null,
)

data class ProjectDetail(
    val id: String,
    val name: String,
    val description: String?,
    val rightsConfirmed: Boolean,
    val assets: List<AssetSummary>,
    val provider: String = "",
    val model: String = "",
    val presetId: String? = null,
    val workflowMode: String = "manual",
)

data class GenerationTarget(val provider: String, val model: String, val size: String = "")
data class StepPreset(val id: String, val name: String, val steps: Map<String, GenerationTarget>)

fun ProjectDetail.generationTarget(purpose: String, presets: List<StepPreset>): GenerationTarget {
    presets.find { it.id == presetId }?.steps?.get(purpose)?.let { return it }
    if (workflowMode == "hybrid" || workflowMode == "hybrid_gemini") {
        if (purpose == "enhance" && workflowMode == "hybrid") return GenerationTarget("bfl", "flux-2-pro", "1MP")
        return GenerationTarget("gemini", "gemini-nano-banana-2.1", "1K")
    }
    return GenerationTarget(provider, model)
}

data class AssetSummary(val id: String, val filename: String, val kind: String, val selected: Boolean)
data class JobSummary(val id: String, val purpose: String, val status: String, val error: String?, val outputAssetIds: List<String>)
data class GalleryItem(
    val id: String, val projectId: String, val projectName: String, val purpose: String, val filename: String,
    val prompt: String = "", val provider: String = "", val model: String = "",
    val width: Int = 0, val height: Int = 0, val createdAt: String = "",
    val tags: List<String> = emptyList(), val conceptKey: String? = null,
)
data class ConceptSummary(val id: String, val status: String, val brief: String)
data class ProviderSummary(val name: String, val displayName: String, val selectable: Boolean, val models: List<String>, val sizes: Map<String, List<String>> = emptyMap(), val defaultSizes: Map<String, String> = emptyMap())
internal data class QueueJob(val id: String, val projectId: String, val projectName: String, val purpose: String, val status: String, val error: String?, val outputIds: List<String>, val prompt: String, val provider: String, val model: String, val createdAt: String) {
    fun photos() = outputIds.map { GalleryItem(it, projectId, projectName, purpose, "$it.png", prompt, provider, model, createdAt = createdAt) }
}

internal fun JSONObject.toProjectSummary() = ProjectSummary(
    id = getString("id"),
    name = getString("name"),
    description = optString("description").takeIf { it.isNotBlank() && it != "null" },
    assetCount = optInt("asset_count"),
    completedJobs = optInt("completed_jobs"),
    activeJobs = optInt("active_jobs"),
    thumbnailAssetId = optString("thumbnail_asset_id").takeIf { it.isNotBlank() && it != "null" },
)

private fun JSONObject.toProjectDetail() = ProjectDetail(
    id = getString("id"),
    name = getString("name"),
    description = optString("description").takeIf { it.isNotBlank() && it != "null" },
    rightsConfirmed = optBoolean("rights_confirmed"),
    assets = optJSONArray("assets")?.let { values ->
        buildList {
            for (index in 0 until values.length()) {
                val asset = values.getJSONObject(index)
                add(AssetSummary(asset.getString("id"), asset.getString("filename"), asset.getString("kind"), asset.optBoolean("selected", true)))
            }
        }
    } ?: emptyList(),
    provider = optString("provider"), model = optString("model"),
    presetId = optString("preset_id").takeIf { it.isNotBlank() && it != "null" },
    workflowMode = optString("workflow_mode", "manual"),
)

private fun JSONObject.toAssetSummary() = AssetSummary(
    id = getString("id"),
    filename = getString("filename"),
    kind = getString("kind"),
    selected = optBoolean("selected", true),
)

private fun JSONObject.toGalleryItem() = GalleryItem(
    id = getString("id"), projectId = getString("project_id"), projectName = getString("project_name"),
    purpose = getString("purpose"), filename = getString("filename"),
    prompt = optString("prompt").takeUnless { it == "null" }.orEmpty(),
    provider = optString("provider"), model = optString("model"),
    width = optInt("width"), height = optInt("height"), createdAt = optString("created_at"),
    tags = photoTags(optJSONObject("meta") ?: JSONObject()),
)

private fun JSONObject.toConceptSummary() = ConceptSummary(
    id = getString("id"), status = optJSONObject("job")?.optString("status", "unknown") ?: "unknown", brief = optString("brief"),
)

private fun JSONObject.toProviderSummary() = ProviderSummary(
    name = getString("name"), displayName = optString("display_name", getString("name")),
    selectable = optBoolean("selectable"), models = optJSONArray("models")?.let { values ->
        buildList { for (index in 0 until values.length()) add(values.getJSONObject(index).optString("id")) }
    } ?: emptyList(),
    sizes = optJSONArray("models")?.let { rows -> (0 until rows.length()).associate { i -> val row = rows.getJSONObject(i); row.getString("id") to (row.optJSONArray("sizes")?.let { values -> (0 until values.length()).map { values.getString(it) } } ?: emptyList()) } } ?: emptyMap(),
    defaultSizes = optJSONArray("models")?.let { rows -> (0 until rows.length()).associate { i -> val row = rows.getJSONObject(i); row.getString("id") to row.optString("default_size").takeUnless { it == "null" }.orEmpty() } } ?: emptyMap(),
)
