import httpx
from fastapi import Request

from app.providers.base import CapabilityError, ImageProvider, ImageRequest, ModelInfo, Submission
from app.providers.bfl import BflProvider
from app.providers.gemini import GeminiProvider
from app.providers.mock import MockProvider
from app.providers.modelark import ModelArkProvider
from app.providers.openai_images import OpenAIImageProvider


class MidjourneyInfo(ImageProvider):
    name = "midjourney"
    display_name = "Midjourney"
    selectable = False
    info_url = "https://www.midjourney.com"
    data_notice = (
        "Midjourney không có API công khai chính thức (kiểm tra 2026-10). Ứng dụng không dùng công cụ tự động hoá "
        "không chính thức, nên chỉ liệt kê để tham khảo."
    )

    @property
    def key_configured(self) -> bool:
        return False

    def models(self) -> list[ModelInfo]:
        return []

    async def submit(self, request: ImageRequest) -> Submission:
        raise CapabilityError("provider_disabled", "Midjourney không được hỗ trợ")

    async def test_connection(self) -> str:
        raise CapabilityError("provider_disabled", "Midjourney không có API chính thức")


class ProviderRegistry:
    def __init__(self, providers: list[ImageProvider]):
        self._providers = {p.name: p for p in providers}

    def all(self) -> list[ImageProvider]:
        return list(self._providers.values())

    def get(self, name: str) -> ImageProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise CapabilityError("unknown_provider", f"Không có nhà cung cấp '{name}'") from None


def build_registry(client: httpx.AsyncClient) -> ProviderRegistry:
    return ProviderRegistry([MockProvider(), GeminiProvider(client), BflProvider(client),
                         ModelArkProvider(client), OpenAIImageProvider(client), MidjourneyInfo()])


def get_registry(request: Request) -> ProviderRegistry:
    return request.app.state.registry
