from typing import Optional, List, Dict, Set
from pydantic import BaseModel, model_validator


from app.models.project_model import ProjectResponse

from .annotation import AnnotationItem
from .pose import Pose
from .calibration import CalibrationMetadata, SensorType


class FrameMetadata(BaseModel):
    """帧元数据响应模型"""

    id: int
    timestamp_ns: str
    prev_timestamp_ns: str
    next_timestamp_ns: str
    lidars: Dict[str, str]  # 必须有点云数据
    images: Optional[Dict[str, str]] = None
    pose: Optional[Pose] = None
    annotation: Optional[List[AnnotationItem]] = None


class ProjectMetadataResponse(BaseModel):
    """项目完整元数据响应模型"""

    project: ProjectResponse

    # 摘要信息
    frame_count: int
    start_timestamp_ns: str
    end_timestamp_ns: str
    duration_seconds: float
    main_channel: str

    # 标定信息（字典结构）
    calibration: Dict[str, CalibrationMetadata]

    # 帧列表（有序且包含上下文链接）
    frames: List[FrameMetadata]

    @model_validator(mode="after")
    def validate_frames_and_calibration(self):
        # —— 0) 基础校验：必须有帧
        if not self.frames:
            raise ValueError("frames 不能为空")

        # —— 1) 以第一帧作为基准，提取 lidars / images 的 key 模板
        first = self.frames[0]
        # lidars 必须非空
        if not first.lidars or len(first.lidars) == 0:
            raise ValueError(f"frame id={first.id} 的 lidars 不能为空")
        lidar_keys_ref: Set[str] = set(first.lidars.keys())

        # images 允许为空；若第一帧为 None，则参考集合为空集
        image_keys_ref: Set[str] = set(first.images.keys()) if first.images else set()

        # —— 2) 遍历所有帧，检查 key 集合一致性
        for idx, f in enumerate(self.frames):
            # 2.1 lidars 一致性（必有）
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

            # 2.2 images 一致性（允许整体都为空；但一旦有，则所有帧都必须有且 key 相同）
            iks = set(f.images.keys()) if f.images else set()
            if iks != image_keys_ref:
                # 若参考为空，但当前帧有 images，或参考非空但当前帧缺失/不同，均不允许
                missing = image_keys_ref - iks
                extra = iks - image_keys_ref
                raise ValueError(
                    f"images key 不一致 at frame idx={idx}, id={f.id}；"
                    f"缺失: {sorted(missing)}，多出: {sorted(extra)}；"
                    f"参考: {sorted(image_keys_ref)}"
                )

        # —— 3) 由帧统计得到的传感器 key 集合
        frames_lidar_keys = set(lidar_keys_ref)
        frames_camera_keys = set(image_keys_ref)

        # —— 4) 从 calibration 中按 sensor_type 分类统计
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

        # —— 5) 一一对应关系检查（集合必须相等）
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

        # 通过校验
        return self
