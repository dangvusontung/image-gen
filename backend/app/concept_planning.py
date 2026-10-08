"""Fresh, persisted scene briefs independent of mood/angle assignments."""
import random

SLOTS = (
    (1, "Cute & Cozy", "front-facing"),
    (2, "Playful & Mischievous", "left three-quarter"),
    (3, "Soft & Dreamy", "right profile"),
    (4, "Fresh & Adventurous", "over-the-shoulder"),
    (5, "Casual & Charming", "high-angle candid"),
    (6, "Elegant & Confident", "right three-quarter"),
    (7, "Chic & Fashionable", "low-angle environmental"),
    (8, "Glamorous & Bold", "wide full-body"),
    (9, "Mysterious & Cinematic", "dynamic off-center"),
)

# Settings and activities are drawn independently from moods, not fixed scenes per slot.
SCENES = (
    ("a sunlit pottery studio", "shaping a clay bowl on a wheel", "a linen shirt and canvas apron", "seated with hands shaping the bowl"),
    ("a rooftop herb garden", "watering aromatic herbs", "a relaxed knit and utility trousers", "leaning toward a terracotta planter"),
    ("an old railway platform", "checking a travel notebook", "a light trench coat and walking boots", "standing beside a travel bag"),
    ("a riverside book market", "browsing illustrated books", "a corduroy jacket and loose trousers", "holding an open book at waist height"),
    ("a mountain observation deck", "unfolding a trail map", "a weatherproof jacket and hiking trousers", "one foot on a low wooden step"),
    ("a glasshouse orchid nursery", "examining an orchid blossom", "a soft cotton blouse and rolled trousers", "reaching gently toward a flower"),
    ("a small neighborhood bakery", "carrying a tray of fresh bread", "a woven cardigan and bakery apron", "balancing the tray with both hands"),
    ("a contemporary sculpture courtyard", "sketching a bronze sculpture", "a structured overshirt and tapered trousers", "standing with a sketchbook and pencil"),
    ("a harbor sailing pier", "tying a rope on a mooring post", "a striped knit and deck trousers", "crouched beside the mooring post"),
    ("a quiet record shop", "selecting a vinyl album", "a denim jacket and relaxed chinos", "turning slightly with an album in hand"),
    ("a lantern-lit pedestrian lane", "walking past paper lanterns", "a tailored wool coat and soft scarf", "taking a natural mid-stride step"),
    ("a coastal bicycle workshop", "adjusting a bicycle handlebar", "a workwear shirt and canvas trousers", "leaning over the bicycle frame"),
    ("an outdoor botanical painting class", "mixing watercolor pigments", "a loose smock over everyday clothes", "seated beside a portable easel"),
    ("a tiled tea pavilion", "pouring tea into a ceramic cup", "a textured wrap jacket and straight trousers", "seated with the teapot lifted"),
    ("a desert astronomy camp", "adjusting a telescope", "a quilted vest and practical boots", "standing at the telescope mount"),
    ("a rain-sheltered flower stall", "arranging a seasonal bouquet", "a light raincoat and cotton scarf", "holding flowers close to the workbench"),
    ("an open-air dance rehearsal stage", "practicing a graceful dance step", "a fluid rehearsal outfit and soft shoes", "balanced in a gentle dance movement"),
    ("a hillside citrus orchard", "picking a ripe orange", "a breezy shirt and a woven sun hat", "stretching one arm toward a branch"),
    ("a restored cinema foyer", "studying a film program", "a sleek evening suit with subtle accessories", "standing near a velvet curtain"),
    ("a forest wooden footbridge", "pausing to listen to birds", "a soft fleece and trail shoes", "resting one hand on the bridge railing"),
)
LIGHTS = (
    ("early spring morning", "soft morning sun and cool fill light"),
    ("late summer afternoon", "warm sidelight with gentle cinematic shadows"),
    ("an overcast autumn day", "diffused skylight and rich soft materials"),
    ("a clear winter dawn", "pale rim light and warm practical highlights"),
    ("blue hour after sunset", "cool ambient light with amber practical lamps"),
)
ATTITUDES = (
    ("a relaxed warm smile", "toward the camera"),
    ("a playful half-smile", "toward the activity with a sideways glance"),
    ("a thoughtful gentle expression", "toward a distant detail in the scene"),
    ("an alert curious expression", "toward the object being handled"),
    ("an easy candid smile", "slightly away from the camera"),
    ("calm self-assurance", "toward the horizon"),
    ("a composed stylish expression", "past the camera"),
    ("a confident lively smile", "into the scene"),
    ("a quietly intriguing expression", "toward a soft off-screen light"),
)


def fresh_brief(prior: list[dict], slot: int, camera: str) -> dict[str, str]:
    used = {b.get("setting") for b in prior}
    choices = [(s, light) for s in SCENES for light in LIGHTS if f"{s[0]}, {light[0]}" not in used]
    # After 100 different settings, add a new environmental treatment; never overwrite history.
    cycle = len(prior) // (len(SCENES) * len(LIGHTS))
    scene, light = random.SystemRandom().choice(choices or [(s, l) for s in SCENES for l in LIGHTS])
    setting = f"{scene[0]}, {light[0]}"
    if not choices:
        setting += f", with a fresh seasonal installation of {['wildflowers', 'paper sculptures', 'woven fabrics', 'ceramics'][cycle % 4]}"
    expression, gaze = ATTITUDES[slot - 1]
    return {"setting": setting, "activity": scene[1], "outfit": scene[2], "pose": scene[3],
            "expression": expression, "gaze": gaze, "camera": camera, "lighting": light[1]}
