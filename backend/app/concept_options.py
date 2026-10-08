"""User-controlled concept styling, stored in each job's immutable metadata."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConceptChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: Literal["cute", "glamour"] = "cute"
    outfit: Literal["auto", "denim_mix", "denim_shorts", "denim_skirt", "pleated_skirt", "sundress", "custom"] = "denim_mix"
    top: Literal["auto", "tee", "knit", "blouse", "cardigan", "fitted_tank", "cropped_tee"] = "auto"
    scene: Literal["auto", "poolside", "beach", "cafe", "garden", "city", "custom"] = "auto"
    lighting: Literal["auto", "daylight", "golden", "blue_hour"] = "auto"
    custom_outfit: str = Field(default="", max_length=600)
    custom_scene: str = Field(default="", max_length=600)
    activity: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def validate_custom(self):
        if self.outfit == "custom" and not self.custom_outfit.strip():
            raise ValueError("Nhập trang phục tùy chỉnh")
        if self.scene == "custom" and not self.custom_scene.strip():
            raise ValueError("Nhập bối cảnh tùy chỉnh")
        return self


MENU = {
    "style": [("glamour", "Glamour · táo bạo, cuốn hút"), ("cute", "Dễ thương · nhẹ nhàng, ấm áp")],
    "outfit": [("denim_mix", "Phối quần short jeans và chân váy"), ("denim_shorts", "Quần short jeans"), ("denim_skirt", "Chân váy jeans"), ("pleated_skirt", "Chân váy xếp ly"), ("sundress", "Váy mùa hè"), ("auto", "Tự động theo cảnh"), ("custom", "Tùy chỉnh")],
    "top": [("fitted_tank", "Áo tank ôm dáng"), ("cropped_tee", "Áo thun crop"), ("auto", "Tự động phối áo"), ("tee", "Áo thun pastel"), ("knit", "Áo len mỏng"), ("blouse", "Áo blouse"), ("cardigan", "Áo cardigan và áo thun")],
    "scene": [("auto", "Đa dạng bối cảnh"), ("poolside", "Bên hồ bơi"), ("beach", "Bãi biển"), ("cafe", "Quán cà phê"), ("garden", "Vườn hoa"), ("city", "Dạo phố"), ("custom", "Tùy chỉnh")],
    "lighting": [("auto", "Tự động theo cảnh"), ("daylight", "Ban ngày dịu sáng"), ("golden", "Nắng chiều vàng"), ("blue_hour", "Chạng vạng")],
}

SCENE_CHOICES = {
    "poolside": [
        ("a pastel-tiled swimming pool terrace with a striped parasol", "sipping a fruit drink beside the pool", "seated naturally on a dry poolside chair"),
        ("a boutique hotel pool with turquoise water and potted palms", "holding a folded pool towel while smiling", "standing on the dry pool deck"),
        ("a garden swimming pool with mosaic tiles and flowering plants", "reading a small illustrated book beside the water", "seated on a poolside bench"),
        ("a rooftop pool terrace with a distant city skyline", "adjusting a straw sun hat beside a lounger", "standing with a gentle head tilt"),
        ("a courtyard pool with cream umbrellas and soft cushions", "enjoying a bowl of fresh strawberries", "seated comfortably at a poolside table"),
    ],
    "beach": [("a sandy beach with pastel beach umbrellas", "carrying a small basket of seashells", "walking along the dry shoreline")],
    "cafe": [("a cozy outdoor cafe with rounded tables and tiny flowers", "holding a ceramic cup of warm cocoa", "seated comfortably at a cafe table")],
    "garden": [("a flower garden with a pale wooden path", "admiring a small bouquet of daisies", "standing with relaxed shoulders")],
    "city": [("a charming pedestrian street with colorful shopfronts", "carrying a small canvas tote while exploring", "taking a natural mid-stride step")],
}


def apply_choices(brief, choices, slot, prior):
    import random
    result = dict(brief)
    scene = choices.scene
    if scene in SCENE_CHOICES:
        variants = SCENE_CHOICES[scene]
        unused = [v for v in variants if not any(b.get("setting", "").startswith(v[0]) for b in prior)]
        setting, activity, pose = random.SystemRandom().choice(unused or variants)
        result.update(setting=setting, activity=activity, pose=pose)
    elif scene == "custom":
        result.update(setting=choices.custom_scene.strip(), activity="enjoying a gentle candid moment in this setting", pose="a relaxed natural pose suited to the setting")
    if choices.activity.strip():
        result["activity"] = choices.activity.strip()
        result["pose"] = "a natural anatomically coherent pose suited to the chosen activity"
    outfit = choices.outfit
    if outfit == "denim_mix":
        outfit = ("denim_shorts", "denim_skirt", "pleated_skirt")[(slot - 1) % 3]
    tops = {"fitted_tank": "a fitted ribbed tank top", "cropped_tee": "a fitted cropped cotton tee", "auto": "a soft pastel cotton tee", "tee": "a soft pastel cotton tee", "knit": "a lightweight fine-knit top", "blouse": "a soft cotton blouse with rounded buttons", "cardigan": "a lightweight pastel cardigan over a cotton tee"}
    bottoms = {"denim_shorts": "comfortable denim shorts with subtle stitched details", "denim_skirt": "a casual denim skirt with neat seams", "pleated_skirt": "a softly pleated skirt"}
    if outfit in bottoms:
        result["outfit"] = f"{tops[choices.top]} and {bottoms[outfit]}, with simple scene-appropriate shoes"
    elif outfit == "sundress":
        result["outfit"] = "a soft pastel summer dress with delicate embroidery and simple sandals"
    elif outfit == "custom":
        result["outfit"] = choices.custom_outfit.strip()
    elif choices.top != "auto":
        result["outfit"] = f"{tops[choices.top]} with simple coordinating casual bottoms"
    light = choices.lighting
    if light == "auto" and scene in ("poolside", "beach"):
        light = "daylight"
    lights = {"daylight": "soft diffused summer daylight with gentle warm reflected fill", "golden": "warm late-afternoon golden light with soft open shadows", "blue_hour": "soft blue-hour ambient light with warm practical highlights"}
    if light in lights:
        result["lighting"] = lights[light]
        if scene == "auto":
            # Remove the planner's weather/time when the user explicitly selects lighting.
            result["setting"] = result["setting"].split(", ")[0]
    if choices.style == "glamour":
        result["expression"] = "a self-assured half-smile with poised fashion-editorial confidence"
        result["gaze"] = "a confident engaging gaze appropriate to the selected camera angle"
        result["pose"] += "; poised fashion-editorial posture with relaxed shoulders and a natural weight shift"
        if choices.top == "auto" and outfit in bottoms:
            result["outfit"] = f"a fitted ribbed tank top and {bottoms[outfit]}, with coordinated scene-appropriate shoes"
    return result


def style_instruction(choices):
    if choices.style != "glamour":
        return "Keep the warm, cute animated-film direction."
    return ("USER STYLE DIRECTION — GLAMOUR: Prioritize confident, attractive fashion-editorial styling over the default cozy/cute styling. "
            "For an adult subject, use a subtly flirty self-assured half-smile, expressive direct or over-the-shoulder gaze, "
            "a poised natural hip weight shift, relaxed shoulders and elegant limb placement. Keep the chosen scene activity physically believable. "
            "Honor the selected fitted top and denim shorts or skirt, with a polished silhouette, tailored seams and tasteful accessories. "
            "Use warm sun-kissed reflected light, dimensional highlights, cinematic contrast and premium resort-fashion atmosphere where appropriate. "
            "Preserve the actual person's face, apparent age, body shape, skin tone and stylized 3D identity; do not exaggerate anatomy. "
            "Keep clothing opaque and the scene non-explicit. If the subject is a minor, use age-appropriate ordinary fashion poses and styling without flirtatious or sensual direction.")
