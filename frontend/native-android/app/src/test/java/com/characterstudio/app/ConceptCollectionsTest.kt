package com.characterstudio.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ConceptCollectionsTest {
    private fun row(id: String, slot: Int, collection: String? = "bamboo-poolside") = JSONObject()
        .put("id", id).put("slot", slot).put("bookmark_key", "default:$slot")
        .put("collection_id", collection ?: JSONObject.NULL).put("collection_name", if (collection != null) "Hồ bơi tre xanh" else "")

    @Test fun revisionsCountAsOneConceptAndUnassignedRowsRemainSeparate() {
        val rows = listOf(row("first", 195), row("revision", 195), row("second", 196), row("old", 1, null))
        assertEquals(listOf(ConceptCollectionSummary("bamboo-poolside", "Hồ bơi tre xanh", 2)), conceptCollections(rows))
        assertTrue(matchesCollection(rows.last(), UNASSIGNED_COLLECTION))
        assertFalse(matchesCollection(rows.first(), UNASSIGNED_COLLECTION))
        assertTrue(matchesCollection(rows.last(), ""))
    }

    @Test fun selectSetExcludesDislikesAndDeselectPreservesOtherSelections() {
        val rows = listOf(row("a", 195), row("b", 196), row("c", 197), row("other", 1, null))
        val eligible = selectableCollection(rows, "bamboo-poolside", setOf("default:196"))
        assertEquals(setOf("a", "c"), eligible)
        val selected = toggleCollectionSelection(setOf("other"), eligible)
        assertEquals(setOf("a", "c", "other"), selected)
        assertEquals(setOf("other"), toggleCollectionSelection(selected, eligible))
    }

    @Test fun oldServersNeedNoCollectionFieldsAndCollectionNamesAreSearchable() {
        val legacy = JSONObject().put("id", "old").put("slot", 1)
        assertNull(conceptCollectionId(legacy))
        assertTrue(conceptCollections(listOf(legacy)).isEmpty())
        assertTrue(matchesConcept(row("a", 195), "ho boi tre xanh"))
        assertEquals(setOf("other"), toggleCollectionSelection(setOf("other"), emptySet()))
    }
}
