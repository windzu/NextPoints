from pydantic import BaseModel
from typing import Dict, Any, Optional
from .project_metadata import ProjectMetadataResponse


class BaseTaskRequest(BaseModel):
    project_meta: ProjectMetadataResponse
    params: Dict[str, Any] = {}


class PreAnnotationRequest(BaseTaskRequest):
    pass


class ReconstructionRequest(BaseTaskRequest):
    pass


class CalibrationRequest(BaseTaskRequest):
    pass
