from typing import Optional, List, Dict
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, JSON  # ✅ 新增导入
from pydantic import BaseModel


# 项目状态枚举
class ProjectStatus(str, Enum):
    unstarted = "unstarted"
    in_progress = "in_progress"
    completed = "completed"
    reviewed = "reviewed"


# 帧标注状态枚举
class AnnotationStatus(str, Enum):
    unlabeled = "unlabeled"
    in_progress = "in_progress"
    completed = "completed"
    reviewed = "reviewed"


class Project(SQLModel, table=True):
    """
    标注项目（场景）表：一个项目对应一个完整的多帧数据序列
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
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

    # 关联帧与标定信息
    frames: List["Frame"] = Relationship(back_populates="project")
    calibration: Optional["Calibration"] = Relationship(back_populates="project")


class Frame(SQLModel, table=True):
    """
    帧数据表：代表一个时间点的多模态数据（点云、图像、位姿等）
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp_ns: int = Field(index=True, description="以纳秒为单位的时间戳")

    # 必需数据
    pointcloud_s3_key: str  # 点云数据完整路径

    # 可选数据
    images: Optional[Dict[str, str]] = Field(
        default=None, sa_column=Column(JSON), description="相机ID到图像路径的映射"
    )

    pose: Optional[Dict] = Field(
        default=None, sa_column=Column(JSON), description="车辆位姿信息（位置 + 姿态）"
    )

    annotation_status: AnnotationStatus = Field(default=AnnotationStatus.unlabeled)

    # 外键关联项目
    project_id: int = Field(foreign_key="project.id")
    project: Project = Relationship(back_populates="frames")

    # 标注信息
    annotation: Optional["Annotation"] = Relationship(back_populates="frame")


class Annotation(SQLModel, table=True):
    """
    标注结果表：一个帧可以有一个对应的标注结果
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    frame_id: int = Field(foreign_key="frame.id", unique=True)
    frame: Frame = Relationship(back_populates="annotation")

    content: Dict = Field(
        default={},
        sa_column=Column(JSON),
        description="标注内容，可为 3D box、mask、多模态结构等",
    )


class Calibration(SQLModel, table=True):
    """
    标定信息表：每个项目对应一组传感器的内外参
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", unique=True)
    project: Project = Relationship(back_populates="calibration")

    intrinsics: Dict[str, Dict] = Field(
        default={}, sa_column=Column(JSON), description="相机ID到内参矩阵"
    )

    extrinsics: Dict[str, Dict] = Field(
        default={}, sa_column=Column(JSON), description="传感器对之间的变换关系"
    )


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
    frame_count: int


class ProjectStatusUpdateRequest(BaseModel):
    """项目状态更新请求模型"""
    status: ProjectStatus