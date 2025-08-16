import httpx
import time
import uuid
from typing import Optional, Dict, Any, Type, TypeVar

from ..version import SDK_VERSION
from ..models.errors import ErrorModel
from ..models.enums import ErrorCode
from ..exceptions import SDKException, TimeoutException

T = TypeVar("T")


class HttpClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 600.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self._client = httpx.Client(timeout=timeout)

    def _headers(self, request_id: str) -> Dict[str, str]:
        h = {
            "X-NextPoints-SDK-Version": SDK_VERSION,
            "X-Request-Id": request_id,
            "User-Agent": f"nextpoints-sdk/{SDK_VERSION}",
        }
        if self.api_key:
            h["Authorization"] = f"ApiKey {self.api_key}"
        h.update(self.extra_headers)
        return h

    def post_json(
        self,
        path: str,
        payload: Dict[str, Any],
        response_model: Type[T],
        timeout: Optional[float] = None,
    ) -> T:
        request_id = str(uuid.uuid4())
        url = f"{self.base_url}{path}"
        headers = self._headers(request_id)
        start = time.time()
        try:
            resp = self._client.post(
                url, json=payload, headers=headers, timeout=timeout or self.timeout
            )
        except httpx.ReadTimeout:
            raise TimeoutException(
                ErrorCode.TIMEOUT, f"Request timeout after {timeout or self.timeout}s"
            )
        duration = time.time() - start
        if resp.status_code >= 400:
            # attempt parse error
            try:
                data = resp.json()
                err = ErrorModel(**data)
                raise SDKException(err.code, err.message, err.detail)
            except SDKException:
                raise
            except Exception:
                raise SDKException(
                    ErrorCode.INTERNAL,
                    f"HTTP {resp.status_code} without valid error body",
                )
        data = resp.json()
        # inject duration if model expects it and not provided
        if isinstance(data, dict) and "duration_seconds" not in data:
            data["duration_seconds"] = duration
            data["request_id"] = request_id
        return response_model(**data)

    def close(self):
        self._client.close()
