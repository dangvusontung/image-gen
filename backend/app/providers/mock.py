import asyncio
import hashlib
import json
import io
import os
import textwrap
import time
import uuid
from functools import lru_cache
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont

from app.providers.base import (
    ErrorKind,
    GeneratedImage,
    ImageProvider,
    ImageRequest,
    ModelInfo,
    ProviderError,
    Submission,
    SubmissionState,
)

ASPECT_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)


@lru_cache(maxsize=8)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def size_for_aspect(aspect_ratio: str, long_side: int = 1024) -> tuple[int, int]:
    w, h = (int(x) for x in aspect_ratio.split(":"))
    if w >= h:
        return long_side, round(long_side * h / w)
    return round(long_side * w / h), long_side


def render_placeholder(request: ImageRequest, note: str = "") -> bytes:
    width, height = size_for_aspect(request.aspect_ratio)
    digest = hashlib.sha256(f"{request.prompt}|{request.seed}".encode()).digest()
    top, bottom = (digest[0] // 2 + 60, digest[1] // 2 + 60, digest[2] // 2 + 90), (digest[3] // 3, digest[4] // 3, digest[5] // 3 + 40)
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(1, height - 1)
        draw.line([(0, y), (width, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))

    pad = width // 20
    draw.text((pad, pad), "MOCK PROVIDER", font=_font(max(18, width // 18)), fill="white")
    meta = f"{request.model} · {request.aspect_ratio} · {len(request.references)} ảnh tham chiếu"
    if note:
        meta += f" · {note}"
    draw.text((pad, pad + width // 12), meta, font=_font(max(12, width // 40)), fill=(235, 235, 235))

    body_font = _font(max(12, width // 36))
    lines = textwrap.wrap(request.prompt, width=max(20, width // max(8, width // 50)))[:8]
    y = pad + width // 6
    for line in lines:
        draw.text((pad, y), line, font=body_font, fill=(245, 245, 245))
        y += int(body_font.size * 1.35) if hasattr(body_font, "size") else 16

    refs = request.references[:8]
    if refs:
        thumb = min((width - pad * 2) // len(refs) - 8, height // 5)
        x, ty = pad, height - pad - thumb
        for ref in refs:
            try:
                with Image.open(io.BytesIO(ref.data)) as r:
                    r = r.convert("RGB")
                    r.thumbnail((thumb, thumb))
                    img.paste(r, (x, ty))
            except OSError:
                draw.rectangle([x, ty, x + thumb, ty + thumb], outline="white")
            draw.text((x, ty - 18), ref.label[:14], font=_font(12), fill="white")
            x += thumb + 8

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class MockProvider(ImageProvider):
    """Offline provider exercising the same submit→poll path as BFL.

    Test hooks via request.options["mock"]:
      "fail" → permanent error, "moderated" → moderation error,
      "transient:N" → first N submits for the same options["mock_key"] raise a safe transient error,
      "ambiguous" → submit raises an ambiguous error.
    """

    name = "mock"
    display_name = "Mock (offline)"
    data_notice = "Không gửi dữ liệu ra ngoài. Ảnh là placeholder để thử luồng."

    def __init__(self, delay_seconds: float | None = None):
        self.delay = float(os.getenv("MOCK_DELAY_SECONDS", "1.5")) if delay_seconds is None else delay_seconds
        self._tasks: dict[str, tuple[float, ImageRequest]] = {}
        self._transient_counts: dict[str, int] = {}

    supports_text = True

    @property
    def key_configured(self) -> bool:
        return True

    async def generate_text(self, prompt: str, references) -> str:
        """Nine plausible briefs in the requested JSON shape, so the flow works offline."""
        settings = ["a sunlit kitchen", "a rainy tram stop", "a rooftop garden", "a second-hand bookshop",
                    "a tide pool at dawn", "a neon arcade", "a potter's courtyard", "a mountain switchback",
                    "a lantern-lit night market"]
        # Cameras vary like a real proposal would, so angle-matching logic gets exercised.
        cameras = ["front-facing", "left three-quarter", "right profile", "over-the-shoulder", "high-angle candid",
                   "right three-quarter", "low-angle environmental", "wide full-body", "left profile"]
        framings = ["full-body", "three-quarter-body", "full-body", "three-quarter-body", "medium candid",
                    "three-quarter-body", "medium environmental", "full-body", "full-body"]
        return json.dumps([
            {
                "title": f"Mock concept {i + 1}",
                "setting": f"{place}, late afternoon",
                "activity": "a believable everyday action suited to the setting",
                "pose": "a relaxed natural stance",
                "outfit": "a simple contemporary outfit suited to the scene",
                "silhouette": "casual everyday separates",
                "expression": "a warm unforced expression",
                "gaze": "toward the activity",
                "camera": cameras[i],
                "framing": framings[i],
                "lighting": "soft directional daylight with gentle shadows",
            }
            for i, place in enumerate(settings)
        ], ensure_ascii=False)

    def models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id="mock-v1",
                display_name="Mock v1",
                max_reference_images=14,
                aspect_ratios=ASPECT_RATIOS,
                price_per_image_usd=0.0,
                price_note="Miễn phí — không gọi API",
                default=True,
            ),
            ModelInfo(
                id="mock-small-refs",
                display_name="Mock (tối đa 2 ảnh tham chiếu)",
                max_reference_images=2,
                aspect_ratios=("1:1", "3:4", "16:9"),
                price_per_image_usd=0.0,
                price_note="Dùng để thử lỗi vượt giới hạn tham chiếu",
            ),
        ]

    async def submit(self, request: ImageRequest) -> Submission:
        behavior = str(request.options.get("mock", ""))
        if behavior == "fail":
            raise ProviderError("mock_failure", "Lỗi giả lập từ mock provider")
        if behavior == "moderated":
            raise ProviderError("content_moderated", "Mock: nội dung bị chặn bởi kiểm duyệt")
        if behavior == "ambiguous":
            raise ProviderError("timeout", "Mock: hết thời gian chờ sau khi gửi", ErrorKind.AMBIGUOUS)
        if behavior.startswith("transient:"):
            key = str(request.options.get("mock_key", request.prompt))
            seen = self._transient_counts.get(key, 0)
            if seen < int(behavior.split(":", 1)[1]):
                self._transient_counts[key] = seen + 1
                raise ProviderError("rate_limited", "Mock: quá giới hạn tốc độ", ErrorKind.TRANSIENT_SAFE, retry_after=0)

        task_id = f"mock-{uuid.uuid4()}"
        self._tasks[task_id] = (time.monotonic() + self.delay, request)
        return Submission(state=SubmissionState.PENDING, provider_request_id=task_id,
                          polling_url=f"mock://{task_id}?aspect_ratio={request.aspect_ratio}")

    async def poll(self, submission: Submission) -> Submission:
        task = self._tasks.get(submission.provider_request_id or "")
        if task is None:
            # Process restarted while the task was pending: real providers keep the task; emulate that.
            ratio = parse_qs(urlparse(submission.polling_url or "").query).get("aspect_ratio", ["1:1"])[0]
            request = ImageRequest(model="mock-v1", prompt="(khôi phục sau khi khởi động lại)",
                                   aspect_ratio=ratio if ratio in ASPECT_RATIOS else "1:1")
            data = await asyncio.to_thread(render_placeholder, request, "resumed")
            return Submission(SubmissionState.READY, submission.provider_request_id, images=[GeneratedImage(data, "image/png")], actual_cost_usd=0.0)
        ready_at, request = task
        if time.monotonic() < ready_at:
            return submission
        del self._tasks[submission.provider_request_id]
        data = await asyncio.to_thread(render_placeholder, request)
        return Submission(
            SubmissionState.READY,
            submission.provider_request_id,
            images=[GeneratedImage(data, "image/png")],
            actual_cost_usd=0.0,
        )

    async def test_connection(self) -> str:
        return "Mock provider luôn sẵn sàng"
