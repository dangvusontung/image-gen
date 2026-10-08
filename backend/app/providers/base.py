from abc import ABC, abstractmethod
from typing import List, Dict, Any


class AbstractProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'mock', 'gemini', 'flux')."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """Provider capabilities: models, max_images, supported_ratios, etc."""
        pass

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        references: List[bytes],
        width: int = 512,
        height: int = 512,
    ) -> bytes:
        """Generate and return image as PNG bytes."""
        pass
