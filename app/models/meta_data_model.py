from typing import Optional, List, Dict
from pydantic import BaseModel

from app.models.project_model import ProjectResponse
from app.models.annotation_model import AnnotationItem
from app.models.calibration_model import CalibrationMetadata


class FrameMetadata(BaseModel):
    """帧元数据响应模型"""
    id: int
    timestamp_ns: str
    prev_timestamp_ns: Optional[str] = None
    next_timestamp_ns: Optional[str] = None
    pointcloud_url: str
    images: Optional[Dict[str, str]] = None
    pose: Optional[Dict] = None
    annotation: Optional[List[AnnotationItem]] = None

class ProjectMetadataResponse(BaseModel):
    """项目完整元数据响应模型"""
    project: ProjectResponse

    # 摘要信息
    frame_count: int
    start_timestamp_ns: str
    end_timestamp_ns: str
    duration_seconds: float

    # 标定信息（字典结构）
    calibration: Dict[str, CalibrationMetadata]

    # 帧列表（有序且包含上下文链接）
    frames: List[FrameMetadata]

