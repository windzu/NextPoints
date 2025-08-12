from typing import Optional, List, Dict
from pydantic import BaseModel, field_validator

from app.models.base_model import Position, Rotation, Scale

class PSR(BaseModel):
    """位置、缩放、旋转信息"""
    position: Position
    rotation: Rotation
    scale: Scale

class AnnotationItem(BaseModel):
    """单个标注项"""
    obj_id: str
    obj_type: str
    obj_attr: Optional[str] = None
    num_pts: Optional[int] = None
    psr: PSR


class FrameAnnotation(BaseModel):
    """单帧的标注数据模型"""
    scene: str  # 项目名称
    frame: str  # 帧ID
    annotation: Optional[List[AnnotationItem]] = []

    @field_validator('annotation', mode='before')
    @classmethod
    def normalize_annotation(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):  # 单个对象转为数组
            return [v]
        return v  # 已经是数组，直接返回
    
    def to_dict(self):
        return {
            "scene": self.scene,
            "frame": self.frame,
            "annotation": [a.model_dump() for a in self.annotation]
        }