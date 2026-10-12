"""BytePlus ModelArk (Seedream) image generation via the OpenAI-compatible REST API.

Endpoint, auth and request/response shape cross-checked 2026-10-09 against
https://docs.byteplus.com/en/docs/ModelArk/image-generation-api (JS-rendered; read via
mirrors), https://docs.apiyi.com/en/api-capabilities/seedream-image/overview and the
Seedream 4.5 walkthrough at https://www.datacamp.com/tutorial/seedream-4-5:
POST {base}/images/generations, "Authorization: Bearer <key>", synchronous (no polling),
`image` as an array of up to 10 public URLs or data URIs, `size` as a "1K".."4K" tier or
exact "WIDTHxHEIGHT", response {created, data:[{url|b64_json}], usage}.

GET {base}/models is the OpenAI-compatible model listing and takes the same Bearer key; it is
documented on the sibling Volcengine Ark deployment (ark.cn-beijing.volces.com/api/v3/models)
and used here for the connection test. Account-level model activation and custom inference
endpoints live on a separate control-plane API (Action=ListModelActivations / ListEndpoints,
Version=2024-01-01) that is HMAC-SHA256 signed with an AccessKey/SecretKey pair, not this key.

UNVERIFIED: per-image pricing is not published in the pages above, so no price ships here —
set ARK_PRICE_PER_IMAGE_USD to your contract price to bring these jobs under the app's
spend cap. `sequential_image_generation` and `stream` are never sent (both 400 on the
5.0 pro/flash models, and this app always wants exactly one image per job).
"""

import base64
import binascii
import json
import logging
import math
from dataclasses import replace

import httpx

from app.config import (
    ARK_ACCESS_KEY,
    ARK_API_BASE,
    ARK_API_KEY,
    ARK_CONTROL_HOST,
    ARK_PRICE_PER_IMAGE_USD,
    ARK_REGION,
    ARK_SECRET_KEY,
    ARK_TEXT_MODEL,
    ARK_WATERMARK,
)
from app.logging_setup import redact
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
from app.providers.byteplus_sign import action_query, sign_request
from app.providers.http_utils import error_text, retry_after_seconds, transport_error

log = logging.getLogger("app.providers")

CONTROL_SERVICE = "ark"
CONTROL_VERSION = "2024-01-01"
CONTROL_PAGE_SIZE = 100
CONTROL_MAX_PAGES = 10
# The control plane lists every foundation model on the account, LLMs included.
IMAGE_MODEL_PREFIXES = ("seedream", "seededit", "dola-seedream", "dola-seededit")
# Chat families ModelArk serves alongside the image models; used to auto-pick a text model.
TEXT_MODEL_PREFIXES = ("doubao", "skylark", "seed-")
# Same families also cover embeddings, speech and video, which cannot answer a prompt.
NOT_CHAT_HINTS = ("embedding", "embed", "rerank", "tokeniz", "asr", "tts", "voice", "speech",
                  "audio", "video", "seedance", "seedream", "seededit", "image")
#: Vision-capable chat models can read the master image; prefer them when one is available.
VISION_HINTS = ("vision", "-vl", "vlm", "multimodal", "omni")

_RATIOS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")
# Size tiers name the square-equivalent long side; exact pixels are computed per aspect ratio.
_TIER_PIXELS = {"1K": 1024, "1.5K": 1536, "2K": 2048, "3K": 3072, "4K": 4096}
_MIN_DIMENSION, _MAX_DIMENSION = 512, 4096
_PRICE_NOTE = (
    "Giá mỗi ảnh chưa được công bố trong tài liệu đã đọc — đặt ARK_PRICE_PER_IMAGE_USD "
    "theo hợp đồng của bạn để job này được tính vào hạn mức chi tiêu."
)

# Documented total-pixel ceilings; the request is scaled down to fit rather than rejected.
MAX_PIXELS = {
    "seedream-5-0-pro-260628": 4_190_000,
    "seedream-5-0-flash-260915": 4_620_000,
}
# Only the 5.0 family documents PNG output; the rest return JPEG.
_PNG_MODELS = {"seedream-5-0-pro-260628", "seedream-5-0-flash-260915", "seedream-5-0-260128"}

MODELS = (
    ModelInfo(
        id="seedream-4-5-251128",
        display_name="Seedream 4.5",
        max_reference_images=10,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1K", "2K", "4K"),
        default_size="2K",
        price_note=_PRICE_NOTE,
        status="ga",
        notes="Tối đa 10 ảnh tham chiếu. Đồng bộ, không cần chờ poll. Chỉ xuất JPEG.",
        default=True,
    ),
    ModelInfo(
        id="seedream-5-0-pro-260628",
        display_name="Seedream 5.0 pro",
        max_reference_images=10,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1K", "2K"),
        default_size="2K",
        price_note=_PRICE_NOTE,
        status="ga",
        notes="Chất lượng cao nhất, chậm (~2 phút/ảnh). Giới hạn ~4.19M điểm ảnh.",
    ),
    ModelInfo(
        id="seedream-5-0-flash-260915",
        display_name="Seedream 5.0 flash",
        max_reference_images=10,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("1K", "1.5K", "2K"),
        default_size="2K",
        price_note=_PRICE_NOTE,
        status="ga",
        notes="Nhanh nhất. Ảnh tham chiếu không tính phí. Mặc định của nhà cung cấp có watermark.",
    ),
    ModelInfo(
        id="seedream-4-0-250828",
        display_name="Seedream 4.0",
        max_reference_images=10,
        aspect_ratios=_RATIOS,
        default_aspect_ratio="3:4",
        sizes=("2K", "4K"),
        default_size="2K",
        price_note=_PRICE_NOTE,
        status="deprecated",
        notes="Thế hệ cũ, giữ lại để so sánh. Chỉ xuất JPEG.",
    ),
)


# BytePlus also exposes the pro model under its dola-prefixed invocation ID.
MODELS += (replace(
    next(model for model in MODELS if model.id == "seedream-5-0-pro-260628"),
    id="dola-seedream-5-0-pro-260628",
    display_name="Seedream 5.0 pro (dola)",
),)
MAX_PIXELS["dola-seedream-5-0-pro-260628"] = MAX_PIXELS["seedream-5-0-pro-260628"]
_PNG_MODELS.add("dola-seedream-5-0-pro-260628")

#: Control-plane "Name" -> the static record whose capabilities that family uses.
FAMILIES = {
    "seedream-4-5": "seedream-4-5-251128",
    "seedream-5-0-pro": "seedream-5-0-pro-260628",
    "dola-seedream-5-0-pro": "dola-seedream-5-0-pro-260628",
    "seedream-5-0-flash": "seedream-5-0-flash-260915",
    "seedream-4-0": "seedream-4-0-250828",
}
_UNKNOWN_NOTE = ("Lấy từ ListModelActivations. Khả năng chi tiết chưa rõ — dùng mặc định thận trọng "
                 "(tối đa 10 ảnh tham chiếu, 1K/2K).")


def seedream_size(aspect_ratio: str, tier: str, max_pixels: int | None = None) -> str:
    """Exact "WIDTHxHEIGHT" for a tier, so portrait jobs are not squared off to a preset."""
    w, h = (int(x) for x in aspect_ratio.split(":"))
    long_side = _TIER_PIXELS[tier]
    budget = long_side * long_side
    if max_pixels is not None:
        budget = min(budget, max_pixels)
    width = math.sqrt(budget * w / h)
    height = width * h / w
    # Keep the longest edge inside the documented 4096 limit before aligning.
    scale = min(1.0, _MAX_DIMENSION / max(width, height))
    align = lambda v: max(_MIN_DIMENSION, min(_MAX_DIMENSION, int(v * scale) // 16 * 16))  # noqa: E731
    return f"{align(width)}x{align(height)}"


def _sniff_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class ModelArkProvider(ImageProvider):
    name = "modelark"
    display_name = "BytePlus ModelArk (Seedream)"
    catalogue_source = "modelark"
    supports_text = True
    info_url = "https://docs.byteplus.com/en/docs/ModelArk/image-generation-api"
    data_notice = (
        "Ảnh tham chiếu và prompt được gửi tới BytePlus (ByteDance). Hãy tự kiểm tra điều khoản ModelArk về "
        "lưu trữ và sử dụng dữ liệu cho khu vực của bạn trước khi gửi ảnh người thật. Ứng dụng luôn gửi "
        "watermark=false; nhà cung cấp vẫn có thể áp dụng chính sách riêng."
    )

    def __init__(self, client: httpx.AsyncClient, api_key: str = ARK_API_KEY, base_url: str = ARK_API_BASE,
                 price_per_image_usd: float = ARK_PRICE_PER_IMAGE_USD, watermark: bool = ARK_WATERMARK,
                 access_key: str = ARK_ACCESS_KEY, secret_key: str = ARK_SECRET_KEY,
                 control_host: str = ARK_CONTROL_HOST, region: str = ARK_REGION,
                 text_model: str = ARK_TEXT_MODEL):
        self._client = client
        self._key = api_key
        self._base = base_url
        self._price = price_per_image_usd
        self._watermark = watermark
        self._access_key = access_key
        self._secret_key = secret_key
        self._control_host = control_host
        self._region = region
        self._live: list[ModelInfo] | None = None
        self._text_model = text_model
        self._discovered_text_model: str | None = None

    @property
    def key_configured(self) -> bool:
        return bool(self._key)

    def models(self) -> list[ModelInfo]:
        return self._priced([replace(m, default_size=m.sizes[0] if m.sizes else m.default_size)
                             for m in (self._live if self._live is not None else MODELS)])

    def _priced(self, models: list[ModelInfo]) -> list[ModelInfo]:
        if not self._price:
            return list(models)
        note = f"~${self._price}/ảnh theo ARK_PRICE_PER_IMAGE_USD"
        return [replace(m, price_per_image_usd=self._price, price_note=note) for m in models]

    @property
    def control_plane_configured(self) -> bool:
        return bool(self._access_key and self._secret_key)

    def apply_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        """Adopt a fetched catalogue; an empty list reverts models() to the built-in records."""
        self._live = self.map_catalogue(items) or None
        return self.models()

    def map_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        """Fetched ids -> ModelInfo, keeping our verified capability records for known families."""
        static = {m.id: m for m in MODELS}
        found: list[ModelInfo] = []
        for item in items:
            model_id = (item.get("id") or "").strip()
            if not model_id.lower().startswith(IMAGE_MODEL_PREFIXES):
                continue
            display = (item.get("display_name") or "").strip()
            family = next((f for f in FAMILIES if model_id == f or model_id.startswith(f + "-")), None)
            template = static.get(FAMILIES.get(family, "")) if family else None
            if template is not None:
                found.append(replace(template, id=model_id, display_name=display or template.display_name,
                                     default=False))
            else:
                found.append(ModelInfo(
                    id=model_id, display_name=display or model_id, max_reference_images=10,
                    aspect_ratios=_RATIOS, default_aspect_ratio="3:4", sizes=("1K", "2K"),
                    default_size="2K", price_note=_PRICE_NOTE, status="preview", notes=_UNKNOWN_NOTE))
        if not found:
            return []
        # Keep a stable default: the first family whose capabilities we actually know.
        preferred = next((i for i, m in enumerate(found) if m.id in static), 0)
        found[preferred] = replace(found[preferred], default=True)
        return found

    async def fetch_catalogue(self) -> list[dict[str, str]]:
        """List models activated for this account, using signed control-plane credentials."""
        if not self.control_plane_configured:
            raise ProviderError(
                "catalogue_unsupported",
                "Thêm ARK_ACCESS_KEY và ARK_SECRET_KEY để lấy model đã kích hoạt qua ListModelActivations.")
        items = [
            {"id": item["FoundationModelName"].strip(),
             "display_name": (item.get("DisplayName") or "").strip()}
            for item in await self.list_model_activations()
            if isinstance(item.get("FoundationModelName"), str)
            and item["FoundationModelName"].strip()
            and item.get("State") == "Available"
            and not item.get("IsDeprecated", False)
        ]
        if not any(item["id"].lower().startswith(IMAGE_MODEL_PREFIXES) for item in items):
            raise ProviderError("no_activated_image_models",
                                "Tài khoản chưa có model Seedream/SeedEdit nào ở trạng thái Available.")
        return items

    async def list_inference_models(self) -> list[dict[str, str]]:
        """GET {base}/models — the OpenAI-compatible listing, using the Bearer inference key."""
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình ARK_API_KEY")
        try:
            resp = await self._client.get(f"{self._base}/models", headers=self._headers(), timeout=30)
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code in (404, 405):
            raise ProviderError(
                "catalogue_unsupported",
                "ModelArk không có endpoint /models với key này. Thêm ARK_ACCESS_KEY và ARK_SECRET_KEY "
                "để lấy danh sách qua control plane.")
        if resp.status_code != 200:
            raise self._http_error(resp)
        try:
            payload = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "ModelArk trả về danh sách model không phải JSON") from None
        entries = payload.get("data") if isinstance(payload, dict) else payload
        return [{"id": str(e.get("id") or "").strip(), "display_name": str(e.get("display_name") or "").strip()}
                for e in (entries or []) if isinstance(e, dict) and e.get("id")]

    async def list_model_activations(self) -> list[dict]:
        """Every page of Action=ListModelActivations from the signed control-plane API."""
        items: list[dict] = []
        for page in range(1, CONTROL_MAX_PAGES + 1):
            body = json.dumps({
                "PageNumber": page, "PageSize": CONTROL_PAGE_SIZE,
                "Filter": {"States": ["Available"], "IncludeDeprecatedModels": False},
            }).encode()
            query = action_query("ListModelActivations", CONTROL_VERSION)
            headers, _ = sign_request(
                method="POST", host=self._control_host, service=CONTROL_SERVICE, region=self._region,
                query=query, body=body, content_type="application/json",
                access_key=self._access_key, secret_key=self._secret_key,
            )
            try:
                resp = await self._client.post(f"https://{self._control_host}/?{query}", headers=headers,
                                               content=body, timeout=httpx.Timeout(30, connect=10))
            except httpx.HTTPError as exc:
                raise transport_error(exc, submitted_is_billable=False) from None
            if resp.status_code != 200:
                raise self._control_error(resp)
            try:
                payload = resp.json()
            except ValueError:
                raise ProviderError("bad_response", "ModelArk control plane trả về phản hồi không phải JSON") from None
            error = (payload.get("ResponseMetadata") or {}).get("Error")
            if error:
                message = redact(str(error.get("Message") or error), (self._secret_key,))[:300]
                code = str(error.get("Code") or "control_plane_error")
                if "auth" in code.lower() or "signature" in code.lower() or "credential" in code.lower():
                    raise ProviderError("auth_failed", f"ModelArk từ chối chữ ký control plane: {message}")
                raise ProviderError("control_plane_error", f"ModelArk ListModelActivations lỗi ({code}): {message}")
            result = payload.get("Result") or payload
            batch = result.get("Items") or []
            items.extend(batch)
            total = result.get("TotalCount")
            if len(batch) < CONTROL_PAGE_SIZE or (isinstance(total, int) and len(items) >= total):
                break
        else:
            raise ProviderError("catalogue_too_large", "Danh sách model vượt giới hạn phân trang; chưa lưu kết quả thiếu.")
        return items

    def _control_error(self, resp: httpx.Response) -> ProviderError:
        message = error_text(resp, (self._secret_key, self._access_key))
        if resp.status_code in (401, 403):
            return ProviderError("auth_failed", f"ARK_ACCESS_KEY/ARK_SECRET_KEY không hợp lệ: {message}")
        if resp.status_code >= 500:
            return ProviderError("provider_unavailable", f"ModelArk control plane lỗi ({resp.status_code})",
                                 ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        return ProviderError("control_plane_error", f"ModelArk control plane từ chối ({resp.status_code}): {message}")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    def build_payload(self, request: ImageRequest, model: ModelInfo) -> dict:
        tier = request.options.get("size") or model.default_size or "2K"
        payload: dict = {
            "model": model.id,
            "prompt": request.prompt,
            "size": seedream_size(request.aspect_ratio, tier, MAX_PIXELS.get(model.id)),
            "response_format": "b64_json",
            "watermark": self._watermark,
        }
        if model.id in _PNG_MODELS:
            payload["output_format"] = "png"
        if request.references:
            # Data URIs keep the reference bytes in-band; no public hosting required.
            payload["image"] = [
                f"data:{ref.mime_type};base64,{base64.b64encode(ref.data).decode('ascii')}"
                for ref in request.references
            ]
        if request.seed is not None:
            payload["seed"] = request.seed
        return payload

    def _http_error(self, resp: httpx.Response) -> ProviderError:
        message = error_text(resp, (self._key,))
        status = resp.status_code
        lowered = message.lower()
        if status == 429:
            if any(word in lowered for word in ("balance", "quota", "insufficient")):
                return ProviderError("quota_exceeded", f"Tài khoản ModelArk không đủ hạn mức: {message}")
            return ProviderError("rate_limited", "ModelArk đang giới hạn tốc độ", ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        if status == 403:
            # Documented as the moderation rejection status; permission errors read differently.
            if any(word in lowered for word in ("moderat", "sensitive", "policy", "risk")):
                return ProviderError("content_moderated", f"ModelArk chặn nội dung: {message}")
            return ProviderError("auth_failed", f"ModelArk từ chối quyền truy cập: {message}")
        if status == 401:
            return ProviderError("auth_failed", f"API key ModelArk không hợp lệ: {message}")
        if status == 404:
            return ProviderError("model_not_found", f"Không tìm thấy model trên ModelArk: {message}")
        if status in (408, 504):
            return ProviderError("timeout", f"ModelArk hết thời gian xử lý ({status})", ErrorKind.AMBIGUOUS)
        if status >= 500:
            return ProviderError("provider_unavailable", f"ModelArk tạm thời lỗi ({status})", ErrorKind.TRANSIENT_SAFE, retry_after_seconds(resp))
        return ProviderError("invalid_request", f"ModelArk từ chối yêu cầu ({status}): {message}")

    def parse_response(self, body: dict) -> Submission:
        entries = body.get("data") or []
        for entry in entries[:1]:
            encoded = entry.get("b64_json")
            if not encoded:
                raise ProviderError("bad_response", "ModelArk trả về kết quả không có dữ liệu ảnh base64")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise ProviderError("bad_response", "ModelArk trả về dữ liệu ảnh không hợp lệ") from None
            request_id = body.get("id") or (str(body["created"]) if body.get("created") else None)
            return Submission(SubmissionState.READY, request_id, images=[GeneratedImage(data, _sniff_mime(data))])
        raise ProviderError("no_image", "ModelArk không trả về ảnh nào")

    async def submit(self, request: ImageRequest) -> Submission:
        model = self.validate(request)
        try:
            resp = await self._client.post(
                f"{self._base}/images/generations",
                headers=self._headers(),
                json=self.build_payload(request, model),
                # 5.0 pro needs ~2 minutes per image; the docs recommend at least 240s.
                timeout=httpx.Timeout(300, connect=10),
            )
        except httpx.HTTPError as exc:
            raise transport_error(exc) from None
        if resp.status_code != 200:
            raise self._http_error(resp)
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "ModelArk trả về phản hồi không phải JSON", ErrorKind.AMBIGUOUS) from None
        return self.parse_response(body)

    async def resolve_text_model(self) -> str:
        """The configured chat model, else the best chat model the account actually lists."""
        if self._text_model:
            return self._text_model
        if self._discovered_text_model:
            return self._discovered_text_model
        try:
            items = await self.list_inference_models()
        except ProviderError as exc:
            raise ProviderError(
                "text_model_unknown",
                f"Chưa biết model văn bản của ModelArk ({exc.code}). Đặt ARK_TEXT_MODEL trong .env.") from None
        chats = [
            i["id"] for i in items
            if i["id"].lower().startswith(TEXT_MODEL_PREFIXES)
            # Those families also cover embedding/speech/video models, which cannot answer a prompt.
            and not any(bad in i["id"].lower() for bad in NOT_CHAT_HINTS)
        ]
        if not chats:
            listed = ", ".join(i["id"] for i in items[:12]) or "không có model nào"
            raise ProviderError(
                "text_model_unknown",
                "Tài khoản ModelArk không có model chat nào để đề xuất concept. "
                f"Đặt ARK_TEXT_MODEL trong .env. Model đang có: {listed}")
        # A vision model can read the master image; otherwise fall back to the first chat model.
        self._discovered_text_model = next(
            (c for c in chats if any(hint in c.lower() for hint in VISION_HINTS)), chats[0])
        log.info("modelark: using %s for concept proposals", self._discovered_text_model)
        return self._discovered_text_model

    async def _chat_candidates(self) -> list[str]:
        """Chat model ids on the account, for error messages. Never raises."""
        try:
            items = await self.list_inference_models()
        except ProviderError:
            return []
        return [i["id"] for i in items
                if i["id"].lower().startswith(TEXT_MODEL_PREFIXES)
                and not any(bad in i["id"].lower() for bad in NOT_CHAT_HINTS)]

    async def generate_text(self, prompt: str, references: list[ReferenceImage]) -> str:
        """Concept proposals via the OpenAI-compatible chat endpoint, with the master as input."""
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình ARK_API_KEY")
        model = await self.resolve_text_model()
        content: list[dict] = [{"type": "text", "text": prompt}]
        for ref in references:
            data_url = f"data:{ref.mime_type};base64,{base64.b64encode(ref.data).decode('ascii')}"
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        payload = {"model": model, "messages": [{"role": "user", "content": content}]}
        try:
            resp = await self._client.post(f"{self._base}/chat/completions", headers=self._headers(),
                                           json=payload, timeout=httpx.Timeout(180, connect=10))
        except httpx.HTTPError as exc:
            raise transport_error(exc) from None
        if resp.status_code != 200:
            error = self._http_error(resp)
            if resp.status_code in (400, 404):
                # Forget the bad pick so the next attempt re-discovers instead of repeating it.
                if not self._text_model:
                    self._discovered_text_model = None
                others = await self._chat_candidates()
                hint = f" Model chat khả dụng: {', '.join(others[:8])}." if others else ""
                raise ProviderError(
                    error.code,
                    f"Model văn bản '{model}' không dùng được. Đặt ARK_TEXT_MODEL trong .env.{hint}")
            raise error
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("bad_response", "ModelArk trả về phản hồi không phải JSON", ErrorKind.AMBIGUOUS) from None
        choices = body.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        text = message.get("content")
        if isinstance(text, list):  # some deployments return content parts
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        if not text or not str(text).strip():
            raise ProviderError("no_text", "ModelArk không trả về văn bản")
        return str(text)

    async def test_connection(self) -> str:
        if not self._key:
            raise ProviderError("provider_not_configured", "Chưa cấu hình ARK_API_KEY")
        if self.control_plane_configured:
            # Verifies the signed credentials and refreshes the catalogue in one call.
            mapped = self.map_catalogue(await self.fetch_catalogue())
            if mapped:
                self._live = mapped
            names = ", ".join(m.id for m in mapped[:4]) or "không có model ảnh nào"
            return f"Kết nối OK — {len(mapped)} model ảnh trên tài khoản: {names}"
        try:
            resp = await self._client.get(f"{self._base}/models", headers=self._headers(), timeout=20)
        except httpx.HTTPError as exc:
            raise transport_error(exc, submitted_is_billable=False) from None
        if resp.status_code == 200:
            try:
                count = len(resp.json().get("data") or [])
            except ValueError:
                count = 0
            return f"Kết nối OK — key hợp lệ, {count} model khả dụng" if count else "Kết nối OK — key hợp lệ"
        if resp.status_code in (404, 405):
            # Documented on Volcengine Ark but not confirmed against a live BytePlus key;
            # generating an image to test instead would cost money.
            raise ProviderError("test_unsupported", "ModelArk không có endpoint /models để kiểm tra key mà không tốn phí")
        raise self._http_error(resp)
