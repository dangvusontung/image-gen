package com.characterstudio.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class CloneConceptTest {
    @Test fun cloneKeepsItsOwnWardrobeChoiceInsteadOfConceptStylingDefaults() {
        val body = JSONObject().put("master_version_id", "master").put("reference_asset_id", "reference").put("keep_master_outfit", true)
        val styled = styledConceptPayload("concepts/clone", body, defaultConceptChoices())
        assertFalse(styled.has("choices"))
        assertTrue(styled.getBoolean("keep_master_outfit"))
        assertEquals(1, generationImageCount(GenerationDraft("concepts/clone", styled, "concept", emptyList())))
    }

    @Test fun currentRetryOfCloneDoesNotInjectTheGeneralOutfitMenu() {
        val photo = GalleryItem("image", "p", "Project", "concept", "image.png")
        val source = JSONObject().put("id", "clone").put("job", JSONObject().put("meta", JSONObject().put("image_clone", true)))
        val retry = photoRetryPlan(photo, source, "current", "", defaultConceptChoices())
        assertEquals("concepts/clone/regenerate", retry.path)
        assertEquals("current", retry.payload.getString("prompt_mode"))
        assertFalse(retry.payload.has("choices"))
    }
}
