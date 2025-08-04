from typing import Optional, List, Dict,Any
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, JSON  # ✅ 新增导入
from pydantic import BaseModel


# Database Models

# 项目状态枚举
class ProjectStatus(str, Enum):
    unstarted = "unstarted"
    in_progress = "in_progress"
    completed = "completed"
    reviewed = "reviewed"


class Project(SQLModel, table=True):
    """
    标注项目（场景）表：一个项目对应一个完整的多帧数据序列
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True,unique=True)  # 项目名称，唯一
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 项目标注状态
    status: ProjectStatus = Field(default=ProjectStatus.unstarted)

    # S3 存储配置
    storage_type: str = Field(default="AWS S3")
    storage_title: Optional[str] = None
    bucket_name: str
    bucket_prefix: Optional[str] = None
    region_name: str = Field(default="us-east-1")
    s3_endpoint: Optional[str] = None
    access_key_id: str
    secret_access_key: str
    use_presigned_urls: bool = Field(default=False)
    expiration_minutes: int = Field(default=60)

    s3_root_path: str  # 项目数据的根路径



# Projects Model
class ProjectCreateRequest(BaseModel):
    """创建项目请求模型"""
    project_name: str
    description: Optional[str] = None
    storage_type: str = "AWS S3"
    storage_title: Optional[str] = None
    bucket_name: str
    bucket_prefix: Optional[str] = None
    region_name: str = "us-east-1"
    s3_endpoint: Optional[str] = None
    access_key_id: str
    secret_access_key: str
    use_presigned_urls: bool = False
    expiration_minutes: int = 60


class ProjectResponse(BaseModel):
    """项目响应模型"""
    id: Optional[int]
    name: str
    description: Optional[str]
    status: ProjectStatus
    created_at: str


class ProjectStatusUpdateRequest(BaseModel):
    """项目状态更新请求模型"""
    status: ProjectStatus


# 项目元数据相关模型
class FrameMetadata(BaseModel):
    """帧元数据响应模型"""
    id: int
    timestamp_ns: str
    prev_timestamp_ns: Optional[str] = None
    next_timestamp_ns: Optional[str] = None
    pointcloud_url: str
    images: Optional[Dict[str, str]] = None
    pose: Optional[Dict] = None


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