package com.characterstudio.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ConceptPolicyTest {
    @Test fun backendBookmarkIdentityWinsOverCharacterAndVersion() {
        val a = JSONObject().put("bookmark_key", "default:155").put("master_version_id", "first-character").put("slot", 155)
        val b = JSONObject().put("bookmark_key", "default:155").put("master_version_id", "second-character").put("slot", 155).put("revision", 4)
        assertEquals(conceptIdentity(a), conceptIdentity(b))
        assertTrue(conceptIdentity(b) in setOf("default:155", "default:159"))
    }

    private fun project(mode: String = "manual", preset: String? = null) = ProjectDetail("p", "test", null, true, emptyList(), "mock", "mock-v1", preset, mode)

    @Test fun partialPresetOverridesOnlyItsConfiguredSteps() {
        val target = GenerationTarget("modelark", "dola", "1K")
        val presets = listOf(StepPreset("saved", "ok 2", mapOf("master" to target)))
        val p = project("hybrid", "saved")
        assertEquals(target, p.generationTarget("master", presets))
        assertEquals(GenerationTarget("gemini", "gemini-nano-banana-2.1", "1K"), p.generationTarget("concept", presets))
        assertEquals(GenerationTarget("bfl", "flux-2-pro", "1MP"), p.generationTarget("enhance", presets))
    }

    @Test fun missingPresetFallsBackToSavedManualSettings() {
        assertEquals(GenerationTarget("mock", "mock-v1"), project(preset = "removed").generationTarget("concept", emptyList()))
    }

    @Test fun searchMatchesTitleBriefAndCategoryWithoutAccents() {
        val row = JSONObject().put("slot", 4).put("title", "Café portrait")
            .put("brief", JSONObject().put("outfit", "Blue jacket"))
        assertTrue(matchesConcept(row, "CAFE"))
        assertTrue(matchesConcept(row, "blue jacket"))
        assertTrue(matchesConcept(row, "pool"))
        assertFalse(matchesConcept(row, "missing"))
        assertTrue(matchesConcept(JSONObject(), ""))
    }

    @Test fun favouritesStayWithConceptAcrossVersionsAndBatchesButNotAnotherMaster() {
        val a = JSONObject().put("master_version_id", "m1").put("slot", 4).put("revision", 1).put("run", 1)
        val b = JSONObject(a.toString()).put("revision", 2).put("run", 2)
        assertEquals(conceptIdentity(a), conceptIdentity(b))
        b.put("master_version_id", "m2")
        assertNotEquals(conceptIdentity(a), conceptIdentity(b))
    }
    @Test fun savedAndExplicitPromptsNeverReceiveStylingOverrides() {
        val choices = defaultConceptChoices().put("outfit", "sundress")
        val saved = styledConceptPayload("concepts/c/regenerate", JSONObject().put("prompt_mode", "saved"), choices)
        assertFalse(saved.has("choices"))
        val explicit = styledConceptPayload("concepts/c/regenerate", JSONObject().put("prompt", "my full prompt"), choices)
        assertFalse(explicit.has("choices"))
        assertEquals("my full prompt", explicit.getString("prompt"))
        val current = styledConceptPayload("concepts/c/regenerate", JSONObject().put("prompt_mode", "current"), choices)
        assertEquals("sundress", current.getJSONObject("choices").getString("outfit"))
        val batch = styledConceptPayload("concepts/generate", JSONObject().put("slots", org.json.JSONArray(listOf(4))), choices)
        assertEquals("barefoot", batch.getJSONObject("choices").getString("footwear"))
        assertEquals(4, batch.getJSONArray("slots").getInt(0))
        choices.put("outfit", "auto")
        assertEquals("sundress", current.getJSONObject("choices").getString("outfit"))
    }

    @Test fun customStylingRequiresDescriptionsAndCanReturnToConceptDefaults() {
        val choices = defaultConceptChoices().put("outfit", "custom")
        assertNotNull(choicesError(choices))
        choices.put("custom_outfit", "linen shirt and trousers")
        assertNull(choicesError(choices))
        assertTrue(overridesConcept(choices))
        choices.put("outfit", "auto").put("footwear", "auto")
        assertFalse(overridesConcept(choices))
    }

    @Test fun createdConceptProgressUsesOnlyThisProjectsHistoryAndKeepsOlderSuccesses() {
        fun row(run: Int, revision: Int, status: String, ids: List<String> = emptyList()) = JSONObject()
            .put("id", "$run-$revision").put("bookmark_key", "default:155").put("run", run).put("revision", revision)
            .put("job", JSONObject().put("status", status).put("output_asset_ids", org.json.JSONArray(ids)))
        val history = projectConceptProgress(listOf(row(1, 1, "succeeded", listOf("a")), row(2, 1, "running")))
        val state = history.getValue("default:155")
        assertEquals(listOf("a"), state.imageIds)
        assertTrue(state.matches("created"))
        assertTrue(state.matches("active"))
        assertFalse(state.matches("uncreated"))
        assertEquals(2, state.rows.first().optInt("run"))
        val other = projectConceptProgress(emptyList())
        assertFalse(other.containsKey("default:155"))
        val failed = ProjectConceptProgress(listOf(row(1, 1, "failed")))
        assertTrue(failed.matches("failed"))
        assertFalse(failed.matches("created"))
    }

}
