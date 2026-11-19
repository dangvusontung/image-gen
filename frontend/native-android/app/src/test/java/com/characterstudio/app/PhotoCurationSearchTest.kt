package com.characterstudio.app

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PhotoCurationSearchTest {
    private fun photo(id: String, project: String = "p", purpose: String = "concept") = GalleryItem(id, project, "Project", purpose, "$id.png", tags = listOf("Bãi biển", "Váy đỏ"), conceptKey = "default:7")

    @Test fun bestReplacesOnlyTheSameConceptInTheSameProject() {
        val a = photo("a")
        val b = photo("b")
        val other = photo("other", "q")
        val first = updateBestPhotos(emptyList(), bestPhotoScope(a, a.conceptKey)!!, a)
        val second = updateBestPhotos(first, bestPhotoScope(other, other.conceptKey)!!, other)
        val result = updateBestPhotos(second, bestPhotoScope(b, b.conceptKey)!!, b)
        assertEquals(setOf("b", "other"), result.map { it.photo.id }.toSet())
        val enhanced = photo("enhanced", purpose = "enhance")
        assertEquals(bestPhotoScope(b, b.conceptKey), bestPhotoScope(enhanced, enhanced.conceptKey))
        assertNull(bestPhotoScope(a, null))
    }

    @Test fun bestCanBeRemovedAndSurvivesSerializationWithTags() {
        val p = photo("a")
        val scope = bestPhotoScope(p, p.conceptKey)!!
        val entries = updateBestPhotos(emptyList(), scope, p)
        assertEquals(entries, decodeBestPhotos(encodeBestPhotos(entries)))
        assertTrue(updateBestPhotos(entries, scope, p).isEmpty())
    }

    @Test fun searchMatchesVietnameseTagsWithoutAccentsAndCombinesTagWithText() {
        val p = photo("a").copy(prompt = "Sunny beach with warm lighting")
        assertTrue(matchesPhoto(p, "#bai bien"))
        assertTrue(matchesPhoto(p, "vay do"))
        assertTrue(matchesPhoto(p, "warm", "Bãi biển"))
        assertFalse(matchesPhoto(p, "warm", "Studio"))
        assertFalse(matchesPhoto(p, "snow"))
    }

    @Test fun tagExtractionUsesActualChoicesAndKeepsCustomDescriptions() {
        val meta = JSONObject().put("tags", JSONArray(listOf("Bãi biển")))
            .put("concept_choices", JSONObject().put("outfit", "custom").put("custom_outfit", "Váy đỏ").put("scene", "beach_sunset").put("style", "auto"))
        assertEquals(setOf("Bãi biển", "Váy đỏ", "beach sunset"), photoTags(meta).toSet())
    }
}
