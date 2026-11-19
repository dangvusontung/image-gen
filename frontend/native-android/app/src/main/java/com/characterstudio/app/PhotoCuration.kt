package com.characterstudio.app

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject

internal data class BestPhoto(val scope: String, val photo: GalleryItem)

internal fun bestPhotoScope(photo: GalleryItem, conceptKey: String?): String? = when (photo.purpose) {
    "concept", "enhance" -> conceptKey?.let { "${photo.projectId}/concept/$it" }
    "master" -> "${photo.projectId}/master"
    else -> "${photo.projectId}/${photo.purpose}/${photo.id}"
}

internal fun updateBestPhotos(entries: List<BestPhoto>, scope: String, photo: GalleryItem): List<BestPhoto> =
    if (entries.any { it.photo.id == photo.id }) entries.filterNot { it.photo.id == photo.id }
    else entries.filterNot { it.scope == scope } + BestPhoto(scope, photo)

internal fun encodeBestPhotos(entries: List<BestPhoto>): String = JSONArray().apply {
    entries.forEach { entry -> put(JSONObject().put("scope", entry.scope).put("photo", JSONObject(encodeConceptPhotos(CachedConceptPhotos(listOf(entry.photo), 0))))) }
}.toString()

internal fun decodeBestPhotos(json: String): List<BestPhoto> {
    val rows = JSONArray(json)
    return (0 until rows.length()).map { index -> val row = rows.getJSONObject(index); BestPhoto(row.getString("scope"), decodeConceptPhotos(row.getJSONObject("photo").toString()).photos.single()) }
}

internal class PhotoCurationState(context: Context, private val origin: String) {
    private val prefs = context.getSharedPreferences("best-photos-v1", Context.MODE_PRIVATE)
    var best by mutableStateOf(read())
        private set
    private fun read() = runCatching { decodeBestPhotos(prefs.getString(origin, "[]") ?: "[]") }.getOrDefault(emptyList())
    fun isBest(id: String) = best.any { it.photo.id == id }
    fun toggle(scope: String, photo: GalleryItem) { val next = updateBestPhotos(read(), scope, photo); prefs.edit().putString(origin, encodeBestPhotos(next)).apply(); best = next }
    fun remove(id: String) { if (read().none { it.photo.id == id }) return; prefs.edit().putString(origin, encodeBestPhotos(read().filterNot { it.photo.id == id })).apply(); best = read() }
    fun observe(): () -> Unit {
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, key -> if (key == origin) best = read() }
        prefs.registerOnSharedPreferenceChangeListener(listener)
        return { prefs.unregisterOnSharedPreferenceChangeListener(listener) }
    }
}

@Composable
internal fun rememberPhotoCuration(origin: String): PhotoCurationState {
    val context = LocalContext.current
    val state = remember(origin) { PhotoCurationState(context.applicationContext, origin) }
    DisposableEffect(state) { val stop = state.observe(); onDispose { stop() } }
    return state
}

@Composable
internal fun BestPhotoBadge(modifier: Modifier = Modifier) {
    Surface(modifier, color = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary, shape = MaterialTheme.shapes.small) {
        Row(Modifier.padding(horizontal = 6.dp, vertical = 3.dp), horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            Icon(DetailIcons.Best, "Best photo", Modifier.size(14.dp))
            Text("Best", style = MaterialTheme.typography.labelSmall)
        }
    }
}
