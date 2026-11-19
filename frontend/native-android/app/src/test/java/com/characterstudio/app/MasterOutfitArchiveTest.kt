package com.characterstudio.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MasterOutfitArchiveTest {
    private val assets = listOf(
        AssetSummary("selected", "chosen.png", "reference", true),
        AssetSummary("template", "outfit.png", "template", false),
        AssetSummary("off", "off.png", "reference", false),
        AssetSummary("output", "output.png", "generated", true),
    )

    @Test fun outfitOnlyUsesSelectedSourceImagesAndDoesNotMutateInput() {
        val original = JSONObject().put("variants", 3)
        val payload = withMasterOutfit(original, "selected", assets)
        assertEquals("selected", payload.getString("outfit_reference_asset_id"))
        assertEquals(3, payload.getInt("variants"))
        assertFalse(original.has("outfit_reference_asset_id"))
        assertFalse(withMasterOutfit(payload, "", assets).has("outfit_reference_asset_id"))
        assertNull(masterOutfitSource(assets, "off"))
        assertNull(masterOutfitSource(assets, "output"))
    }

    @Test fun switchingBetweenTemplateAndPresetClearsPreviousSource() {
        val image = withMasterOutfit(JSONObject(), "template", assets)
        assertEquals("template", image.getString("outfit_reference_asset_id"))
        val preset = withMasterOutfit(image, "preset:bikini", assets)
        assertFalse(preset.has("outfit_reference_asset_id"))
        assertEquals("bikini", preset.getJSONObject("master_outfit").getString("outfit"))
        assertFalse(withMasterOutfit(preset, "selected", assets).has("master_outfit"))
    }

    @Test(expected = IllegalArgumentException::class) fun deselectedOutfitIsRejected() { withMasterOutfit(JSONObject(), "off", assets) }

    @Test fun archiveFilterSupportsOlderServersAndCustomRows() {
        val archived = JSONObject().put("run", 0).put("display_number", JSONObject.NULL)
        val custom = JSONObject().put("run", 1).put("display_number", JSONObject.NULL)
        assertTrue(matchesConceptArchive(archived, "archived"))
        assertFalse(matchesConceptArchive(archived, "active"))
        assertTrue(matchesConceptArchive(custom, "active"))
        assertTrue(matchesConceptArchive(archived, "all"))
        assertFalse(archivedConcept(JSONObject().put("archived", false)))
    }
}
