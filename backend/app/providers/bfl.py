"""Black Forest Labs FLUX via the official async REST API.

Verified 2026-10-08 against api.bfl.ai/openapi.json and docs.bfl.ml: endpoints, x-key auth, FLUX.2
input_image..input_image_8, AsyncResponse {id, polling_url, cost}, status enum, 10-minute signed
result URLs, /v1/credits. UNVERIFIED: whether FLUX.2 accepts inline base64 (docs show URLs only) —
see BFL_IMAGE_ENCODING.
Pricing: https://bfl.ai/pricing?category=flux.2 and https://docs.bfl.ai/quick_start/pricing
"""

import math
from dataclasses import replace

import httpx

from app.config import BFL_API_BASE, BFL_API_KEY, BFL_IMAGE_ENCODING, GENERATED_MAX_SIZE
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
from app.providers.http_utils import b64, download_image, error_text, host_allowed, transport_error

_ALLOWED_API_HOSTS = ("bfl.ai",)
_FLUX2_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
_FLUX3_RATIOS = ("21:9", "2:1", "16:9", "3:2", "7:5", "4:3", "5:4", "1:1", "4:5", "3:4", "5:7", "2:3", "9:16", "1:2", "9:21")
_CREDIT_USD = 0.01
# BFL publishes no model list, but its OpenAPI spec documents one POST path per model.
_OPENAPI_PATH = "/openapi.json"
# Only the FLUX.2 and FLUX 3 families use the request shapes build_payload produces.
SUPPORTED_FAMILIES = ("flux-2-", "flux-3-")

MODELS = (
    ModelInfo(
        id="flux-2-pro",
        display_name="FLUX.2 [pro]",
        max_reference_images=8,
        aspect_ratios=_FLUX2_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1MP", "2MP", "4MP"),
        default_size="1MP",
        price_per_image_usd=0.045,
        price_note="Chỉnh sửa từ $0.045/ảnh, tăng theo megapixel; chi phí thực lấy từ phản hồi API",
        status="ga",
        notes="Phiên bản cố định (pinned). Tối đa 8 ảnh tham chiếu. BFL khuyến nghị FLUX.2 cho giữ nhân vật.",
        default=True,
    ),
    ModelInfo(
        id="flux-2-max",
        display_name="FLUX.2 [max]",
        max_reference_images=8,
        aspect_ratios=_FLUX2_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1MP", "2MP", "4MP"),
        default_size="1MP",
        price_per_image_usd=0.07,
        price_note="Từ $0.07/ảnh, tăng theo megapixel; chi phí thực lấy từ phản hồi API",
        status="ga",
        notes="Chất lượng cao nhất của FLUX.2. Tối đa 8 ảnh tham chiếu.",
    ),
    ModelInfo(
        id="flux-3-image",
        display_name="FLUX 3 Image",
        max_reference_images=10,
        aspect_ratios=_FLUX3_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("768sq", "1k", "1.5k", "2k", "4k"),
        default_size="1k",
        price_table=(("768sq", 0.041), ("1k", 0.048), ("2k", 0.10), ("4k", 0.607)),
        price_per_image_usd=0.048,
        price_note="768sq $0.041 · 1k $0.048 · 2k $0.10 · 4k $0.607",
        status="preview",
        notes="Tối đa 10 ảnh tham chiếu. Tài liệu chưa ghi GA/preview. Luôn tắt grounding (tìm kiếm web).",
    ),
)

_PENDING = {"Pending", "Reasoning", "Generating"}
_MODERATED = {"Request Moderated", "Content Moderated"}


def flux2_dimensions(aspect_ratio: str, megapixels: float) -> tuple[int, int]:
    w, h = (int(x) for x in aspect_ratio.split(":"))
    pixels = megapixels * 1_000_000
    width = math.sqrt(pixels * w / h)
    # Multiples of 32 satisfy either a 16- or 32-pixel alignment requirement.
    return max(64, int(width // 32) * 32), max(64, int((width * h / w) // 32) * 32)


class BflProvider(ImageProvider):
    name = "bfl"
    display_name = "Black Forest Labs FLUX"
    catalogue_source = "bfl"
    info_url = "https://docs.bfl.ai"
    data_notice = (
        "Ảnh tham chiếu và prompt được gửi tới Black Forest Labs. Theo chính sách bảo mật (2026-08-01), dữ liệu vào/ra "
        "có thể được dùng để huấn luyện — có thể từ chối qua email privacy@blackforestlabs.ai (tiêu đề "
        "\"Training Opt Out\"). Thời gian lưu không công bố cụ thể."
    )

    def __init__(self, client: httpx.AsyncClient, api_key: str = BFL_API_KEY, base_url: str = BFL_API_BASE,
                 image_encoding: str = BFL_IMAGE_ENCODING):
        self._client = client
        self._key = api_key
        self._base = base_url
        self._encoding = image_encoding
        self._live: list[ModelInfo] | None = None

    @property
    def key_configured(self) -> bool:
        return bool(self._key)

    def models(self) -> list[ModelInfo]:
        return [replace(m, default_size=m.sizes[0] if m.sizes else m.default_size)
                for m in (self._live if self._live is not None else MODELS)]

    async def fetch_catalogue(self) -> list[dict[str, str]]:
        """BFL has no models endpoint, so read the model paths out of its OpenAPI spec."""
        url = f"{self._base}{_OPENAPI_PATH}"
        try:
            resp = await self._client.get(url, timeout=30)
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code != 200:
            raise ProviderError("catalogue_unsupported",
                                f"Không đọc được danh sách model của BFL ({resp.status_code})")
        try:
            spec = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "BFL trả về openapi.json không hợp lệ") from None
        items: list[dict[str, str]] = []
        for path, methods in (spec.get("paths") or {}).items():
            parts = path.strip("/").split("/")
            # One POST path per model, directly under /v1 — /v1/flux-tools/* are editing utilities.
            if len(parts) != 2 or parts[0] != "v1" or "post" not in {k.lower() for k in methods}:
                continue
            summary = str((methods.get("post") or {}).get("summary") or "").strip()
            items.append({"id": parts[1], "display_name": summary})
        return items

    def apply_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        self._live = self.map_catalogue(items) or None
        return self.models()

    def map_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        """Keep the families this adapter can actually build requests for."""
        static = {m.id: m for m in MODELS}
        found: list[ModelInfo] = []
        for item in items:
            model_id = item["id"]
            if not model_id.startswith(SUPPORTED_FAMILIES) or "video" in model_id:
                continue
            template = static.get(model_id)
            display = item.get("display_name") or ""
            if template is not None:
                found.append(replace(template, display_name=display or template.display_name, default=False))
            else:
                is_flux3 = model_id.startswith("flux-3-")
                found.append(ModelInfo(
                    id=model_id, display_name=display or model_id, max_reference_images=8,
                    aspect_ratios=_FLUX3_RATIOS if is_flux3 else _FLUX2_RATIOS,
                    default_aspect_ratio="3:4",
                    sizes=("1k", "2k") if is_flux3 else ("1MP", "2MP", "4MP"),
                    default_size="1k" if is_flux3 else "1MP",
                    status="preview",
                    notes="Lấy từ openapi.json. Giá và giới hạn chưa rõ — chi phí thực lấy từ phản hồi API."))
        if not found:
            return []
        preferred = next((i for i, m in enumerate(found) if m.id in static), 0)
        found[preferred] = replace(found[preferred], default=True)
        return found

    def _headers(self) -> dict[str, str]:
        return {"x-key": self._key, "accept": "application/json", "Content-Type": "application/json"}

    def estimate_request_cost_usd(self, model, size, reference_sizes):
        if model.id == "flux-3-image":
            return self.estimate_cost_usd(model, size)
        # Official FLUX.2 rates, with conservative MP rounding for each normalized reference.
        first, additional, reference = (0.03, 0.015, 0.015) if model.id == "flux-2-pro" else (0.07, 0.03, 0.03)
        output_mp = int((size or model.default_size).removesuffix("MP"))
        input_mp = 0
        for width, height in reference_sizes:
            scale = min(1, 2048 / max(width, height))
            input_mp += max(1, math.ceil(math.ceil(width * scale) * math.ceil(height * scale) / 1_000_000))
        return round(first + additional * max(0, output_mp - 1) + reference * input_mp, 6)

    def _encode(self, ref: ReferenceImage) -> str:
        if self._encoding == "data_url":
            return f"data:{ref.mime_type};base64,{b64(ref.data)}"
        return b64(ref.data)

    def build_payload(self, request: ImageRequest, model: ModelInfo) -> dict:
        size = request.options.get("size") or model.default_size
        safety = int(request.options.get("safety_tolerance", 2))
        prompt = request.prompt
        if request.references:
            prompt += "\nReference image roles (in input order):\n" + "\n".join(
                f"Image {index}: {ref.label}" for index, ref in enumerate(request.references, start=1)
            )
        if model.id == "flux-3-image":
            payload: dict = {
                "prompt": prompt,
                "aspect_ratio": request.aspect_ratio,
                "resolution": size,
                "safety_tolerance": min(safety, 4),
                "grounding": False,
            }
            if request.references:
                payload["images"] = [self._encode(r) for r in request.references]
            return payload

        width, height = flux2_dimensions(request.aspect_ratio, float(size.removesuffix("MP")))
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "output_format": "png",
            "safety_tolerance": min(safety, 5),
            # Prompts are curated templates; don't let the API rewrite them.
            "disable_pup": True,
        }
        if request.seed is not None:
            payload["seed"] = request.seed
        for index, ref in enumerate(request.references, start=1):
            payload["input_image" if index == 1 else f"input_image_{index}"] = self._encode(ref)
        return payload

    def _http_error(self, resp: httpx.Response, *, during_submit: bool) -> ProviderError:
        status, message = resp.status_code, error_text(resp, (self._key,))
        if status == 402:
            return ProviderError("insufficient_credits", "Tài khoản BFL hết credits")
        if status in (401, 403):
            return ProviderError("auth_failed", f"API key BFL không hợp lệ hoặc thiếu quyền: {message}")
        if status in (400, 422):
            return ProviderError("invalid_request", f"BFL từ chối tham số ({status}): {message}")
        if status == 429:
            return ProviderError("rate_limited", "BFL giới hạn tốc độ/số tác vụ đồng thời", ErrorKind.TRANSIENT_SAFE)
        if status == 503:
            return ProviderError("provider_unavailable", "BFL tạm thời không khả dụng", ErrorKind.TRANSIENT_SAFE)
        kind = ErrorKind.AMBIGUOUS if during_submit else ErrorKind.TRANSIENT_SAFE
        return ProviderError("provider_error", f"BFL lỗi máy chủ ({status}): {message}", kind)

    async def submit(self, request: ImageRequest) -> Submission:
        model = self.validate(request)
        try:
            resp = await self._client.post(
                f"{self._base}/v1/{model.id}",
                headers=self._headers(),
                json=self.build_payload(request, model),
                timeout=httpx.Timeout(120, connect=10),
            )
        except httpx.HTTPError as exc:
            raise transport_error(exc) from None
        if resp.status_code != 200:
            raise self._http_error(resp, during_submit=True)
        try:
            body = resp.json()
            task_id, polling_url = body["id"], body["polling_url"]
        except (ValueError, KeyError, TypeError):
            raise ProviderError("bad_response", "BFL trả về phản hồi không hợp lệ", ErrorKind.AMBIGUOUS) from None
        if not host_allowed(polling_url, _ALLOWED_API_HOSTS):
            raise ProviderError("bad_response", "polling_url không thuộc domain BFL — từ chối gửi API key tới đó")
        cost = body.get("cost")
        return Submission(
            SubmissionState.PENDING,
            provider_request_id=task_id,
            polling_url=polling_url,
            actual_cost_usd=cost * _CREDIT_USD if isinstance(cost, (int, float)) else None,
        )

    async def poll(self, submission: Submission) -> Submission:
        url = submission.polling_url or ""
        if not host_allowed(url, _ALLOWED_API_HOSTS):
            raise ProviderError("bad_response", "polling_url không thuộc domain BFL")
        try:
            resp = await self._client.get(url, headers=self._headers(), timeout=httpx.Timeout(30, connect=10))
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code != 200:
            raise self._http_error(resp, during_submit=False)
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "BFL trả về phản hồi không phải JSON", ErrorKind.TRANSIENT_SAFE) from None

        status = body.get("status")
        cost = body.get("cost")
        if isinstance(cost, (int, float)):
            submission.actual_cost_usd = cost * _CREDIT_USD
        if status in _PENDING:
            return submission
        if status == "Ready":
            sample = (body.get("result") or {}).get("sample")
            if not sample or not sample.startswith("https://"):
                raise ProviderError("bad_response", "BFL báo Ready nhưng không có URL ảnh")
            data, mime = await download_image(self._client, sample, GENERATED_MAX_SIZE)
            return Submission(
                SubmissionState.READY,
                submission.provider_request_id,
                submission.polling_url,
                images=[GeneratedImage(data, mime)],
                actual_cost_usd=submission.actual_cost_usd,
            )
        if status in _MODERATED:
            reasons = (body.get("details") or {}).get("Moderation Reasons") if isinstance(body.get("details"), dict) else None
            suffix = f": {', '.join(map(str, reasons))}" if reasons else ""
            raise ProviderError("content_moderated", f"BFL kiểm duyệt chặn ({status}){suffix}")
        if status == "Task not found":
            raise ProviderError("task_not_found", "BFL không còn tác vụ này (có thể đã hết hạn)")
        raise ProviderError("provider_error", f"BFL báo lỗi tác vụ: {status}")

    async def test_connection(self) -> str:
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình BFL_API_KEY")
        try:
            resp = await self._client.get(f"{self._base}/v1/credits", headers=self._headers(), timeout=20)
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code != 200:
            raise self._http_error(resp, during_submit=False)
        credits = resp.json().get("credits")
        return f"Kết nối OK — còn {credits} credits (~${credits * _CREDIT_USD:.2f})" if isinstance(credits, (int, float)) else "Kết nối OK"
