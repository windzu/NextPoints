from pydantic import BaseModel
from typing import Dict, List, Optional
from .annotation import AnnotationItem
from .calibration import CalibrationMetadata
from .artifacts import Artifact


class BaseTaskResponse(BaseModel):
    duration_seconds: float
    request_id: str


class PreAnnotationResponse(BaseTaskResponse):
    annotations: Dict[int, List[AnnotationItem]]


class ReconstructionResponse(BaseTaskResponse):
    point_cloud_map: Artifact


class CalibrationResponse(BaseTaskResponse):
    updated_calibration: Optional[Dict[str, CalibrationMetadata]] = None
    artifacts: Optional[List[Artifact]] = None
