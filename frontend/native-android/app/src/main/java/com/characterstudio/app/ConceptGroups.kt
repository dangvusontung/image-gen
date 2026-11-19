package com.characterstudio.app

import java.text.Normalizer
import org.json.JSONObject

private val catalogGroups = listOf(
    "Living room & everyday" to setOf(1, 9, 10, 17, 21, 28, 53, 54, 55, 56, 115, 116, 131, 132, 133, 134, 135, 139, 147, 148, 149, 152, 153, 155, 160, 161, 162, 171, 182, 183, 186, 187),
    "Bedroom & rest" to setOf(2, 5, 11, 15, 16, 18, 19, 20, 24, 25, 41, 42, 43, 44, 93, 94, 95, 97, 98, 107, 108, 127, 128, 130, 138, 145, 146, 150, 151, 156, 159, 163, 167, 168, 169, 172, 173, 174, 175, 176, 178, 180, 184, 185, 190),
    "Kitchen & windows" to setOf(12, 13, 14, 27, 81, 82, 83, 84),
    "Bathroom" to setOf(22, 45, 46, 47, 48, 105, 106, 144, 96),
    "Beauty & work" to setOf(7, 23, 73, 74, 75, 76),
    "Cafe" to setOf(99, 100, 101, 102, 103, 104, 136, 137),
    "Pool" to setOf(4, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 122, 123, 124, 125, 126, 158),
    "Beach" to setOf(49, 50, 51, 52, 129, 164, 166),
    "Outdoors & travel" to setOf(3, 6, 8, 26, 117, 165),
    "Vietnam" to setOf(85, 86, 87, 88, 89, 90, 91, 92),
    "Fashion & lights" to setOf(61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 109, 110, 111, 112, 113, 114, 118, 119, 120, 121),
    "Studio & portraits" to setOf(57, 58, 59, 60, 77, 78, 79, 80, 154, 157, 170, 177, 179, 181, 188, 189),
    "Yoga" to setOf(140, 141, 142, 143)
)
internal fun conceptGroup(row: JSONObject): String = row.optString("group").takeIf { it.isNotBlank() }
    ?: if (row.optInt("run") > 0 && !row.optString("bookmark_key").startsWith("default:")) "Concept đề xuất"
    else catalogGroups.firstOrNull { row.optInt("slot") in it.second }?.first ?: "Other concepts"
internal fun conceptLabel(row: JSONObject): String = row.optString("label").takeIf { it.isNotBlank() }
    ?: row.optString("title", row.optString("mood"))
internal fun conceptTags(row: JSONObject): List<String> = row.optJSONArray("tags")?.let { tags ->
    (0 until tags.length()).map { tags.optString(it) }
} ?: emptyList()
internal fun conceptOrder(row: JSONObject): Int = if (row.has("display_number") && !row.isNull("display_number")) row.optInt("display_number") else row.optInt("slot")
internal fun conceptIdentity(row: JSONObject): String = row.optString("bookmark_key").takeIf { it.isNotBlank() }
    ?: (row.optString("master_version_id")+":"+row.optInt("slot"))
internal fun searchable(value: String): String = Normalizer.normalize(value, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").lowercase().replace('đ', 'd')
internal fun matchesConcept(row: JSONObject, query: String): Boolean {
    val text = searchable(listOf(conceptLabel(row), row.optString("title", row.optString("mood")),
        row.optJSONObject("brief")?.toString().orEmpty(), conceptGroup(row), row.optString("family"),
        conceptTags(row).joinToString(" "), conceptCollectionName(row).orEmpty(), conceptCollectionId(row).orEmpty(), row.optString("catalog_code"), row.optInt("slot").toString(),
        conceptOrder(row).toString()).joinToString(" "))
    return query.isBlank() || searchable(query.trim()).split(Regex("\\s+")).all { text.contains(it) }
}
