import io
from typing import List, Dict, Any
from PIL import Image, ImageDraw
from app.providers.base import AbstractProvider


class MockProvider(AbstractProvider):
    @property
    def name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "models": ["mock-v1"],
            "max_images_per_request": 4,
            "supported_ratios": ["1:1", "3:4", "4:3", "16:9"],
            "provider_status": "mock (no API calls)",
        }

    async def generate_image(
        self,
        prompt: str,
        references: List[bytes],
        width: int = 512,
        height: int = 512,
    ) -> bytes:
        """Generate a placeholder PNG with text overlay."""
        img = Image.new("RGB", (width, height), color=(200, 200, 220))
        draw = ImageDraw.Draw(img)

        text_lines = [
            "Mock Provider",
            f"{width}×{height}",
            prompt[:40] + ("..." if len(prompt) > 40 else ""),
        ]

        y_offset = height // 2 - 40
        for line in text_lines:
            draw.text(
                (width // 2 - 50, y_offset),
                line,
                fill=(50, 50, 100),
            )
            y_offset += 30

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
