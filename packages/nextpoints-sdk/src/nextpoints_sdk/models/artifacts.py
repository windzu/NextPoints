from pydantic import BaseModel, HttpUrl
from typing import Optional
from .enums import ArtifactType


class Artifact(BaseModel):
    type: ArtifactType
    uri: HttpUrl  # presigned URL
    description: Optional[str] = None
