from fastapi import APIRouter

from app.providers.mock import MockProvider
from app.schemas import ProviderInfo

router = APIRouter(prefix="/api/providers", tags=["providers"])

mock_provider = MockProvider()


@router.get("", response_model=list[ProviderInfo])
def list_providers():
    return [ProviderInfo(name=mock_provider.name, enabled=True, capabilities=mock_provider.capabilities)]
