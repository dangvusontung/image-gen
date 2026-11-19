package com.characterstudio.app

import org.junit.Assert.*
import org.junit.Test

class ConceptPhotoCacheTest {
    @Test fun preservesViewerMetadataAndTimestamp() {
        val photo = GalleryItem("image", "project", "Dự án", "concept", "image.png", "**Prompt**\n\nNội dung", "gemini", "model", 1024, 2048, "2026-11-18")
        val snapshot = CachedConceptPhotos(listOf(photo), 123L)
        assertEquals(snapshot, decodeConceptPhotos(encodeConceptPhotos(snapshot)))
        assertFalse(snapshot.fresh)
    }

    @Test fun emptyResultsAreCachedToo() {
        val snapshot = CachedConceptPhotos(emptyList(), System.currentTimeMillis())
        assertEquals(snapshot, decodeConceptPhotos(encodeConceptPhotos(snapshot)))
        assertTrue(snapshot.fresh)
    }
}
