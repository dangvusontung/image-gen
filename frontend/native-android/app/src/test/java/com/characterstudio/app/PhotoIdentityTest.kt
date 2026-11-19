package com.characterstudio.app

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PhotoIdentityTest {
    private val concept = JSONObject().put("id", "concept-id").put("slot", 5).put("mood", "Reading")
        .put("bookmark_key", "default:5").put("catalog_code", "C005")
        .put("job", JSONObject().put("output_asset_ids", JSONArray(listOf("concept-photo"))))
    private fun photo(id: String, purpose: String) = GalleryItem(id, "project", "Project", purpose, "image.png")

    @Test fun conceptHeaderUsesCanonicalBookmarkIdentity() {
        val identity = photoIdentity(photo("concept-photo", "concept"), listOf(concept), emptyList())
        assertEquals("default:5", identity.bookmarkKey)
        assertTrue(identity.title.contains("C005"))
        assertTrue(identity.title.contains("Reading"))
    }
    @Test fun enhancementBookmarksTheOriginalConcept() {
        val enhancement = JSONObject().put("concept_id", "concept-id").put("job", JSONObject().put("output_asset_ids", JSONArray(listOf("enhanced-photo"))))
        val identity = photoIdentity(photo("enhanced-photo", "enhance"), listOf(concept), listOf(enhancement))
        assertEquals("default:5", identity.bookmarkKey)
        assertTrue(identity.title.startsWith("Enhancement"))
    }
    @Test fun masterHasNoConceptBookmark() {
        assertEquals(PhotoIdentity("Master"), photoIdentity(photo("master", "master"), listOf(concept), emptyList()))
    }
}
