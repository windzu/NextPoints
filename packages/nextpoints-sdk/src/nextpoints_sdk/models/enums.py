from enum import Enum


class ServiceType(str, Enum):
    PRE_ANNOTATION = "PRE_ANNOTATION"
    RECONSTRUCTION = "RECONSTRUCTION"
    CALIBRATION = "CALIBRATION"


class ErrorCode(str, Enum):
    VALIDATION = "VALIDATION"
    INTERNAL = "INTERNAL"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED = "UNSUPPORTED"
    AUTH = "AUTH"


class ArtifactType(str, Enum):
    POINT_CLOUD_MAP = "POINT_CLOUD_MAP"
    CALIB_REPORT = "CALIB_REPORT"
    CALIB_DATA = "CALIB_DATA"


class TaskStatusEnum(str, Enum):
    """任务状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectStatusEnum(str, Enum):
    """项目状态"""

    unstarted = "unstarted"
    in_progress = "in_progress"
    completed = "completed"
    reviewed = "reviewed"


class ProjectDataSourceType(str, Enum):
    """项目数据源类型"""

    NEXTPOINTS = "nextpoints"  # 直接创建
    CUSTOM = "custom"  # custom 2 nextpoints
    SUS = "sus"  # sus 2 nextpoints
