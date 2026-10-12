"""Google Gemini image generation ("Nano Banana" family) via REST generateContent.

Verified 2026-10-08 against https://ai.google.dev/gemini-api/docs/generate-content/image-generation
and https://ai.google.dev/gemini-api/docs/pricing (plus models, api-errors, billing):
model IDs, generationConfig.imageConfig {aspectRatio, imageSize}, 14 total references,
"400/500 errors are not charged". Response parsing is defensive (camelCase or snake_case).
"""

import base64
import binascii
from dataclasses import replace

import httpx

from app.config import GEMINI_API_BASE, GEMINI_API_KEY
from app.providers.base import (
    ErrorKind,
    GeneratedImage,
    ImageProvider,
    ImageRequest,
    ModelInfo,
    ProviderError,
    ReferenceImage,
    Submission,
    SubmissionState,
)
from app.providers.http_utils import b64, error_text, retry_after_seconds, transport_error

_FLASH_RATIOS = ("1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9")
_PRO_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
_REF_NOTE = "Tối đa 14 ảnh tham chiếu (≤4 nhân vật khác nhau). Ảnh có watermark SynthID."
#: Text-only reasoning (concept proposals) goes to the flash tier, not an image model.
TEXT_MODEL = "gemini-3.1-flash"
# models.list returns every model on the key, including text, embedding and video.
IMAGE_HINTS = ("image", "imagen", "banana")
NOT_IMAGE_HINTS = ("embedding", "embed", "aqa", "tts", "veo", "video", "live", "learnlm")

MODELS = (
    ModelInfo(
        id="gemini-nano-banana-2.1",
        display_name="Nano Banana 2.1",
        max_reference_images=14,
        aspect_ratios=_FLASH_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1K", "2K", "4K"),
        default_size="2K",
        price_table=(("1K", 0.0336), ("2K", 0.0504), ("4K", 0.113)),
        price_per_image_usd=0.0504,
        price_note="Ảnh ra: 1K $0.0336 · 2K $0.0504 · 4K $0.113; ảnh vào ~$1.50/1M token (bảng giá 2026-10-07)",
        status="ga",
        notes=_REF_NOTE + " Google khuyến nghị cho dự án mới.",
        default=True,
    ),
    ModelInfo(
        id="gemini-3.1-flash-image",
        display_name="Nano Banana 2 (Gemini 3.1 Flash Image)",
        max_reference_images=14,
        aspect_ratios=_FLASH_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("512", "1K", "2K", "4K"),
        default_size="2K",
        price_table=(("512", 0.045), ("1K", 0.067), ("2K", 0.101), ("4K", 0.151)),
        price_per_image_usd=0.101,
        price_note="Ảnh ra: 512 $0.045 · 1K $0.067 · 2K $0.101 · 4K $0.151; ảnh vào ~$0.50/1M token",
        status="ga",
        notes=_REF_NOTE + " Đã có bản thay thế là 2.1.",
    ),
    ModelInfo(
        id="gemini-3-pro-image",
        display_name="Nano Banana Pro (Gemini 3 Pro Image)",
        max_reference_images=14,
        aspect_ratios=_PRO_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1K", "2K", "4K"),
        default_size="2K",
        price_table=(("1K", 0.134), ("2K", 0.134), ("4K", 0.24)),
        price_per_image_usd=0.134,
        price_note="Ảnh ra: 1K/2K $0.134 · 4K $0.24; ảnh vào ~$0.0011/ảnh",
        status="ga",
        notes="Chất lượng cao nhất. Tối đa 14 ảnh tham chiếu (≤5 nhân vật). Ảnh có watermark SynthID.",
    ),
)

_BLOCK_FINISH_REASONS = {
    "SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "IMAGE_PROHIBITED_CONTENT",
    "BLOCKLIST", "SPII", "RECITATION", "IMAGE_RECITATION",
}


def _get(d: dict, camel: str, snake: str):
    return d.get(camel, d.get(snake))


class GeminiProvider(ImageProvider):
    name = "gemini"
    display_name = "Google Gemini (Nano Banana)"
    info_url = "https://ai.google.dev/gemini-api/docs/image-generation"
    data_notice = (
        "Ảnh tham chiếu và prompt được gửi tới Google. Gói miễn phí: Google có thể dùng dữ liệu để cải thiện sản phẩm "
        "và người duyệt có thể xem — nên dùng key trả phí (không dùng để huấn luyện, chỉ lưu log có thời hạn để chống "
        "lạm dụng). Người dùng API phải từ 18 tuổi."
    )

    supports_text = True
    catalogue_source = "gemini"

    def __init__(self, client: httpx.AsyncClient, api_key: str = GEMINI_API_KEY, base_url: str = GEMINI_API_BASE):
        self._client = client
        self._key = api_key
        self._base = base_url
        self._live: list[ModelInfo] | None = None

    @property
    def key_configured(self) -> bool:
        return bool(self._key)

    def models(self) -> list[ModelInfo]:
        return [replace(m, default_size=m.sizes[0] if m.sizes else m.default_size)
                for m in (self._live if self._live is not None else MODELS)]

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._key, "Content-Type": "application/json"}

    def build_payload(self, request: ImageRequest, model: ModelInfo) -> dict:
        parts: list[dict] = [{"text": request.prompt}]
        for index, ref in enumerate(request.references, start=1):
            parts.append({"text": f"Image {index}: {ref.label}"})
            parts.append({"inlineData": {"mimeType": ref.mime_type, "data": b64(ref.data)}})
        image_config = {"aspectRatio": request.aspect_ratio, "imageSize": request.options.get("size") or model.default_size}
        config: dict = {"responseModalities": ["TEXT", "IMAGE"], "candidateCount": 1, "imageConfig": image_config}
        if request.seed is not None:
            config["seed"] = request.seed
        return {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}

    def _http_error(self, resp: httpx.Response) -> ProviderError:
        message = error_text(resp, (self._key,))
        status = resp.status_code
        if status == 429:
            if "quota" in message.lower() and "minute" not in message.lower():
                return ProviderError("quota_exceeded", f"Hết hạn mức Gemini: {message}")
            return ProviderError("rate_limited", "Gemini đang giới hạn tốc độ", ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        if status in (500, 503):
            # Google billing docs: 400/500 failures are not charged; 503 = overloaded, rejected.
            return ProviderError("provider_unavailable", f"Gemini tạm thời lỗi ({status})", ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        if status in (408, 504):
            return ProviderError("timeout", f"Gemini hết thời gian xử lý ({status})", ErrorKind.AMBIGUOUS)
        if status in (401, 403):
            return ProviderError("auth_failed", f"API key Gemini không hợp lệ hoặc không có quyền: {message}")
        if status == 404:
            return ProviderError("model_not_found", f"Không tìm thấy model trên Gemini: {message}")
        if status == 402:
            return ProviderError("payment_required", "Tài khoản Gemini cần bật thanh toán")
        return ProviderError("invalid_request", f"Gemini từ chối yêu cầu ({status}): {message}")

    def parse_response(self, body: dict) -> Submission:
        feedback = _get(body, "promptFeedback", "prompt_feedback") or {}
        block = _get(feedback, "blockReason", "block_reason")
        if block:
            raise ProviderError("content_moderated", f"Gemini chặn prompt/ảnh vào: {block}")

        candidates = body.get("candidates") or []
        images, texts, finish = [], [], None
        for cand in candidates[:1]:
            finish = _get(cand, "finishReason", "finish_reason")
            for part in (cand.get("content") or {}).get("parts") or []:
                if part.get("thought"):
                    continue
                inline = _get(part, "inlineData", "inline_data")
                if inline and inline.get("data"):
                    try:
                        data = base64.b64decode(inline["data"], validate=True)
                    except (binascii.Error, ValueError):
                        raise ProviderError("bad_response", "Gemini trả về dữ liệu ảnh không hợp lệ") from None
                    images.append(GeneratedImage(data, _get(inline, "mimeType", "mime_type") or "image/png"))
                elif part.get("text"):
                    texts.append(part["text"])

        if images:
            return Submission(SubmissionState.READY, _get(body, "responseId", "response_id"), images=images[:1])
        if finish in _BLOCK_FINISH_REASONS:
            raise ProviderError("content_moderated", f"Gemini chặn kết quả: {finish}")
        hint = (" — " + " ".join(texts)[:200]) if texts else ""
        raise ProviderError("no_image", f"Gemini không trả về ảnh (finishReason={finish}){hint}")

    async def submit(self, request: ImageRequest) -> Submission:
        model = self.validate(request)
        url = f"{self._base}/models/{model.id}:generateContent"
        try:
            resp = await self._client.post(
                url,
                headers=self._headers(),
                json=self.build_payload(request, model),
                timeout=httpx.Timeout(240, connect=10),
            )
        except httpx.HTTPError as exc:
            raise transport_error(exc) from None
        if resp.status_code != 200:
            raise self._http_error(resp)
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "Gemini trả về phản hồi không phải JSON", ErrorKind.AMBIGUOUS) from None
        return self.parse_response(body)

    async def fetch_catalogue(self) -> list[dict[str, str]]:
        """Every model the key can reach, via models.list. Filtering happens on apply."""
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình GEMINI_API_KEY")
        items: list[dict[str, str]] = []
        token: str | None = None
        for _ in range(10):
            params = {"pageSize": "1000", **({"pageToken": token} if token else {})}
            try:
                resp = await self._client.get(f"{self._base}/models", headers=self._headers(),
                                              params=params, timeout=30)
            except httpx.HTTPError as exc:
                raise transport_error(exc, submitted_is_billable=False) from None
            if resp.status_code != 200:
                raise self._http_error(resp)
            try:
                body = resp.json()
            except ValueError:
                raise ProviderError("bad_response", "Gemini trả về danh sách model không phải JSON") from None
            for entry in body.get("models") or []:
                name = str(entry.get("name") or "").removeprefix("models/").strip()
                if name:
                    items.append({"id": name, "display_name": str(entry.get("displayName") or "").strip()})
            token = body.get("nextPageToken")
            if not token:
                break
        return items

    def apply_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        self._live = self.map_catalogue(items) or None
        return self.models()

    def map_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        """Keep the image models, with our verified capability records where we have them."""
        static = {m.id: m for m in MODELS}
        found: list[ModelInfo] = []
        for item in items:
            model_id = item["id"]
            lowered = model_id.lower()
            if not any(hint in lowered for hint in IMAGE_HINTS) or any(bad in lowered for bad in NOT_IMAGE_HINTS):
                continue
            template = static.get(model_id)
            display = item.get("display_name") or ""
            if template is not None:
                found.append(replace(template, display_name=display or template.display_name, default=False))
            else:
                found.append(ModelInfo(
                    id=model_id, display_name=display or model_id, max_reference_images=14,
                    aspect_ratios=_PRO_RATIOS, default_aspect_ratio="3:4", sizes=("1K", "2K"),
                    default_size="2K", status="preview",
                    notes="Lấy từ models.list. Khả năng chi tiết chưa rõ — dùng mặc định thận trọng."))
        if not found:
            return []
        preferred = next((i for i, m in enumerate(found) if m.id in static), 0)
        found[preferred] = replace(found[preferred], default=True)
        return found

    async def generate_text(self, prompt: str, references: list[ReferenceImage]) -> str:
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình GEMINI_API_KEY")
        parts: list[dict] = [{"text": prompt}]
        for index, ref in enumerate(references, start=1):
            parts.append({"text": f"Image {index}: {ref.label}"})
            parts.append({"inlineData": {"mimeType": ref.mime_type, "data": b64(ref.data)}})
        payload = {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": {"responseModalities": ["TEXT"], "candidateCount": 1}}
        try:
            resp = await self._client.post(f"{self._base}/models/{TEXT_MODEL}:generateContent",
                                           headers=self._headers(), json=payload,
                                           timeout=httpx.Timeout(180, connect=10))
        except httpx.HTTPError as exc:
            raise transport_error(exc) from None
        if resp.status_code != 200:
            raise self._http_error(resp)
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "Gemini trả về phản hồi không phải JSON", ErrorKind.AMBIGUOUS) from None
        feedback = _get(body, "promptFeedback", "prompt_feedback") or {}
        if _get(feedback, "blockReason", "block_reason"):
            raise ProviderError("content_moderated", "Gemini chặn prompt/ảnh vào")
        texts = [
            part["text"]
            for cand in (body.get("candidates") or [])[:1]
            for part in (cand.get("content") or {}).get("parts") or []
            if part.get("text") and not part.get("thought")
        ]
        if not texts:
            raise ProviderError("no_text", "Gemini không trả về văn bản")
        return "\n".join(texts)

    async def test_connection(self) -> str:
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình GEMINI_API_KEY")
        model = self.default_model()
        try:
            resp = await self._client.get(f"{self._base}/models/{model.id}", headers=self._headers(), timeout=20)
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code != 200:
            raise self._http_error(resp)
        return f"Kết nối OK — truy cập được model {model.id}"
