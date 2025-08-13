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
import logging
import redis
from celery import current_task
from celery.exceptions import Retry
from sqlmodel import SQLModel, create_engine, Session,select
from fastapi import APIRouter, Depends, HTTPException, Query

# 注意：这里需要导入你实际的 celery_app
from app.celery_app import celery_app
from app.models.export_model import ExportStatus, NuScenesExportRequest
from app.models.annotation_model import AnnotationItem
from app.database import get_session
from app.services.project_service import get_project_metadata
from app.services.s3_service import S3Service
from app.models.export_model import NuScenesExportRequest
from app.models.meta_data_model import ProjectMetadataResponse
from app.models.project_model import Project

from tools.export_tools.export_to_nuscenes import NextPointsToNuScenesConverter

redis_client = redis.Redis.from_url(celery_app.conf.broker_url)

@celery_app.task(bind=True)
def export_to_nuscenes_task(
    self,
    project_name: str,
    export_request: dict
) -> Dict[str, Any]:
    """
    导出项目到 NuScenes 格式的异步任务
    
    Args:
        project_name: 项目名称
        export_request: 导出请求配置
    
    Returns:
        任务结果字典
    """
    request = NuScenesExportRequest.model_validate(export_request)



    try:
        with next(get_session()) as session:
            # 更新任务状态为处理中
            self.update_state(
                state=ExportStatus.PROCESSING,
                meta={
                    "progress": 0,
                    "current_step": "Initializing export task",
                    "message": "Starting NuScenes export process"
                }
            )
            # 1. 验证项目是否存在
            project: Optional[Project] = session.exec(
                select(Project).where(Project.name == project_name)
            ).first()
            if not project:
                raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")


            
            # 2. 获取项目元数据
            self.update_state(
                state=ExportStatus.PROCESSING,
                meta={"message": f"Loading metadata for project: {project_name}"}
            )
            project_metadata = get_project_metadata(project_name, session)
            if not project_metadata:
                raise ValueError(f"Project {project_name} not found")
            
            
            # 3. 创建输出目录
            output_dir = Path(f"/tmp/exports/{project_name}")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 4. 执行转换
            self.update_state(
                state=ExportStatus.PROCESSING,
                meta={
                    "message": "converting to NuScenes format",
                }
            )
            result = _perform_nuscenes_conversion(
                project_metadata=project_metadata,
                export_request=request,
                output_dir=output_dir
            )
            print(f"output_dir: {output_dir}")

        
            # 5. upload to S3
            self.update_state(
                state=ExportStatus.PROCESSING,
                meta={"message": "Uploading to S3"}
            )
            s3_service = S3Service(
                access_key_id=project.access_key_id,
                secret_access_key=project.secret_access_key,
                endpoint_url=project.s3_endpoint,
                region_name=project.region_name
            )
            s3_service.upload_folder(
                local_folder_path=str(output_dir),
                bucket_name=project.bucket_name,
                object_prefix=f"{project.name}/nuscenes/",
                include_folder_name=False
            )

            
            # 6. 清理临时文件
            # shutil.rmtree(output_dir)
        
            # 7. 返回成功结果
            return {
                "status": ExportStatus.COMPLETED,
                "message": "Export completed successfully",
                "completed_at": datetime.utcnow().isoformat()
            }
        
    except Exception as exc:
        # 更新任务状态为失败
        self.update_state(
            state=ExportStatus.FAILED,
            meta={
                "progress": 0,
                "current_step": "Task failed",
                "message": str(exc),
                "error_details": str(exc)
            }
        )
        raise exc
    finally:
        redis_key = f"export_to_nuscenes_task:{project_name}"
        if redis_client.exists(redis_key):
            try:
                redis_client.delete(redis_key)
            except Exception:
                # 如果无法获取任务状态，保守地设置过期时间
                redis_client.expire(redis_key, 10)

def _perform_nuscenes_conversion(
    project_metadata: ProjectMetadataResponse,
    export_request: NuScenesExportRequest,
    output_dir: Path
) -> Dict[str, Any]:
    """
    执行实际的 NuScenes 格式转换
    """
    # Import the new converter
    
    
    try:
        # Create converter instance
        converter = NextPointsToNuScenesConverter(project_metadata, export_request)
        
        # Perform conversion
        conversion_stats = converter.convert(output_dir)
        
        return {
            "frames_count": conversion_stats.get("frames_processed", 0),
            "annotations_count": conversion_stats.get("annotations_converted", 0),
            "instances_count": conversion_stats.get("instances_created", 0),
            "errors": conversion_stats.get("errors", [])
        }
        
    except Exception as e:
        return {
            "frames_count": 0,
            "annotations_count": 0,
            "instances_count": 0,
            "errors": [f"Conversion failed: {str(e)}"]
        }


def _create_archive(source_dir: Path, project_name: str) -> Path:
    """创建压缩包"""
    archive_path = Path(f"/tmp/exports/{project_name}.zip")
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)
    
    return archive_path

@celery_app.task(name="cleanup_export_files")
def cleanup_export_files_task(project_name: str):
    """清理导出文件"""
    try:
        archive_path = Path(f"/tmp/exports/{project_name}.zip")
        if archive_path.exists():
            archive_path.unlink()
        return f"Cleaned up files for project {project_name}"
    except Exception as e:
        return f"Failed to cleanup project {project_name}: {str(e)}"

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

