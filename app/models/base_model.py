from typing import Optional, List, Dict
from pydantic import BaseModel, field_validator

class Translation(BaseModel):
    """平移信息模型"""
    x: float
    y: float
    z: float
    
class Rotation(BaseModel):
    """旋转信息模型"""
    x: float
    y: float
    z: float
    w: float

class Transform(BaseModel):
    """变换信息模型"""
    translation: Translation
    rotation: Rotation

class Pose(BaseModel):
    """位姿信息模型"""
    parent_frame_id: str
    child_frame_id: str
    transform: Transform


class Position(BaseModel):
    """位置信息"""
    x: float
    y: float
    z: float

class Scale(BaseModel):
    """缩放信息"""
    x: float
    y: float
    z: float






