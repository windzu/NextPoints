from typing import Optional, Dict, Any
from ..models.requests import (
    PreAnnotationRequest,
    ReconstructionRequest,
    CalibrationRequest,
)
from ..models.responses import (
    PreAnnotationResponse,
    ReconstructionResponse,
    CalibrationResponse,
)
from .http_client import HttpClient


class ServicesClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 600.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.http = HttpClient(
            base_url, api_key=api_key, timeout=timeout, extra_headers=extra_headers
        )

    def pre_annotate(
        self, req: PreAnnotationRequest, timeout: Optional[float] = None
    ) -> PreAnnotationResponse:
        return self.http.post_json(
            "/pre-annotation",
            req.model_dump(mode="json"),
            PreAnnotationResponse,
            timeout=timeout,
        )

    def reconstruct(
        self, req: ReconstructionRequest, timeout: Optional[float] = None
    ) -> ReconstructionResponse:
        return self.http.post_json(
            "/reconstruction",
            req.model_dump(mode="json"),
            ReconstructionResponse,
            timeout=timeout,
        )

    def calibrate(
        self, req: CalibrationRequest, timeout: Optional[float] = None
    ) -> CalibrationResponse:
        return self.http.post_json(
            "/calibration",
            req.model_dump(mode="json"),
            CalibrationResponse,
            timeout=timeout,
        )

    def close(self):
        self.http.close()
