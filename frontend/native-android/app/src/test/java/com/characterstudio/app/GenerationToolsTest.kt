package com.characterstudio.app

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class GenerationToolsTest {
    @Test fun setupRoundTripPreservesAllTargetsAndStyling() {
        val steps = mapOf("master" to GenerationTarget("gemini", "image", "2K"), "concept" to GenerationTarget("bfl", "flux", "1MP"))
        val setup = GenerationSetup("id", "Biển buổi tối", JSONObject().put("scene", "custom").put("custom_scene", "Biển\nHoàng hôn").put("glasses", true).toString(), steps, 4, 3)
        val restored = decodeSetups(encodeSetups(listOf(setup))).single()
        assertEquals(setup.id, restored.id)
        assertEquals(setup.name, restored.name)
        assertEquals(setup.steps, restored.steps)
        assertEquals("Biển\nHoàng hôn", JSONObject(restored.choices).getString("custom_scene"))
        assertEquals(4, restored.masterCount)
        assertEquals(3, restored.customCount)
    }

    @Test fun reviewCountsMasterCustomAndPickedConcepts() {
        assertEquals(4, generationImageCount(GenerationDraft("master/generate", JSONObject().put("variants", 4), "master", emptyList())))
        assertEquals(3, generationImageCount(GenerationDraft("concepts/generate", JSONObject().put("custom", true).put("count", 3), "concept", emptyList())))
        assertEquals(2, generationImageCount(GenerationDraft("concepts/generate", JSONObject().put("slots", JSONArray(listOf(7, 11))), "concept", emptyList())))
        assertEquals(1, generationImageCount(GenerationDraft("concepts/x/regenerate", JSONObject(), "concept", emptyList())))
    }

    @Test fun enhancementOfEnhancedPhotoUsesThatExactSource() {
        val photo = GalleryItem("output", "p", "Project", "enhance", "output.png")
        val enhanced = JSONObject().put("id", "enhancement").put("concept_id", "concept").put("job", JSONObject().put("output_asset_ids", JSONArray(listOf("output"))))
        val plan = batchEnhancePlan(photo, emptyList(), listOf(enhanced))
        assertEquals("concepts/concept/enhance", plan.path)
        assertEquals("enhancement", plan.payload.getString("from_enhancement_id"))
        assertTrue(plan.payload.getBoolean("confirm_reference_subset"))
    }

    @Test(expected = IllegalStateException::class) fun enhancementRejectsUnknownImage() {
        batchEnhancePlan(GalleryItem("missing", "p", "Project", "concept", "missing.png"), emptyList(), emptyList())
    }
}
