"""User-controlled concept styling, stored in each job's immutable metadata."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConceptChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    glasses: bool = False
    style: Literal["auto", "cute", "glamour"] = "auto"
    outfit: Literal["auto", "denim_mix", "denim_shorts", "denim_skirt", "pleated_skirt", "tennis_skirt",
                    "wide_trousers", "straight_jeans", "cargo_shorts", "sundress", "midi_dress", "knit_dress",
                    "bikini", "satin_dress", "satin_pyjamas", "shirt_shorts", "bodysuit_trousers", "offshoulder_skirt",
                    "pyjamas", "overalls", "linen_set", "blazer_skirt", "tracksuit", "custom"] = "auto"
    top: Literal["auto", "tee", "knit", "blouse", "cardigan", "fitted_tank", "cropped_tee", "shirt",
                 "hoodie", "turtleneck", "polo", "vest"] = "auto"
    scene: Literal["auto", "poolside", "beach", "cafe", "garden", "city", "bedroom", "kitchen", "library",
                   "studio", "rooftop", "park", "market", "office", "vintage_cafe", "garden_cafe", "custom"] = "auto"
    lighting: Literal["auto", "daylight", "golden", "blue_hour"] = "auto"
    custom_outfit: str = Field(default="", max_length=600)
    custom_scene: str = Field(default="", max_length=600)
    activity: str = Field(default="", max_length=400)

    def overrides_concept(self) -> bool:
        """True when the user picked something that should replace the concept's own wording."""
        return any((self.glasses, self.outfit != "auto", self.top != "auto", self.scene != "auto",
                    self.lighting != "auto", self.style != "auto", self.activity.strip()))

    @model_validator(mode="after")
    def validate_custom(self):
        if self.outfit == "custom" and not self.custom_outfit.strip():
            raise ValueError("Nhập trang phục tùy chỉnh")
        if self.scene == "custom" and not self.custom_scene.strip():
            raise ValueError("Nhập bối cảnh tùy chỉnh")
        return self


MENU = {
    "style": [("auto", "Theo từng concept (không ghi đè)"), ("cute", "Dễ thương · nhẹ nhàng, ấm áp"), ("glamour", "Glamour · táo bạo, cuốn hút")],
    "outfit": [("bikini", "Bikini · mặc định"), ("satin_dress", "Váy satin"), ("satin_pyjamas", "Bộ ngủ satin"),
               ("shirt_shorts", "Sơ mi + quần short"), ("bodysuit_trousers", "Bodysuit + quần dài"),
               ("offshoulder_skirt", "Áo trễ vai + chân váy"), ("auto", "Theo từng concept (không ghi đè)"), ("denim_mix", "Phối quần short jeans và chân váy"),
               ("denim_shorts", "Quần short jeans"), ("cargo_shorts", "Quần short cargo"), ("denim_skirt", "Chân váy jeans"),
               ("pleated_skirt", "Chân váy xếp ly"), ("tennis_skirt", "Chân váy tennis"), ("straight_jeans", "Quần jeans ống đứng"),
               ("wide_trousers", "Quần ống rộng"), ("sundress", "Váy mùa hè"), ("midi_dress", "Váy midi"),
               ("knit_dress", "Váy len"), ("pyjamas", "Đồ ngủ"), ("overalls", "Yếm denim"), ("linen_set", "Set linen"),
               ("blazer_skirt", "Blazer và chân váy"), ("tracksuit", "Đồ thể thao"), ("custom", "Tùy chỉnh")],
    "top": [("auto", "Theo từng concept (không ghi đè)"), ("fitted_tank", "Áo tank ôm dáng"), ("cropped_tee", "Áo thun crop"),
            ("tee", "Áo thun pastel"), ("shirt", "Áo sơ mi"), ("blouse", "Áo blouse"), ("knit", "Áo len mỏng"),
            ("turtleneck", "Áo cổ lọ"), ("polo", "Áo polo"), ("hoodie", "Áo hoodie"), ("vest", "Áo gi-lê"),
            ("cardigan", "Áo cardigan và áo thun")],
    "scene": [("auto", "Theo từng concept (không ghi đè)"), ("bedroom", "Phòng ngủ"), ("kitchen", "Bếp"),
              ("library", "Thư viện"), ("studio", "Xưởng sáng tác"), ("cafe", "Quán cà phê"), ("vintage_cafe", "Café vintage · cửa sổ & bàn ăn"), ("garden_cafe", "Café sân vườn · cửa sổ xanh"), ("garden", "Vườn hoa"),
              ("park", "Công viên"), ("rooftop", "Sân thượng"), ("market", "Chợ/phiên chợ"), ("office", "Văn phòng"),
              ("city", "Dạo phố"), ("poolside", "Bên hồ bơi"), ("beach", "Bãi biển"), ("custom", "Tùy chỉnh")],
    "lighting": [("auto", "Theo từng concept (không ghi đè)"), ("daylight", "Ban ngày dịu sáng"), ("golden", "Nắng chiều vàng"), ("blue_hour", "Chạng vạng")],
}

SCENE_CHOICES = {
    "garden_cafe": [('a sunlit cottage cafe window-seat nook with pale yellow timber walls and ceiling beams, wide-open '
  'green-painted casement windows, pink floral curtains, a cushioned wooden bench with rose-patterned '
  'cushions and a small plush white bear, a round white-linen table with a croissant breakfast plate, and a '
  'lush garden of trees, purple flowers and a pale picket fence outside',
  'enjoying a quiet moment in the warm garden sunlight',
  'seated sideways on the cushioned window bench with one knee softly raised, both hands resting on the '
  'cushion beside her for support, shoulders relaxed and chin gently tilted toward the light'),
 ('a sunlit cottage cafe window-seat nook with pale yellow timber walls and ceiling beams, wide-open '
  'green-painted casement windows, pink floral curtains, a cushioned wooden bench with rose-patterned '
  'cushions and a small plush white bear, a round white-linen table with a croissant breakfast plate, and a '
  'lush garden of trees, purple flowers and a pale picket fence outside',
  'turning back toward the camera from the window seat',
  'seated sideways on the bench with legs comfortably folded, hands resting naturally on the cushion, torso '
  'angled toward the garden and head turning over her shoulder toward the camera'),
 ('a sunlit cottage cafe window-seat nook with pale yellow timber walls and ceiling beams, wide-open '
  'green-painted casement windows, pink floral curtains, a cushioned wooden bench with rose-patterned '
  'cushions and a small plush white bear, a round white-linen table with a croissant breakfast plate, and a '
  'lush garden of trees, purple flowers and a pale picket fence outside',
  'watching the garden before breakfast',
  'seated diagonally on the cushioned bench with knees folded naturally to one side, hands on the seat '
  'beside her, back upright and face turned toward the open window')],
    "vintage_cafe": [('a cozy vintage cafe dining nook with cream walls, dark wood wainscoting and a narrow counter, a wall '
  'shelf of decorative books and ceramic plates, hanging wine glasses, large monstera plants, a tall '
  'metal-grille window with tied-back white sheer curtains, leafy trees outside, and a white-linen dining '
  'table with pizza, pasta, salad and a pink fruit drink',
  'turning gently toward the window during a candid cafe moment',
  'standing beside the dark wooden counter with arms relaxed, torso turning toward the window and hair '
  'moving naturally with the turn, face visible in a soft three-quarter angle'),
 ('a cozy vintage cafe dining nook with cream walls, dark wood wainscoting and a narrow counter, a wall '
  'shelf of decorative books and ceramic plates, hanging wine glasses, large monstera plants, a tall '
  'metal-grille window with tied-back white sheer curtains, leafy trees outside, and a white-linen dining '
  'table with pizza, pasta, salad and a pink fruit drink',
  'pausing beside the lunch table while holding a fork',
  'standing upright against the counter, one hand resting lightly on its edge and the other holding a small '
  'fork near shoulder height, head turned gently toward the window'),
 ('a cozy vintage cafe dining nook with cream walls, dark wood wainscoting and a narrow counter, a wall '
  'shelf of decorative books and ceramic plates, hanging wine glasses, large monstera plants, a tall '
  'metal-grille window with tied-back white sheer curtains, leafy trees outside, and a white-linen dining '
  'table with pizza, pasta, salad and a pink fruit drink',
  'enjoying a quiet moment beside the cafe window',
  'standing with one hand resting behind her on the wooden counter, one knee softly bent, the other hand '
  'lightly beside her chin, shoulders relaxed and balanced posture')],
    "poolside": [
        ("a pastel-tiled swimming pool terrace with a striped parasol", "sipping a fruit drink beside the pool", "seated naturally on a dry poolside chair"),
        ("a boutique hotel pool with turquoise water and potted palms", "holding a folded pool towel while smiling", "standing on the dry pool deck"),
        ("a garden swimming pool with mosaic tiles and flowering plants", "reading a small illustrated book beside the water", "seated on a poolside bench"),
        ("a rooftop pool terrace with a distant city skyline", "adjusting a straw sun hat beside a lounger", "standing with a gentle head tilt"),
        ("a courtyard pool with cream umbrellas and soft cushions", "enjoying a bowl of fresh strawberries", "seated comfortably at a poolside table"),
    ],
    "beach": [
        ("a sandy beach with pastel beach umbrellas", "carrying a small basket of seashells", "walking along the dry shoreline"),
        ("a quiet cove at low tide", "watching the water from a flat rock", "seated with knees drawn up"),
        ("a boardwalk above pale dunes", "leaning on the weathered railing", "standing with the breeze in her hair"),
    ],
    "cafe": [
        ("a cozy outdoor cafe with rounded tables and tiny flowers", "holding a ceramic cup of warm cocoa", "seated comfortably at a cafe table"),
        ("a sunlit corner bakery counter", "choosing a pastry from the tray", "standing at the counter, half turned"),
        ("a window seat in a small coffee bar", "writing in a notebook beside her cup", "seated with one elbow on the table"),
    ],
    "garden": [
        ("a flower garden with a pale wooden path", "admiring a small bouquet of daisies", "standing with relaxed shoulders"),
        ("a greenhouse full of potted ferns", "misting the leaves with a spray bottle", "leaning toward a shelf of plants"),
        ("a garden bench under a flowering tree", "resting with a book closed in her lap", "seated, ankles crossed"),
    ],
    "city": [
        ("a charming pedestrian street with colorful shopfronts", "carrying a small canvas tote while exploring", "taking a natural mid-stride step"),
        ("a quiet crossing at golden hour", "waiting for the light to change", "standing with the bag on one shoulder"),
        ("a narrow lane of old shutters and bicycles", "looking into a shop window", "paused mid-step, half turned"),
    ],
    "bedroom": [
        ("a sunlit bedroom with a photo wall and soft rug", "taking a mirror selfie", "perched on the edge of the bed, bare feet on the rug"),
        ("a bed with rumpled pastel bedding", "reading in bed with a mug nearby", "propped against the pillows"),
        ("a bedroom window seat", "watching the street below", "curled up with knees to her chest"),
    ],
    "kitchen": [
        ("a bright white kitchen with a wide window", "pouring coffee into a tall mug", "standing at the counter, weight on one hip"),
        ("a warm wooden kitchen table", "slicing fruit onto a plate", "leaning over the table, sleeves pushed up"),
        ("a kitchen island with fresh herbs", "stirring a bowl with a wooden spoon", "standing square to the island"),
    ],
    "library": [
        ("a reading room with tall windows and dark shelves", "reading an open hardback", "seated on a window bench, legs crossed"),
        ("a quiet aisle between high bookshelves", "pulling a book from the shelf", "standing on tiptoe, arm raised"),
    ],
    "studio": [
        ("a working pottery studio with shelves of raw bowls", "shaping a bowl on the wheel", "leaning in over the wheel"),
        ("a painting studio with canvases against the wall", "mixing colour on a palette", "standing beside the easel"),
    ],
    "rooftop": [
        ("a rooftop herb garden above a city skyline", "watering the planters", "leaning over a wooden planter"),
        ("a rooftop terrace railing at dusk", "looking out over the lights", "standing at the railing, looking back"),
    ],
    "park": [
        ("a park path under tall trees", "walking with a takeaway cup", "taking an easy mid-stride step"),
        ("a picnic blanket on open grass", "laughing at something off-camera", "sitting on the blanket, barefoot"),
    ],
    "market": [
        ("an outdoor flower market under striped awnings", "carrying a wrapped bouquet", "walking between the stalls"),
        ("a morning produce market", "choosing fruit from a crate", "leaning toward the stall"),
    ],
    "office": [
        ("a bright open-plan office", "walking through carrying a tablet", "mid-stride, shoulders square"),
        ("a desk by a wall of windows", "looking up from a laptop", "seated, one hand on the desk"),
    ],
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
    tops = {"fitted_tank": "a fitted ribbed tank top", "cropped_tee": "a fitted cropped cotton tee",
            "auto": "a soft pastel cotton tee", "tee": "a soft pastel cotton tee",
            "knit": "a lightweight fine-knit top", "blouse": "a soft cotton blouse with rounded buttons",
            "cardigan": "a lightweight pastel cardigan over a cotton tee", "shirt": "a crisp cotton shirt",
            "hoodie": "a soft cotton hoodie", "turtleneck": "a fine-knit turtleneck",
            "polo": "a simple knit polo shirt", "vest": "a tailored vest over a plain tee"}
    bottoms = {"denim_shorts": "comfortable denim shorts with subtle stitched details",
               "cargo_shorts": "relaxed cotton cargo shorts",
               "denim_skirt": "a casual denim skirt with neat seams",
               "pleated_skirt": "a softly pleated skirt",
               "tennis_skirt": "a short pleated tennis skirt",
               "straight_jeans": "straight-leg jeans with a clean hem",
               "wide_trousers": "wide-leg cotton trousers"}
    # Complete looks that replace the top as well.
    full_outfits = {
        "sundress": "a soft pastel summer dress with delicate embroidery and simple sandals",
        "midi_dress": "a flowing midi dress with a neat waist and simple shoes",
        "knit_dress": "a fine-knit dress with soft drape and ankle boots",
        "pyjamas": "a white ruffled short-sleeve pyjama set, barefoot",
        "overalls": "denim dungarees over a plain tee, sleeves rolled",
        "linen_set": "a matching linen short-sleeve set in a warm neutral",
        "blazer_skirt": "a tailored blazer over a plain top with a short skirt and loafers",
        "tracksuit": "a soft cotton tracksuit with clean trainers",
    }
    color = ("coral pink", "powder blue", "sage green", "burgundy", "lavender", "champagne beige", "deep teal", "terracotta")[(slot - 1) % 8]
    full_outfits.update({
        "bikini": (result["outfit"] if "bikini" in result["outfit"].lower() else f"an opaque {color} two-piece bikini, barefoot"),
        "satin_dress": f"an opaque {color} satin midi slip dress with thin straps and a softly draped neckline, barefoot",
        "satin_pyjamas": f"an opaque {color} satin camisole and matching fully lined pajama shorts, barefoot",
        "shirt_shorts": f"an opaque {color} relaxed button-up shirt over a white camisole and cream tailored shorts, barefoot",
        "bodysuit_trousers": f"an opaque {color} square-neck bodysuit tucked into cream high-waisted wide-leg trousers, barefoot",
        "offshoulder_skirt": f"an opaque {color} off-shoulder knitted top with a cream fitted midi skirt, barefoot",
    })
    # A user-selected garment replaces the planner's silhouette too, so the prompt
    # never asks for a chosen skirt and a planned pair of shorts at once.
    if outfit in bottoms:
        result["outfit"] = f"{tops[choices.top]} and {bottoms[outfit]}, with simple scene-appropriate shoes"
        result["silhouette"] = bottoms[outfit]
    elif outfit in full_outfits:
        result["outfit"] = full_outfits[outfit]
        result["silhouette"] = full_outfits[outfit].split(",")[0]
    elif outfit == "custom":
        result["outfit"] = choices.custom_outfit.strip()
        result["silhouette"] = "the custom outfit described above, exactly as written"
    elif choices.top != "auto":
        result["outfit"] = f"{tops[choices.top]}, with {result['silhouette']}"
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
            result["silhouette"] = bottoms[outfit]
    if choices.glasses:
        result["outfit"] += "; wearing clear-lens eyeglasses with a simple thin frame, eyes clearly visible"
    return result


def style_instruction(choices):
    if choices.style == "auto":
        # The concept's own expression, gaze and pose stand; nothing is added.
        return ""
    if choices.style != "glamour":
        return "Keep the warm, cute animated-film direction."
    return ("USER STYLE DIRECTION — GLAMOUR: Prioritize confident, attractive fashion-editorial styling over the default cozy/cute styling. "
            "For an adult subject, use a subtly flirty self-assured half-smile, expressive direct or over-the-shoulder gaze, "
            "a poised natural hip weight shift, relaxed shoulders and elegant limb placement. Keep the chosen scene activity physically believable. "
            "Honor the selected fitted top and denim shorts or skirt, with a polished silhouette, tailored seams and tasteful accessories. "
            "Use warm sun-kissed reflected light, dimensional highlights, cinematic contrast and premium resort-fashion atmosphere where appropriate. "
            "Preserve the actual person's face, apparent age, body shape, skin tone and stylized 3D identity; do not exaggerate anatomy. "
            "Keep clothing opaque and the scene non-explicit. If the subject is a minor, use age-appropriate ordinary fashion poses and styling without flirtatious or sensual direction.")
