from typing import List, Dict, Set, Optional
from pydantic import BaseModel, model_validator

from .annotation import AnnotationItem
from .calibration import CalibrationMetadata, SensorType
from .pose import Pose


class ProjectResponse(BaseModel):
    id: int
    name: str


class FrameMetadata(BaseModel):
    id: int
    timestamp_ns: str
    prev_timestamp_ns: str
    next_timestamp_ns: str
    lidars: Dict[str, str]
    images: Optional[Dict[str, str]] = None
    pose: Optional[Pose] = None
    annotation: Optional[List[AnnotationItem]] = None


class ProjectMetadataResponse(BaseModel):
    project: ProjectResponse
    frame_count: int
    start_timestamp_ns: str
    end_timestamp_ns: str
    duration_seconds: float
    main_channel: str
    calibration: Dict[str, CalibrationMetadata]
    frames: List[FrameMetadata]

    @model_validator(mode="after")
    def validate_frames_and_calibration(self):
        if not self.frames:
            raise ValueError("frames 不能为空")
        first = self.frames[0]
        if not first.lidars or len(first.lidars) == 0:
            raise ValueError(f"frame id={first.id} 的 lidars 不能为空")
        lidar_keys_ref: Set[str] = set(first.lidars.keys())
        image_keys_ref: Set[str] = set(first.images.keys()) if first.images else set()
        for idx, f in enumerate(self.frames):
            if not f.lidars or len(f.lidars) == 0:
                raise ValueError(f"frame idx={idx}, id={f.id} 的 lidars 不能为空")
            lks = set(f.lidars.keys())
            if lks != lidar_keys_ref:
                missing = lidar_keys_ref - lks
                extra = lks - lidar_keys_ref
                raise ValueError(
                    f"lidars key 不一致 at frame idx={idx}, id={f.id}；"
                    f"缺失: {sorted(missing)}，多出: {sorted(extra)}；"
                    f"参考: {sorted(lidar_keys_ref)}"
                )
            iks = set(f.images.keys()) if f.images else set()
            if iks != image_keys_ref:
                missing = image_keys_ref - iks
                extra = iks - image_keys_ref
                raise ValueError(
                    f"images key 不一致 at frame idx={idx}, id={f.id}；"
                    f"缺失: {sorted(missing)}，多出: {sorted(extra)}；"
                    f"参考: {sorted(image_keys_ref)}"
                )
        frames_lidar_keys = set(lidar_keys_ref)
        frames_camera_keys = set(image_keys_ref)
        calib_lidar_keys = {
            name
            for name, calib in self.calibration.items()
            if calib.sensor_type == SensorType.LIDAR
        }
        calib_camera_keys = {
            name
            for name, calib in self.calibration.items()
            if calib.sensor_type == SensorType.CAMERA
        }
        if calib_lidar_keys != frames_lidar_keys:
            missing = frames_lidar_keys - calib_lidar_keys
            extra = calib_lidar_keys - frames_lidar_keys
            raise ValueError(
                "calibration(LIDAR) 与 frames 中的 lidar key 不一致；"
                f"calibration 缺失: {sorted(missing)}，calibration 多出: {sorted(extra)}；"
                f"frames.lidars: {sorted(frames_lidar_keys)}"
            )
        if calib_camera_keys != frames_camera_keys:
            missing = frames_camera_keys - calib_camera_keys
            extra = calib_camera_keys - frames_camera_keys
            raise ValueError(
                "calibration(CAMERA) 与 frames 中的 camera key 不一致；"
                f"calibration 缺失: {sorted(missing)}，calibration 多出: {sorted(extra)}；"
                f"frames.images: {sorted(frames_camera_keys)}"
            )
        return self
