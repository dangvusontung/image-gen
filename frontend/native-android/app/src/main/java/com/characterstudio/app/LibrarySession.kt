package com.characterstudio.app

import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.runtime.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

internal data class FeedPage<T>(val items: List<T>, val total: Int)

internal class PagedFeed<T>(private val scope: CoroutineScope, private val key: (T) -> String, private val fetch: suspend (Int) -> FeedPage<T>) {
    var items by mutableStateOf<List<T>>(emptyList())
        private set
    var total by mutableIntStateOf(0)
        private set
    var loading by mutableStateOf(false)
        private set
    var refreshing by mutableStateOf(false)
        private set
    var loaded by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    private var offset = 0
    private var generation = 0
    val hasMore get() = loaded && offset < total

    fun updateItems(transform: (T) -> T) { items = items.map(transform) }
    fun seed(page: FeedPage<T>) { items = page.items; total = page.total; offset = page.items.size }
    fun ensureLoaded() { if (!loaded && !loading) refresh() }
    fun refresh() = request(reset = true)
    fun loadMore() { if (!loading && hasMore) request(reset = false) }
    fun remove(id: String) { items = items.filterNot { key(it) == id }; total = (total - 1).coerceAtLeast(0); offset = (offset - 1).coerceAtLeast(0) }
    fun request(reset: Boolean) {
        if (!reset && loading) return
        val version = if (reset) ++generation else generation
        val start = if (reset) 0 else offset
        loading = true
        refreshing = reset && loaded
        error = null
        scope.launch {
            try {
                val page = fetch(start)
                if (version != generation) return@launch
                items = (if (reset) page.items else items + page.items).distinctBy(key)
                total = page.total
                offset = if (page.items.isEmpty()) total else start + page.items.size
                loaded = true
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { if (version == generation) error = e.message ?: "Could not load data" }
            finally { if (version == generation) { loading = false; refreshing = false } }
        }
    }
}

internal class LibrarySession(val origin: String, val scope: CoroutineScope, context: android.content.Context) {
    private val client = BackendClient()
    var queue by mutableStateOf<List<QueueJob>>(emptyList())
        private set
    var queueError by mutableStateOf<String?>(null)
        private set
    var queueLoaded by mutableStateOf(false)
        private set
    var queueRevision by mutableIntStateOf(0)
    suspend fun refreshQueue() {
        try {
            val active = client.queueJobs(origin, true)
            val recent = client.queueJobs(origin, false)
            queue = (active + recent).distinctBy { it.id }.sortedByDescending { it.createdAt }
            queueLoaded = true
            queueError = null
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { queueError = e.message }
    }
    var search by mutableStateOf("")
    var showSearch by mutableStateOf(false)
    var sort by mutableStateOf("Default")
    var appliedQuery = ""
    var appliedSort = "updated"
    val listState = LazyListState()
    val gridState = LazyGridState()
    private val cache = context.getSharedPreferences("project-list-cache", android.content.Context.MODE_PRIVATE)
    val projects = PagedFeed(scope, { p: ProjectSummary -> p.id }) { offset ->
        client.projectPage(origin, offset, appliedQuery, appliedSort).also { page ->
            if (offset == 0 && appliedQuery.isEmpty() && appliedSort == "updated") {
                val rows = org.json.JSONArray()
                page.items.forEach { p -> rows.put(org.json.JSONObject().put("id", p.id).put("name", p.name).put("description", p.description).put("asset_count", p.assetCount).put("completed_jobs", p.completedJobs).put("active_jobs", p.activeJobs).put("thumbnail_asset_id", p.thumbnailAssetId)) }
                cache.edit().putString(origin, org.json.JSONObject().put("items", rows).put("total", page.total).toString()).apply()
            }
        }
    }
    init {
        runCatching {
            val saved = org.json.JSONObject(cache.getString(origin, null) ?: return@runCatching)
            val rows = saved.getJSONArray("items")
            projects.seed(FeedPage((0 until rows.length()).map { rows.getJSONObject(it).toProjectSummary() }, saved.getInt("total")))
        }
    }
    val gallery = PagedFeed(scope, { p: GalleryItem -> p.id }) { offset -> client.galleryPage(origin, offset) }
    private val projectGalleries = mutableMapOf<String, PagedFeed<GalleryItem>>()
    fun gallery(projectId: String) = projectGalleries.getOrPut(projectId) {
        PagedFeed(scope, { p: GalleryItem -> p.id }) { offset -> client.galleryPage(origin, offset, projectId) }
    }
    private val projectGrids = mutableMapOf<String, LazyGridState>()
    fun grid(projectId: String) = projectGrids.getOrPut(projectId) { LazyGridState() }
}
