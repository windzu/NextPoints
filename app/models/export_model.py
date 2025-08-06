"""
导出任务相关的 Pydantic 模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class ExportFormat(str, Enum):
    """支持的导出格式"""
    NUSCENES_V1_0 = "nuscenes_v1.0"
    KITTI = "kitti"
    WAYMO = "waymo"

class ExportStatus(str, Enum):
    """导出任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CoordinateSystem(str, Enum):
    """坐标系选择"""
    EGO_VEHICLE = "ego_vehicle"
    GLOBAL = "global"
    LIDAR = "lidar"

class FrameSelection(BaseModel):
    """帧选择配置"""
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    frame_step: int = Field(default=1, ge=1, description="帧间隔，每隔几帧导出一次")
    max_frames: Optional[int] = Field(default=None, ge=1, description="最大导出帧数")

class AnnotationFilter(BaseModel):
    """标注过滤配置"""
    object_types: Optional[List[str]] = Field(default=None, description="只导出指定类型的对象")
    min_points: Optional[int] = Field(default=None, ge=0, description="最小点云数量阈值")
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="置信度阈值")
    bbox_size_filter: Optional[Dict[str, float]] = Field(default=None, description="边界框尺寸过滤")

class ExportOptions(BaseModel):
    """导出选项配置"""
    include_images: bool = True
    include_pointcloud: bool = True
    include_calibration: bool = True
    include_ego_pose: bool = True
    compress_output: bool = True
    output_format: str = "zip"  # zip, tar.gz
    coordinate_precision: int = Field(default=6, ge=1, le=10, description="坐标精度（小数位数）")

class NuScenesExportRequest(BaseModel):
    """NuScenes 导出请求模型"""
    export_format: ExportFormat = ExportFormat.NUSCENES_V1_0
    coordinate_system: CoordinateSystem = CoordinateSystem.EGO_VEHICLE
    frame_selection: Optional[FrameSelection] = None
    annotation_filter: Optional[AnnotationFilter] = None
    export_options: Optional[ExportOptions] = None
    notification_email: Optional[str] = Field(default=None, description="完成后通知邮箱")
    custom_metadata: Optional[Dict[str, Any]] = Field(default=None, description="自定义元数据")

class ExportTaskResponse(BaseModel):
    """导出任务创建响应"""
    task_id: str
    status: ExportStatus
    message: str
    created_at: datetime
    estimated_duration: Optional[int] = Field(default=None, description="预估耗时（秒）")
    
class ExportTaskStatus(BaseModel):
    """导出任务状态响应"""
    task_id: str
    status: ExportStatus
    progress: float = Field(ge=0.0, le=100.0, description="进度百分比")
    current_step: Optional[str] = Field(default=None, description="当前处理步骤")
    message: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 结果信息
    download_url: Optional[str] = None
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    total_frames_processed: Optional[int] = None
    total_annotations_exported: Optional[int] = None
    
    # 错误信息
    error_details: Optional[str] = None
    retry_count: Optional[int] = Field(default=0, description="重试次数")

class ExportTaskList(BaseModel):
    """导出任务列表响应"""
    tasks: List[ExportTaskStatus]
    total_count: int
    page: int
    page_size: int
