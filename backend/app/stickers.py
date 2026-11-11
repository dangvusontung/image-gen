"""Sticker rendering and platform packaging, independent of the image provider."""
import io
import unicodedata
from collections import deque
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ARTWORK_VERSION = 2

STYLES = {
    "chibi": "Cute chibi illustration, oversized expressive head, compact body, clean bold outlines, soft pastel colors",
    "clay": "Handmade 3D clay character, soft rounded shapes, tactile matte finish, expressive cartoon proportions",
    "comic": "Bold comic illustration, confident black ink outlines, flat vibrant colors, exaggerated expressions",
    "kawaii": "Minimal kawaii illustration, simple rounded shapes, warm pastel palette, adorable expressive features",
}
DEFAULT_ITEMS = [
    {"id": "hello", "expression": "Waving hello with a big friendly smile", "caption": "Hi!", "emoji": "👋"},
    {"id": "love", "expression": "Heart eyes, hugging a large red heart", "caption": "Love you", "emoji": "❤️"},
    {"id": "laugh", "expression": "Laughing uncontrollably with tears of joy", "caption": "LOL", "emoji": "😂"},
    {"id": "sad", "expression": "Crying dramatically with big tears", "caption": "", "emoji": "😭"},
    {"id": "wow", "expression": "Amazed, wide eyes and open mouth, hands on cheeks", "caption": "WOW", "emoji": "😮"},
    {"id": "thanks", "expression": "Grateful smile with hands pressed together", "caption": "Thank you", "emoji": "🙏"},
    {"id": "yes", "expression": "Confident grin and an enthusiastic thumbs up", "caption": "YES!", "emoji": "👍"},
    {"id": "sleep", "expression": "Sleepy, wearing a nightcap and hugging a pillow", "caption": "Zzz…", "emoji": "😴"},
    {"id": "angry", "expression": "Adorably furious, puffed cheeks, crossed arms", "caption": "Nope", "emoji": "😤"},
    {"id": "party", "expression": "Celebrating with confetti and a party hat", "caption": "Yay!", "emoji": "🎉"},
    {"id": "please", "expression": "Pleading puppy eyes, hands clasped under chin", "caption": "Please?", "emoji": "🥺"},
    {"id": "coffee", "expression": "Relaxed smile holding a steaming cup of coffee", "caption": "Break time", "emoji": "☕"},
]


def concept_prompt(style: str, brief: str) -> str:
    return (
        "Create ONE character design concept from the supplied reference photos. "
        "Preserve the person's identity, face, hairstyle and distinguishing features. "
        f"Art direction: {STYLES[style]}. "
        f"Character design brief: {brief or 'A friendly expressive character, simple recognizable outfit, suitable for a consistent messaging sticker pack'}. "
        "Show the full character in a relaxed neutral pose with a friendly expression, facing forward or at a slight three-quarter angle. "
        "Keep the face, hairstyle, outfit, proportions and palette clear for future expression variations. "
        "One character only, plain light background, no text, lettering, captions, bubbles, grid or watermark."
    )


def sticker_prompt(style: str, item: dict) -> str:
    return (
        "Create ONE standalone messaging sticker, not a sticker sheet. "
        "Preserve the identity, face, hair, distinguishing features and clothing of the supplied character/photo. "
        f"Art direction: {STYLES[style]}. Expression and action: {item['expression']}. "
        "ARTWORK ONLY. Do not draw any text, letters, words, captions, speech bubbles or thought bubbles. "
        "Dialogue and bubbles will be added separately by the app using real fonts. "
        "Full subject completely inside a square canvas, generous empty margin, no cropped limbs. "
        "Add a clean white die-cut outline around the subject. "
        "Background must be perfectly flat solid pure magenta #FF00FF, with no shadows, texture, gradients or scenery. "
        "Do not use magenta anywhere in the character, clothing, props or lettering. "
        "The background will be removed automatically. No watermark, no grid, no extra characters."
    )


def artwork_matches(job_meta: dict, style: str, item: dict) -> bool:
    return (job_meta.get("artwork_version") == ARTWORK_VERSION
            and job_meta.get("style") == style
            and (job_meta.get("sticker_item") or {}).get("expression") == item["expression"])


@lru_cache(maxsize=64)
def caption_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path(__file__).with_name("fonts") / "NotoSans-Bold.ttf"), size)


@lru_cache(maxsize=128)
def text_layout(text: str, size: int, bubble: bool) -> tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    """Fit all characters by wrapping and shrinking; never truncate the user's dialogue."""
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    max_width, max_height = (390, 126) if bubble else (428, 144)
    for fitted in range(size, 9, -1):
        font = caption_font(fitted)
        lines = []
        for paragraph in unicodedata.normalize("NFC", text).split("\n"):
            line = ""
            # Character wrapping also handles long words and explicit line breaks.
            for word in paragraph.split(" "):
                candidate = f"{line} {word}" if line else word
                if draw.textlength(candidate, font=font) <= max_width:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                line = ""
                for char in word:
                    if line and draw.textlength(line + char, font=font) > max_width:
                        lines.append(line)
                        line = ""
                    line += char
            lines.append(line)
        wrapped = "\n".join(lines)
        bounds = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=4, align="center", stroke_width=3)
        if bounds[2] - bounds[0] <= max_width and bounds[3] - bounds[1] <= max_height:
            return wrapped, font, bounds
    raise ValueError("The dialogue is too long to fit. Shorten it or use fewer line breaks.")


def compose_sticker(artwork: Image.Image, item: dict) -> Image.Image:
    text = item.get("caption", "")
    if not text.strip():
        return artwork.copy()
    kind = item.get("text_style", "caption")
    bubble = kind != "caption"
    wrapped, font, bounds = text_layout(text, item.get("text_size", 48), bubble)
    pad = 22 if bubble else 10
    width, height = bounds[2] - bounds[0] + pad * 2, bounds[3] - bounds[1] + pad * 2
    center_x = max(width / 2 + 12, min(500 - width / 2, item.get("text_x", .5) * 512))
    center_y = max(height / 2 + 14, min(466 - height / 2, item.get("text_y", .84) * 512))
    left, top = round(center_x - width / 2), round(center_y - height / 2)
    canvas = Image.new("RGBA", (512, 512))
    character = artwork.crop(artwork.getchannel("A").getbbox())
    # Reserve space for dialogue so the default placement does not cover the face.
    if center_y >= 256:
        available_top, available_bottom = 16, max(110, top - 8)
    else:
        available_top, available_bottom = min(390, top + height + 38), 496
    character.thumbnail((480, available_bottom - available_top), Image.Resampling.LANCZOS)
    canvas.alpha_composite(character, ((512 - character.width) // 2, available_top + (available_bottom - available_top - character.height) // 2))
    draw = ImageDraw.Draw(canvas)
    if bubble:
        if kind == "speech":
            tail_x = round(center_x + width * .18)
            direction = -1 if center_y >= 256 else 1
            edge = top if direction == -1 else top + height
            draw.polygon([(tail_x - 16, edge - direction * 8), (tail_x + 16, edge - direction * 8), (tail_x - 12, edge + direction * 26)], fill="white", outline="#302a3b", width=3)
        else:
            direction = -1 if center_y >= 256 else 1
            edge = top if direction == -1 else top + height
            for radius, offset in ((9, 12), (5, 29)):
                cx = round(center_x + width * .18 - offset / 2)
                cy = edge + direction * offset
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill="white", outline="#302a3b", width=2)
        draw.rounded_rectangle((left, top, left + width, top + height), radius=28 if kind == "speech" else 42, fill="white", outline="#302a3b", width=3)
    color = item.get("text_color", "#302a3b")
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    stroke = "#302a3b" if sum(rgb) > 600 else "white"
    draw.multiline_text((left + pad - bounds[0], top + pad - bounds[1]), wrapped, font=font,
                        fill=color, stroke_width=(2 if sum(rgb) > 600 else 0) if bubble else 4, stroke_fill=stroke, spacing=4, align="center")
    return canvas


def sticker_image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
    width, height = image.size
    pixels = list(image.get_flattened_data())
    # Remove only magenta connected to the outside, keeping similarly colored internal details.
    pending = deque(i for i in range(width * height)
                    if i < width or i >= width * (height - 1) or i % width in (0, width - 1))
    visited = bytearray(width * height)
    while pending:
        index = pending.popleft()
        if visited[index]:
            continue
        visited[index] = 1
        r, g, b, a = pixels[index]
        if a > 0 and not (r > 150 and b > 150 and g < 140 and min(r, b) - g > 65):
            continue
        pixels[index] = (0, 0, 0, 0)
        x, y = index % width, index // width
        if x: pending.append(index - 1)
        if x < width - 1: pending.append(index + 1)
        if y: pending.append(index - width)
        if y < height - 1: pending.append(index + width)
    image.putdata(pixels)
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError("The output is empty after background removal. Regenerate this sticker.")
    if alpha.getextrema()[0] == 255:
        raise ValueError("The model did not produce the required magenta background. Regenerate this sticker.")
    image = image.crop(bounds)
    image.thumbnail((480, 480), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (512, 512))
    canvas.alpha_composite(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    return canvas


def encode_webp(image: Image.Image, limit: int) -> bytes:
    for quality in (95, 85, 75, 60, 45, 30, 15, 5):
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=quality, method=6)
        if output.tell() <= limit:
            return output.getvalue()
    raise ValueError("This sticker exceeds the platform file size limit. Regenerate with a simpler style.")
