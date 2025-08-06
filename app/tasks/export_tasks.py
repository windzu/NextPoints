"""
Celery 导出任务定义
"""
import os
import json
import uuid
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from celery import current_task
from celery.exceptions import Retry

# 注意：这里需要导入你实际的 celery_app
# from app.celery_app import celery_app
from app.models.export_model import ExportStatus, NuScenesExportRequest
from app.models.annotation_model import AnnotationItem
from app.database import get_session
from app.services.project_service import get_project_metadata
from app.services.s3_service import S3Service

# 临时使用 Celery 实例（实际应该从 celery_app 导入）
from celery import Celery
celery_app = Celery('nextpoints')

@celery_app.task(bind=True, name="export_to_nuscenes")
def export_to_nuscenes_task(
    self,
    project_name: str,
    export_request: Dict[str, Any],
    task_id: str
) -> Dict[str, Any]:
    """
    导出项目到 NuScenes 格式的异步任务
    
    Args:
        project_name: 项目名称
        export_request: 导出请求配置
        task_id: 任务ID
    
    Returns:
        任务结果字典
    """
    try:
        # 更新任务状态为处理中
        current_task.update_state(
            state=ExportStatus.PROCESSING,
            meta={
                "progress": 0,
                "current_step": "Initializing export task",
                "message": "Starting NuScenes export process"
            }
        )
        
        # 1. 验证和解析请求
        request = NuScenesExportRequest(**export_request)
        
        # 2. 获取项目元数据
        current_task.update_state(
            state=ExportStatus.PROCESSING,
            meta={
                "progress": 10,
                "current_step": "Loading project metadata",
                "message": f"Loading metadata for project: {project_name}"
            }
        )
        
        with get_session() as session:
            project_metadata = get_project_metadata(project_name, session)
            if not project_metadata:
                raise ValueError(f"Project {project_name} not found")
        
        # 3. 创建输出目录
        output_dir = Path(f"/tmp/exports/{task_id}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. 执行转换
        result = _perform_nuscenes_conversion(
            task=current_task,
            project_metadata=project_metadata,
            export_request=request,
            output_dir=output_dir
        )
        
        # 5. 压缩输出文件
        current_task.update_state(
            state=ExportStatus.PROCESSING,
            meta={
                "progress": 90,
                "current_step": "Compressing output files",
                "message": "Creating archive file"
            }
        )
        
        archive_path = _create_archive(output_dir, task_id)
        
        # 6. 清理临时文件
        shutil.rmtree(output_dir)
        
        # 7. 返回成功结果
        return {
            "status": ExportStatus.COMPLETED,
            "message": "Export completed successfully",
            "file_path": str(archive_path),
            "file_size": os.path.getsize(archive_path),
            "total_frames_processed": result.get("frames_count", 0),
            "total_annotations_exported": result.get("annotations_count", 0),
            "completed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        # 更新任务状态为失败
        current_task.update_state(
            state=ExportStatus.FAILED,
            meta={
                "progress": 0,
                "current_step": "Task failed",
                "message": str(exc),
                "error_details": str(exc)
            }
        )
        raise exc

def _perform_nuscenes_conversion(
    task,
    project_metadata,
    export_request: NuScenesExportRequest,
    output_dir: Path
) -> Dict[str, Any]:
    """
    执行实际的 NuScenes 格式转换
    """
    # 这里是你需要实现的核心转换逻辑
    frames_count = 0
    annotations_count = 0
    
    # 创建 NuScenes 目录结构
    nuscenes_dir = output_dir / "nuscenes"
    nuscenes_dir.mkdir(exist_ok=True)
    
    # 创建子目录
    (nuscenes_dir / "samples").mkdir(exist_ok=True)
    (nuscenes_dir / "sweeps").mkdir(exist_ok=True)
    (nuscenes_dir / "maps").mkdir(exist_ok=True)
    
    # 获取帧列表
    frames = project_metadata.frames
    total_frames = len(frames)
    
    # 应用帧选择过滤
    if export_request.frame_selection:
        frames = _filter_frames(frames, export_request.frame_selection)
    
    # 处理每一帧
    for i, frame in enumerate(frames):
        # 更新进度
        progress = 20 + (i / len(frames)) * 60  # 20-80% 的进度
        task.update_state(
            state=ExportStatus.PROCESSING,
            meta={
                "progress": progress,
                "current_step": f"Processing frame {i+1}/{len(frames)}",
                "message": f"Converting frame {frame.timestamp_ns}"
            }
        )
        
        # 转换单帧数据
        frame_result = _convert_single_frame(
            frame, 
            export_request, 
            nuscenes_dir
        )
        
        frames_count += 1
        annotations_count += frame_result.get("annotations_count", 0)
    
    # 生成 NuScenes 元数据文件
    _generate_nuscenes_metadata(nuscenes_dir, project_metadata, export_request)
    
    return {
        "frames_count": frames_count,
        "annotations_count": annotations_count
    }

def _filter_frames(frames: List, frame_selection) -> List:
    """根据帧选择配置过滤帧"""
    if not frame_selection:
        return frames
    
    # 应用帧间隔
    if frame_selection.frame_step > 1:
        frames = frames[::frame_selection.frame_step]
    
    # 应用最大帧数限制
    if frame_selection.max_frames:
        frames = frames[:frame_selection.max_frames]
    
    return frames

def _convert_single_frame(frame, export_request, output_dir) -> Dict[str, Any]:
    """转换单个帧的数据"""
    annotations_count = 0
    
    # 这里实现你的单帧转换逻辑
    # 例如：
    # 1. 转换标注数据格式
    # 2. 处理点云数据
    # 3. 处理图像数据
    # 4. 转换坐标系
    
    if frame.annotation:
        # 过滤标注
        filtered_annotations = _filter_annotations(
            frame.annotation, 
            export_request.annotation_filter
        )
        annotations_count = len(filtered_annotations)
        
        # 转换标注格式
        nuscenes_annotations = _convert_annotations_to_nuscenes(
            filtered_annotations,
            export_request.coordinate_system
        )
        
        # 保存标注文件
        annotation_file = output_dir / "samples" / f"{frame.timestamp_ns}.json"
        with open(annotation_file, 'w') as f:
            json.dump(nuscenes_annotations, f, indent=2)
    
    return {"annotations_count": annotations_count}

def _filter_annotations(annotations: List[AnnotationItem], filter_config) -> List[AnnotationItem]:
    """根据过滤配置过滤标注"""
    if not filter_config:
        return annotations
    
    filtered = annotations
    
    # 按对象类型过滤
    if filter_config.object_types:
        filtered = [ann for ann in filtered if ann.obj_type in filter_config.object_types]
    
    # 按点数过滤
    if filter_config.min_points:
        filtered = [ann for ann in filtered if ann.num_pts and ann.num_pts >= filter_config.min_points]
    
    return filtered

def _convert_annotations_to_nuscenes(annotations: List[AnnotationItem], coordinate_system: str) -> List[Dict]:
    """将标注转换为 NuScenes 格式"""
    nuscenes_annotations = []
    
    for ann in annotations:
        # 这里实现你的具体转换逻辑
        nuscenes_ann = {
            "token": str(uuid.uuid4()),
            "sample_token": str(uuid.uuid4()),
            "instance_token": ann.obj_id,
            "category_name": ann.obj_type,
            "attribute_tokens": [],
            "translation": [ann.psr.position.x, ann.psr.position.y, ann.psr.position.z],
            "size": [ann.psr.scale.x, ann.psr.scale.y, ann.psr.scale.z],
            "rotation": [ann.psr.rotation.x, ann.psr.rotation.y, ann.psr.rotation.z, 1.0],  # 四元数
            "num_lidar_pts": ann.num_pts or 0,
            "num_radar_pts": 0,
        }
        nuscenes_annotations.append(nuscenes_ann)
    
    return nuscenes_annotations

def _generate_nuscenes_metadata(output_dir: Path, project_metadata, export_request):
    """生成 NuScenes 元数据文件"""
    metadata = {
        "version": "v1.0-custom",
        "description": f"Exported from NextPoints project: {project_metadata.project.name}",
        "export_timestamp": datetime.utcnow().isoformat(),
        "source_project": project_metadata.project.name,
        "export_config": export_request.dict(),
        "total_frames": len(project_metadata.frames),
    }
    
    with open(output_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

def _create_archive(source_dir: Path, task_id: str) -> Path:
    """创建压缩包"""
    archive_path = Path(f"/tmp/exports/{task_id}.zip")
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)
    
    return archive_path

@celery_app.task(name="cleanup_export_files")
def cleanup_export_files_task(task_id: str):
    """清理导出文件"""
    try:
        archive_path = Path(f"/tmp/exports/{task_id}.zip")
        if archive_path.exists():
            archive_path.unlink()
        return f"Cleaned up files for task {task_id}"
    except Exception as e:
        return f"Failed to cleanup task {task_id}: {str(e)}"

@celery_app.task(name="cleanup_old_exports")
def cleanup_old_exports_task():
    """清理旧的导出文件（周期性任务）"""
    exports_dir = Path("/tmp/exports")
    if not exports_dir.exists():
        return "No exports directory found"
    
    cleaned_count = 0
    cutoff_time = datetime.utcnow().timestamp() - 86400  # 24小时前
    
    for file_path in exports_dir.glob("*.zip"):
        if file_path.stat().st_mtime < cutoff_time:
            file_path.unlink()
            cleaned_count += 1
    
    return f"Cleaned up {cleaned_count} old export files"
