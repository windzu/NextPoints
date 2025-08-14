from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime
from enum import Enum
from pydantic import BaseModel

from app.models.status_model import TaskStatus


# Database Models

# 项目状态枚举
class ProjectStatus(str, Enum):
    unstarted = "unstarted"
    in_progress = "in_progress"
    completed = "completed"
    reviewed = "reviewed"

class DataSourceType(str, Enum):
    NEXTPOINTS = "nextpoints"
    CUSTOM = "custom"
    SUS = "sus"


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
    bucket_name: str
    bucket_prefix: Optional[str] = None
    region_name: str = Field(default="us-east-1")
    s3_endpoint: Optional[str] = None
    access_key_id: str
    secret_access_key: str
    use_presigned_urls: bool = Field(default=True)
    expiration_minutes: int = Field(default=60)



# Projects Model
class ProjectCreateRequest(BaseModel):
    """创建项目请求模型"""
    project_name: str
    data_source_type: DataSourceType = DataSourceType.NEXTPOINTS

    description: Optional[str] = None
    storage_type: str = "AWS S3"
    bucket_name: str
    region_name: str = "us-east-1"
    s3_endpoint: Optional[str] = None
    access_key_id: str
    secret_access_key: str
    use_presigned_urls: bool = True
    expiration_minutes: int = 60

    main_channel: str = "lidar-fusion"
    time_interval: float = 0.5  # 时间间隔，单位为秒

class ProjectCreateResponse(BaseModel):
    """项目响应模型"""
    project_name: str
    status: TaskStatus
    message: Optional[str]

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
