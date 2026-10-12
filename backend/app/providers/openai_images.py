"""OpenAI GPT Image via the Images API.

Verified 2026-10-11 against the OpenAI images reference and cookbook: POST /v1/images/generations
(JSON) for text-to-image and POST /v1/images/edits (multipart, one repeated `image[]` part per
reference, up to 16) when references are supplied; "Authorization: Bearer <key>"; size is one of
a preset or a custom WIDTHxHEIGHT (multiples of 16, between 1:3 and 3:1, each edge <= 3840 and
655,360-8,294,400 pixels total); quality is low|medium|high|xhigh|max|auto, with xhigh and max on
the 2.5 models only; GPT Image always answers with base64 in data[].b64_json.

UNVERIFIED: per-image pricing is token-based and varies by quality, so no price ships here — set
OPENAI_PRICE_PER_IMAGE_USD to bring these jobs under the app's spend cap.
"""

import base64
import binascii
import math
from dataclasses import replace

import httpx

from app.config import (
    OPENAI_API_BASE,
    OPENAI_API_KEY,
    OPENAI_IMAGE_QUALITY,
    OPENAI_PRICE_PER_IMAGE_USD,
)
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
from app.providers.http_utils import error_text, retry_after_seconds, transport_error

_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9")
# gpt-image-2.5 adds xhigh and max; earlier GPT Image models stop at high.
QUALITIES = ("low", "medium", "high", "xhigh", "max", "auto")
LEGACY_QUALITIES = ("low", "medium", "high", "auto")
IMAGE_MODEL_PREFIX = "gpt-image"
# Custom sizes must be multiples of 16, between 1:3 and 3:1, each edge <= 3840,
# and 655,360 to 8,294,400 pixels in total. Aim for the pixel count of 1024x1536.
_TARGET_PIXELS = 1024 * 1536
_MIN_PIXELS, _MAX_PIXELS = 655_360, 8_294_400
_MAX_EDGE = 3840
_PRICE_NOTE = (
    "Giá tính theo token và thay đổi theo mức chất lượng — đặt OPENAI_PRICE_PER_IMAGE_USD "
    "để job này được tính vào hạn mức chi tiêu."
)

MODELS = (
    ModelInfo(
        id="gpt-image-2.5-sunburst",
        display_name="GPT Image 2.5 Sunburst",
        max_reference_images=16,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=QUALITIES,
        default_size="low",
        price_note=_PRICE_NOTE,
        status="ga",
        notes="OpenAI khuyến nghị khi cần chỉnh sửa chính xác từ ảnh tham chiếu. Tối đa 16 ảnh. "
              "Ô kích thước chọn mức chất lượng; khung hình tính theo tỉ lệ yêu cầu.",
        default=True,
    ),
    ModelInfo(
        id="gpt-image-2.5-flare",
        display_name="GPT Image 2.5 Flare",
        max_reference_images=16,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=QUALITIES,
        default_size="low",
        price_note=_PRICE_NOTE,
        status="ga",
        notes="Nhanh hơn, dùng cho ảnh thường ngày. Tối đa 16 ảnh tham chiếu.",
    ),
    ModelInfo(
        id="gpt-image-1",
        display_name="GPT Image 1",
        max_reference_images=16,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=LEGACY_QUALITIES,
        default_size="low",
        price_note=_PRICE_NOTE,
        status="deprecated",
        notes="Thế hệ trước, giữ lại cho tài khoản chưa có model 2.5.",
    ),
)


def openai_size(aspect_ratio: str) -> str:
    """Exact "WIDTHxHEIGHT" for a ratio, so 3:4 renders as 3:4 rather than the nearest preset."""
    w, h = (int(part) for part in aspect_ratio.split(":"))
    width = math.sqrt(_TARGET_PIXELS * w / h)
    height = width * h / w
    scale = min(1.0, _MAX_EDGE / max(width, height))
    pixels = (width * scale) * (height * scale)
    if pixels > _MAX_PIXELS:
        scale *= math.sqrt(_MAX_PIXELS / pixels)
    elif pixels < _MIN_PIXELS:
        scale *= math.sqrt(_MIN_PIXELS / pixels)
    align = lambda value: max(16, min(_MAX_EDGE, round(value * scale / 16) * 16))  # noqa: E731
    return f"{align(width)}x{align(height)}"


class OpenAIImageProvider(ImageProvider):
    name = "openai"
    display_name = "OpenAI GPT Image"
    catalogue_source = "openai"
    info_url = "https://platform.openai.com/docs/guides/image-generation"
    data_notice = (
        "Ảnh tham chiếu và prompt được gửi tới OpenAI. Theo chính sách API, dữ liệu không được dùng "
        "để huấn luyện trừ khi bạn bật chia sẻ; log có thể được lưu một thời gian để chống lạm dụng. "
        "Ảnh tạo ra có gắn metadata C2PA."
    )

    def __init__(self, client: httpx.AsyncClient, api_key: str = OPENAI_API_KEY,
                 base_url: str = OPENAI_API_BASE, quality: str = OPENAI_IMAGE_QUALITY,
                 price_per_image_usd: float = OPENAI_PRICE_PER_IMAGE_USD):
        self._client = client
        self._key = api_key
        self._base = base_url
        self._quality = quality if quality in QUALITIES else "low"
        self._price = price_per_image_usd
        self._live: list[ModelInfo] | None = None

    @property
    def key_configured(self) -> bool:
        return bool(self._key)

    def models(self) -> list[ModelInfo]:
        models = [replace(model, default_size=self._quality if self._quality in model.sizes else "low")
                  for model in (self._live if self._live is not None else MODELS)]
        if not self._price:
            return list(models)
        note = f"~${self._price}/ảnh theo OPENAI_PRICE_PER_IMAGE_USD"
        return [replace(m, price_per_image_usd=self._price, price_note=note) for m in models]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}"}

    def _http_error(self, resp: httpx.Response) -> ProviderError:
        message = error_text(resp, (self._key,))
        status = resp.status_code
        if status == 429:
            if "quota" in message.lower() or "billing" in message.lower():
                return ProviderError("quota_exceeded", f"Hết hạn mức OpenAI: {message}")
            return ProviderError("rate_limited", "OpenAI đang giới hạn tốc độ", ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        if status in (401, 403):
            return ProviderError("auth_failed", f"API key OpenAI không hợp lệ hoặc không có quyền: {message}")
        if status == 404:
            return ProviderError("model_not_found", f"Không tìm thấy model trên OpenAI: {message}")
        if status in (408, 504):
            return ProviderError("timeout", f"OpenAI hết thời gian xử lý ({status})", ErrorKind.AMBIGUOUS)
        if status >= 500:
            return ProviderError("provider_unavailable", f"OpenAI tạm thời lỗi ({status})", ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        if "moderation" in message.lower() or "safety" in message.lower():
            return ProviderError("content_moderated", f"OpenAI chặn nội dung: {message}")
        return ProviderError("invalid_request", f"OpenAI từ chối yêu cầu ({status}): {message}")

    def parse_response(self, body: dict) -> Submission:
        entries = body.get("data") or []
        for entry in entries[:1]:
            encoded = entry.get("b64_json")
            if not encoded:
                raise ProviderError("bad_response", "OpenAI trả về kết quả không có dữ liệu ảnh base64")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise ProviderError("bad_response", "OpenAI trả về dữ liệu ảnh không hợp lệ") from None
            request_id = str(body.get("created") or "") or None
            return Submission(SubmissionState.READY, request_id, images=[GeneratedImage(data, "image/png")])
        raise ProviderError("no_image", "OpenAI không trả về ảnh nào")

    async def submit(self, request: ImageRequest) -> Submission:
        model = self.validate(request)
        quality = request.options.get("size") or model.default_size or self._quality
        size = openai_size(request.aspect_ratio)
        timeout = httpx.Timeout(300, connect=10)
        try:
            if request.references:
                # Editing takes multipart, one repeated image[] part per reference.
                fields = {"model": model.id, "prompt": request.prompt, "size": size, "quality": quality}
                files = [
                    ("image[]", (f"reference-{index}.png", ref.data, ref.mime_type))
                    for index, ref in enumerate(request.references, start=1)
                ]
                resp = await self._client.post(f"{self._base}/images/edits", headers=self._headers(),
                                               data=fields, files=files, timeout=timeout)
            else:
                payload = {"model": model.id, "prompt": request.prompt, "size": size,
                           "quality": quality, "n": 1}
                resp = await self._client.post(f"{self._base}/images/generations",
                                               headers={**self._headers(), "Content-Type": "application/json"},
                                               json=payload, timeout=timeout)
        except httpx.HTTPError as exc:
            raise transport_error(exc) from None
        if resp.status_code != 200:
            raise self._http_error(resp)
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "OpenAI trả về phản hồi không phải JSON", ErrorKind.AMBIGUOUS) from None
        return self.parse_response(body)

    async def fetch_catalogue(self) -> list[dict[str, str]]:
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình OPENAI_API_KEY")
        try:
            resp = await self._client.get(f"{self._base}/models", headers=self._headers(), timeout=30)
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code != 200:
            raise self._http_error(resp)
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "OpenAI trả về danh sách model không phải JSON") from None
        return [{"id": str(entry.get("id") or "").strip(), "display_name": ""}
                for entry in (body.get("data") or []) if entry.get("id")]

    def apply_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        self._live = self.map_catalogue(items) or None
        return self.models()

    def map_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        """Keep the GPT Image models; everything else on the key is text or audio."""
        static = {m.id: m for m in MODELS}
        found: list[ModelInfo] = []
        for item in items:
            model_id = item["id"]
            if not model_id.lower().startswith(IMAGE_MODEL_PREFIX):
                continue
            template = static.get(model_id)
            if template is not None:
                found.append(replace(template, default=False))
            else:
                found.append(ModelInfo(
                    id=model_id, display_name=model_id, max_reference_images=16,
                    aspect_ratios=_RATIOS, default_aspect_ratio="3:4", sizes=QUALITIES,
                    default_size="low", price_note=_PRICE_NOTE, status="preview",
                    notes="Lấy từ /models. Khả năng chi tiết chưa rõ."))
        if not found:
            return []
        preferred = next((i for i, m in enumerate(found) if m.id in static), 0)
        found[preferred] = replace(found[preferred], default=True)
        return found

    async def test_connection(self) -> str:
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình OPENAI_API_KEY")
        items = await self.fetch_catalogue()
        images = [i["id"] for i in items if i["id"].lower().startswith(IMAGE_MODEL_PREFIX)]
        if not images:
            raise ProviderError("model_not_found", "Key hợp lệ nhưng tài khoản không có model GPT Image nào")
        return f"Kết nối OK — {len(images)} model ảnh: {', '.join(images[:4])}"
