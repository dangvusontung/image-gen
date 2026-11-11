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

class BackendClient {
    private val http = OkHttpClient.Builder()
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

    suspend fun updateProjectSettings(origin: String, id: String, name: String, description: String, provider: String, model: String) = withContext(Dispatchers.IO) {
        requestJson("${normalize(origin)}/api/projects/$id", "PATCH", JSONObject()
            .put("name", name.trim()).put("description", description.trim()).put("provider", provider.trim()).put("model", model.trim()))
    }

    suspend fun listProviders(origin: String): List<ProviderSummary> = withContext(Dispatchers.IO) {
        val body = JSONArray(request("${normalize(origin)}/api/providers"))
        buildList { for (index in 0 until body.length()) add(body.getJSONObject(index).toProviderSummary()) }
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

    suspend fun uploadAssets(origin: String, projectId: String, uris: List<Uri>, resolver: ContentResolver): List<AssetSummary> = withContext(Dispatchers.IO) {
        val multipart = okhttp3.MultipartBody.Builder().setType(okhttp3.MultipartBody.FORM)
            .addFormDataPart("kind", "reference")
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

    suspend fun cancelJob(origin: String, jobId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/jobs/$jobId/cancel", "POST")
    }

    suspend fun retryJob(origin: String, jobId: String) = withContext(Dispatchers.IO) {
        request("${normalize(origin)}/api/jobs/$jobId/retry", "POST")
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
            if (!it.isSuccessful) error("Server returned HTTP ${it.code}")
            return it.body?.string().orEmpty()
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
)

data class ProjectDetail(
    val id: String,
    val name: String,
    val description: String?,
    val rightsConfirmed: Boolean,
    val assets: List<AssetSummary>,
    val provider: String = "",
    val model: String = "",
)

data class AssetSummary(val id: String, val filename: String, val kind: String, val selected: Boolean)
data class JobSummary(val id: String, val purpose: String, val status: String, val error: String?, val outputAssetIds: List<String>)
data class GalleryItem(val id: String, val projectId: String, val projectName: String, val purpose: String, val filename: String)
data class ConceptSummary(val id: String, val status: String, val brief: String)
data class ProviderSummary(val name: String, val displayName: String, val selectable: Boolean, val models: List<String>)

private fun JSONObject.toProjectSummary() = ProjectSummary(
    id = getString("id"),
    name = getString("name"),
    description = optString("description").takeIf { it.isNotBlank() && it != "null" },
    assetCount = optInt("asset_count"),
    completedJobs = optInt("completed_jobs"),
    activeJobs = optInt("active_jobs"),
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
)

private fun JSONObject.toConceptSummary() = ConceptSummary(
    id = getString("id"), status = optJSONObject("job")?.optString("status", "unknown") ?: "unknown", brief = optString("brief"),
)

private fun JSONObject.toProviderSummary() = ProviderSummary(
    name = getString("name"), displayName = optString("display_name", getString("name")),
    selectable = optBoolean("selectable"), models = optJSONArray("models")?.let { values ->
        buildList { for (index in 0 until values.length()) add(values.getJSONObject(index).optString("id")) }
    } ?: emptyList(),
)
