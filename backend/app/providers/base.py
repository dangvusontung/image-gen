from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    max_reference_images: int
    aspect_ratios: tuple[str, ...]
    default_aspect_ratio: str = "1:1"
    price_per_image_usd: float | None = None
    # Optional per-size prices keyed by the provider's size option (e.g. Gemini "1K"/"2K").
    price_table: tuple[tuple[str, float], ...] = ()
    price_note: str | None = None
    sizes: tuple[str, ...] = ()
    default_size: str | None = None
    status: str = "ga"  # "ga" | "preview" | "deprecated"
    notes: str | None = None
    default: bool = False


@dataclass(frozen=True)
class ReferenceImage:
    data: bytes
    mime_type: str
    label: str  # role hint, e.g. "reference 1", "master"; never contains secrets


@dataclass
class ImageRequest:
    model: str
    prompt: str
    references: list[ReferenceImage] = field(default_factory=list)
    aspect_ratio: str = "1:1"
    seed: int | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedImage:
    data: bytes
    mime_type: str


class SubmissionState(str, Enum):
    PENDING = "pending"
    READY = "ready"


@dataclass
class Submission:
    """Result of submit(): either images are ready now (sync APIs) or a provider task to poll."""

    state: SubmissionState
    provider_request_id: str | None = None
    polling_url: str | None = None
    images: list[GeneratedImage] = field(default_factory=list)
    actual_cost_usd: float | None = None


class ErrorKind(str, Enum):
    # Request was rejected before any work happened: retry is safe and cannot double-bill.
    TRANSIENT_SAFE = "transient_safe"
    # Outcome unknown (timeout/5xx after sending): the provider may have run and billed it.
    AMBIGUOUS = "ambiguous"
    # Will fail the same way again (validation, auth, moderation, credits).
    PERMANENT = "permanent"


class ProviderError(Exception):
    def __init__(self, code: str, message: str, kind: ErrorKind = ErrorKind.PERMANENT, retry_after: float | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
        self.retry_after = retry_after


class CapabilityError(ProviderError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, ErrorKind.PERMANENT)


class ImageProvider(ABC):
    name: str
    display_name: str
    #: Disabled providers are listed for information only and never receive jobs.
    selectable: bool = True
    info_url: str | None = None
    data_notice: str | None = None

    @property
    @abstractmethod
    def key_configured(self) -> bool: ...

    @abstractmethod
    def models(self) -> list[ModelInfo]: ...

    def get_model(self, model_id: str) -> ModelInfo:
        for m in self.models():
            if m.id == model_id:
                return m
        raise CapabilityError("unknown_model", f"Model '{model_id}' không có trong {self.display_name}")

    def default_model(self) -> ModelInfo:
        models = self.models()
        if not models:
            raise CapabilityError("provider_disabled", f"{self.display_name} không có model nào dùng được")
        return next((m for m in models if m.default), models[0])

    def check_request(self, model_id: str, reference_count: int, aspect_ratio: str, size: str | None = None) -> ModelInfo:
        """Refuse requests the model can't honour instead of silently dropping references."""
        if not self.selectable:
            raise CapabilityError("provider_disabled", f"{self.display_name} không hỗ trợ tạo ảnh trong ứng dụng này")
        if not self.key_configured:
            raise CapabilityError("provider_not_configured", f"Chưa cấu hình API key cho {self.display_name}")
        model = self.get_model(model_id)
        if reference_count > model.max_reference_images:
            raise CapabilityError(
                "reference_limit_exceeded",
                f"{model.display_name} nhận tối đa {model.max_reference_images} ảnh tham chiếu, "
                f"yêu cầu có {reference_count}",
            )
        if aspect_ratio not in model.aspect_ratios:
            raise CapabilityError(
                "unsupported_aspect_ratio",
                f"{model.display_name} không hỗ trợ tỉ lệ {aspect_ratio} (hỗ trợ: {', '.join(model.aspect_ratios)})",
            )
        if size is not None and size not in model.sizes:
            raise CapabilityError(
                "unsupported_size",
                f"{model.display_name} không hỗ trợ kích thước {size} (hỗ trợ: {', '.join(model.sizes) or 'mặc định'})",
            )
        return model

    def validate(self, request: ImageRequest) -> ModelInfo:
        return self.check_request(
            request.model, len(request.references), request.aspect_ratio, request.options.get("size")
        )

    def estimate_cost_usd(self, model: ModelInfo, size: str | None = None) -> float | None:
        prices = dict(model.price_table)
        if prices:
            return prices.get(size or model.default_size or "")
        return model.price_per_image_usd

    def estimate_request_cost_usd(self, model: ModelInfo, size: str | None, reference_sizes: list[tuple[int, int]]) -> float | None:
        return self.estimate_cost_usd(model, size)

    #: Non-None when the provider can enumerate the account's real catalogue; names the source.
    catalogue_source: str | None = None
    #: True when the provider can answer with text, not only images.
    supports_text: bool = False

    async def generate_text(self, prompt: str, references: list[ReferenceImage]) -> str:
        """Answer a prompt about the given images with text."""
        raise CapabilityError(
            "text_unsupported",
            f"{self.display_name} chỉ tạo ảnh, không trả về văn bản. Chọn nhà cung cấp hỗ trợ văn bản (Gemini).",
        )

    async def fetch_catalogue(self) -> list[dict[str, str]]:
        """The account's models as [{"id", "display_name"}], straight from the provider's API."""
        raise CapabilityError("catalogue_unsupported", f"{self.display_name} không có API liệt kê model")

    def apply_catalogue(self, items: list[dict[str, str]]) -> list[ModelInfo]:
        """Adopt a fetched catalogue as models(). Returns what models() will now report."""
        raise CapabilityError("catalogue_unsupported", f"{self.display_name} không có API liệt kê model")

    @abstractmethod
    async def submit(self, request: ImageRequest) -> Submission: ...

    async def poll(self, submission: Submission) -> Submission:
        raise NotImplementedError(f"{self.name} is synchronous")

    @abstractmethod
    async def test_connection(self) -> str:
        """Cheap authenticated call; returns a short human-readable status or raises ProviderError."""
