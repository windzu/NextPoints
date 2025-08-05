from typing import Optional, List, Dict
from pydantic import BaseModel

from app.models.project_model import ProjectResponse

class IgnoreArea(BaseModel):
    x: float
    y: float
    z: Optional[float] = 0.0
    width: float
    height: float
    yaw: Optional[float] = 0.0

class CameraConfig(BaseModel):
    """相机配置模型"""
    width: int
    height: int
    model: str
    intrinsic: List[List[float]]  # 相机内参矩阵
    distortion_coefficients: List[float]  # 畸变系数

class CalibrationMetadata(BaseModel):
    """标定信息响应模型"""
    channel: str
    translation: List[float]
    rotation: List[float]
    camera_config: Optional[CameraConfig] = None  # 包含相机内参、畸变系数等
    ignore_areas: List[IgnoreArea] = []  # 可选，忽略区域列表


