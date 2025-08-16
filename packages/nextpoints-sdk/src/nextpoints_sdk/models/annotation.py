from pydantic import BaseModel, field_validator
from typing import Optional, List


# Reuse PSR style structure consistent with main project
class Position(BaseModel):
    x: float
    y: float
    z: float


class Rotation(BaseModel):
    x: float
    y: float
    z: float
    w: float


class Scale(BaseModel):
    x: float
    y: float
    z: float


class PSR(BaseModel):
    position: Position
    rotation: Rotation
    scale: Scale


class AnnotationItem(BaseModel):
    obj_id: str
    obj_type: str
    obj_attr: Optional[str] = None
    num_pts: Optional[int] = None
    psr: PSR


class FrameAnnotation(BaseModel):
    scene: str
    frame: str
    annotation: Optional[List[AnnotationItem]] = []

    @field_validator("annotation", mode="before")
    @classmethod
    def normalize_annotation(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        return v

    def to_dict(self):
        ann = self.annotation or []
        return {
            "scene": self.scene,
            "frame": self.frame,
            "annotation": [a.model_dump() for a in ann],
        }
