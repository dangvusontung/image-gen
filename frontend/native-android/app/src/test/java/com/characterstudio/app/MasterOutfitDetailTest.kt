package com.characterstudio.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MasterOutfitDetailTest {
    @Test fun resolvesTheViewedMasterInsteadOfTheApprovedOrNewestOne() {
        val workflow = JSONObject("""{"approved_master_id":"new","masters":[
            {"id":"new","job":{"status":"succeeded","output_asset_ids":["new-photo"]}},
            {"id":"old","job":{"status":"succeeded","output_asset_ids":["old-photo"]}},
            {"id":"failed","job":{"status":"failed","output_asset_ids":["failed-photo"]}}
        ]}""")
        assertEquals("old", masterVersionForImage(workflow, "old-photo"))
        assertEquals("new", masterVersionForImage(workflow, "new-photo"))
        assertNull(masterVersionForImage(workflow, "failed-photo"))
        assertNull(masterVersionForImage(workflow, "missing"))
    }
    @Test fun presetAndPhotoAreExclusiveOutfitSources() {
        val preset = masterOutfitEditPayload("preset:tank_pleated_classic")
        assertEquals("tank_pleated_classic", preset.getJSONObject("master_outfit").getString("outfit"))
        assertFalse(preset.has("outfit_reference_asset_id"))
        val photo = masterOutfitEditPayload("photo")
        assertEquals("photo", photo.getString("outfit_reference_asset_id"))
        assertFalse(photo.has("master_outfit"))
        assertEquals("Yellow sweatshirt", masterOutfitEditPayload("preset:custom", "Yellow sweatshirt").getJSONObject("master_outfit").getString("custom_outfit"))
    }

    @Test(expected = IllegalArgumentException::class) fun customOutfitRequiresDescription() { masterOutfitEditPayload("preset:custom") }
}
