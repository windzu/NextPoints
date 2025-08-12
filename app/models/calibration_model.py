from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel

from app.models.base_model import Pose

class CameraModel(str, Enum):
    PINHOLE = "pinhole"
    FISHEYE = "fisheye"
    OMNIDIRECTIONAL = "omnidirectional"

class CameraIntrinsics(BaseModel):
    fx: float  # 焦距x
    fy: float  # 焦距y
    cx: float  # 主点x
    cy: float  # 主点y
    skew: Optional[float] = 0.0  # 偏斜参数

class CameraDistortion(BaseModel):
    k1: float  # 径向畸变系数1
    k2: float  # 径向畸变系数2
    p1: float  # 切向畸变系数1
    p2: float  # 切向畸变系数2
    k3: Optional[float] = 0.0  # 径向畸变系数3
    k4: Optional[float] = 0.0  # 径向畸变系数4
    k5: Optional[float] = 0.0



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
    model: CameraModel
    intrinsic: CameraIntrinsics  # 相机内参矩阵
    distortion_coefficients: CameraDistortion  # 畸变系数

class CalibrationMetadata(BaseModel):
    """标定信息响应模型"""
    channel: str
    pose : Pose
    camera_config: Optional[CameraConfig] = None  # 包含相机内参、畸变系数等
    ignore_areas: List[IgnoreArea] = []  # 可选，忽略区域列表



