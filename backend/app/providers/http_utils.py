import base64
from urllib.parse import urlparse

import httpx

from app.logging_setup import redact
from app.providers.base import ErrorKind, ProviderError


def transport_error(exc: httpx.HTTPError, *, submitted_is_billable: bool = True) -> ProviderError:
    """Classify network failures by whether the request may have reached the provider."""
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)):
        return ProviderError("network_unreachable", "Không kết nối được tới nhà cung cấp", ErrorKind.TRANSIENT_SAFE)
    kind = ErrorKind.AMBIGUOUS if submitted_is_billable else ErrorKind.TRANSIENT_SAFE
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError("timeout", "Hết thời gian chờ phản hồi từ nhà cung cấp", kind)
    return ProviderError("network_error", f"Lỗi mạng: {type(exc).__name__}", kind)


def retry_after_seconds(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def error_text(resp: httpx.Response, secrets: tuple[str, ...], limit: int = 300) -> str:
    """Provider error text, with the caller's own credentials scrubbed (some APIs echo them back)."""
    try:
        body = resp.json()
    except ValueError:
        return redact(resp.text[:limit], secrets)
    detail = body.get("error", body) if isinstance(body, dict) else body
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("detail") or detail
    return redact(str(detail), secrets)[:limit]


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def host_allowed(url: str, allowed_suffixes: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == s or host.endswith("." + s) for s in allowed_suffixes)


async def download_image(client: httpx.AsyncClient, url: str, max_bytes: int) -> tuple[bytes, str]:
    """Fetch a provider-hosted result without forwarding credentials."""
    try:
        async with client.stream("GET", url, timeout=httpx.Timeout(60, connect=10)) as resp:
            if resp.status_code != 200:
                raise ProviderError("download_failed", f"Tải ảnh kết quả thất bại (HTTP {resp.status_code})", ErrorKind.TRANSIENT_SAFE)
            chunks, total = [], 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ProviderError("download_too_large", "Ảnh kết quả vượt giới hạn kích thước")
                chunks.append(chunk)
            return b"".join(chunks), resp.headers.get("content-type", "application/octet-stream").split(";")[0]
    except httpx.HTTPError as exc:
        raise transport_error(exc, submitted_is_billable=False) from None
