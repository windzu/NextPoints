from pydantic import BaseModel, model_validator
from typing import Optional, List
from enum import Enum

from .pose import Pose


class SensorType(str, Enum):
    LIDAR = "lidar"
    CAMERA = "camera"
    RADAR = "radar"
    IMU = "imu"
    GPS = "gps"


class CameraModel(str, Enum):
    PINHOLE = "pinhole"
    FISHEYE = "fisheye"
    OMNIDIRECTIONAL = "omnidirectional"


class CameraIntrinsics(BaseModel):
    fx: float
    fy: float
    cx: float
    cy: float
    skew: Optional[float] = 0.0


class CameraDistortion(BaseModel):
    k1: float
    k2: float
    p1: float
    p2: float
    k3: Optional[float] = 0.0
    k4: Optional[float] = 0.0
    k5: Optional[float] = 0.0


class IgnoreArea(BaseModel):
    x: float
    y: float
    z: Optional[float] = 0.0
    width: float
    height: float
    yaw: Optional[float] = 0.0


class CameraConfig(BaseModel):
    width: int
    height: int
    model: CameraModel
    intrinsic: CameraIntrinsics
    distortion_coefficients: CameraDistortion


class CalibrationMetadata(BaseModel):
    channel: str
    sensor_type: SensorType
    pose: Pose
    camera_config: Optional[CameraConfig] = None
    ignore_areas: List[IgnoreArea] = []

    @model_validator(mode="after")
    def check_camera_config_requirement(self):
        if self.sensor_type == SensorType.CAMERA:
            if self.camera_config is None:
                raise ValueError(
                    "When sensor_type is CAMERA, camera_config must be provided"
                )
        else:
            if self.camera_config is not None:
                raise ValueError(
                    f"When sensor_type is {self.sensor_type}, camera_config must be None"
                )
        return self
