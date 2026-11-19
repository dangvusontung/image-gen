package com.characterstudio.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PhotoRetryTest {
    private fun photo(purpose: String) = GalleryItem("asset", "project", "Project", purpose, "image.png", prompt = "original prompt")
    private fun source() = JSONObject().put("id", "version").put("concept_id", "concept").put("job", JSONObject()
        .put("settings", JSONObject().put("size", "1K"))
        .put("meta", JSONObject().put("from_enhancement_id", "previous-enhancement")))

    @Test fun savedConceptPromptIsNotCombinedWithStyling() {
        val plan = photoRetryPlan(photo("concept"), source(), "saved", "ignored", defaultConceptChoices())
        assertEquals("concepts/version/regenerate", plan.path)
        assertEquals("saved", plan.payload.getString("prompt_mode"))
        assertFalse(plan.payload.has("choices"))
        assertFalse(plan.payload.has("prompt"))
        assertEquals("1K", plan.payload.getString("size"))
    }

    @Test fun currentAndEditedConceptPromptsUseTheirOwnPayloads() {
        val choices = defaultConceptChoices()
        val current = photoRetryPlan(photo("concept"), source(), "current", "ignored", choices)
        assertEquals("current", current.payload.getString("prompt_mode"))
        assertEquals(choices.toString(), current.payload.getJSONObject("choices").toString())
        val edited = photoRetryPlan(photo("concept"), source(), "edit", "new prompt", choices)
        assertEquals("new prompt", edited.payload.getString("prompt"))
        assertFalse(edited.payload.has("prompt_mode"))
        assertFalse(edited.payload.has("choices"))
    }

    @Test fun enhancementRetriesKeepSourceAndUseSavedCurrentOrEditedPrompt() {
        val saved = photoRetryPlan(photo("enhance"), source(), "saved", "ignored", defaultConceptChoices())
        assertEquals("concepts/concept/enhance", saved.path)
        assertEquals("original prompt", saved.payload.getString("prompt"))
        assertEquals("previous-enhancement", saved.payload.getString("from_enhancement_id"))
        val current = photoRetryPlan(photo("enhance"), source(), "current", "ignored", defaultConceptChoices())
        assertFalse(current.payload.has("prompt"))
        val edited = photoRetryPlan(photo("enhance"), source(), "edit", "custom prompt", defaultConceptChoices())
        assertEquals("custom prompt", edited.payload.getString("prompt"))
    }

    @Test(expected = IllegalArgumentException::class) fun emptyEditedPromptIsRejected() {
        photoRetryPlan(photo("concept"), source(), "edit", "  ", defaultConceptChoices())
    }
}
