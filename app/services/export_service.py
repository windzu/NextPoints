"""
导出服务 - 处理异步导出任务的管理
"""
import uuid
import os
import redis
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from fastapi import HTTPException, status
from celery.result import AsyncResult

from app.models.export_model import (
    NuScenesExportRequest, ExportTaskResponse, ExportTaskStatus, 
    ExportStatus, ExportTaskList
)
from app.models.project_model import Project
from app.tasks.export_tasks import export_to_nuscenes_task
from app.celery_app import celery_app

class ExportService:
    """导出服务类"""
    
    def __init__(self):
        # 可以在这里初始化其他依赖，如数据库连接池等
        REDIS_URL=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
        self.redis_client = redis.Redis.from_url(REDIS_URL)
        self.celery_app = celery_app

    def get_task_status(self, task_id: str) -> ExportTaskResponse:
        """获取任务状态"""
        try:
            task_result = AsyncResult(task_id, app=self.celery_app)
            return ExportTaskResponse(
                task_id=task_id,
                status=task_result.state,
                message=str(task_result.info) if task_result.info else "",
                created_at=datetime.utcnow(),
            )
        except Exception as e:
            print(f"Error in get_task_status: {e}")
            return ExportTaskResponse(
                task_id=task_id,
                status=ExportStatus.FAILED,
                message=f"获取任务状态失败: {str(e)}",
                created_at=datetime.utcnow(),
            )

    
    def start_nuscenes_export(
        self,
        project_name: str,
        export_request: NuScenesExportRequest,
        session: Session
    ) -> ExportTaskResponse:
        """
        启动 NuScenes 导出任务
        
        Args:
            project_name: 项目名称
            export_request: 导出请求配置
            session: 数据库会话
            
        Returns:
            导出任务响应
        """
        # 1. 验证项目是否存在
        project = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()
        
        if not project:
            return ExportTaskResponse(
                task_id="none",
                status=ExportStatus.FAILED,
                message=f"Project '{project_name}' does not exist",
                created_at=datetime.now(),
            )
        
        # 3. 启动异步任务
        try:
            # check task if already running for the same project 
            redis_key = f"export_to_nuscenes_task:{project_name}"
            if self.redis_client.get(redis_key):
                task_id = self.redis_client.get(redis_key).decode('utf-8')
                return self.get_task_status(task_id)
            else:
                # debug
                print(f"Starting export task for project: {project_name}, request: {export_request}")

                celery_task = export_to_nuscenes_task.delay(
                    project_name=project_name,
                    export_request=export_request.model_dump(),
                )
                success = self.redis_client.set(
                    redis_key,
                    celery_task.id,
                    ex=30,
                    nx=True,
                )
                if not success:
                    return ExportTaskResponse(
                        task_id=celery_task.id,
                        status=ExportStatus.FAILED,
                        message=f"Export task for project '{project_name}' already exists",
                        created_at=datetime.now(),
                    )

                # debug
                print(f"Celery task started with ID: {celery_task.id}")

                return ExportTaskResponse(
                    task_id=celery_task.id,  # 使用 Celery 任务ID
                    status=ExportStatus.PENDING,
                    message=f"Export task created for project '{project_name}'",
                    created_at=datetime.now(),
                )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start export task: {str(e)}"
            )
    
    def get_export_status(self, task_id: str) -> ExportTaskStatus:
        """
        获取导出任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        try:
            # 获取 Celery 任务结果
            async_result = AsyncResult(task_id)
            
            # 构建基础状态信息
            task_status = ExportTaskStatus(
                task_id=task_id,
                status=self._convert_celery_state(async_result.state),
                progress=0.0,
                message="Task status unknown",
                created_at=datetime.utcnow()
            )
            
            # 根据任务状态更新详细信息
            if async_result.state == "PENDING":
                task_status.message = "Task is waiting to be processed"
                task_status.progress = 0.0
                
            elif async_result.state == "PROGRESS":
                # 从任务元数据中获取进度信息
                meta = async_result.info or {}
                task_status.progress = meta.get("progress", 0.0)
                task_status.current_step = meta.get("current_step")
                task_status.message = meta.get("message", "Task is processing")
                task_status.started_at = datetime.utcnow()  # 简化处理
                
            elif async_result.state == "SUCCESS":
                result = async_result.result or {}
                task_status.status = ExportStatus.COMPLETED
                task_status.progress = 100.0
                task_status.message = result.get("message", "Export completed")
                task_status.completed_at = datetime.utcnow()
                task_status.file_size = result.get("file_size")
                task_status.total_frames_processed = result.get("total_frames_processed")
                task_status.total_annotations_exported = result.get("total_annotations_exported")
                task_status.download_url = f"/api/projects/export/download/{task_id}"
                
            elif async_result.state == "FAILURE":
                meta = async_result.info or {}
                task_status.status = ExportStatus.FAILED
                task_status.message = "Export task failed"
                task_status.error_details = str(meta) if meta else "Unknown error"
                task_status.completed_at = datetime.utcnow()
                
            return task_status
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get task status: {str(e)}"
            )
    
    def cancel_export_task(self, task_id: str) -> Dict[str, str]:
        """
        取消导出任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            取消结果
        """
        try:
            async_result = AsyncResult(task_id)
            
            if async_result.state in ["PENDING", "PROGRESS"]:
                async_result.revoke(terminate=True)
                return {"message": f"Task {task_id} has been cancelled"}
            else:
                return {"message": f"Task {task_id} cannot be cancelled (status: {async_result.state})"}
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel task: {str(e)}"
            )
    
    def list_export_tasks(
        self,
        project_name: Optional[str] = None,
        status_filter: Optional[ExportStatus] = None,
        page: int = 1,
        page_size: int = 10
    ) -> ExportTaskList:
        """
        列出导出任务
        
        注意：这个方法需要配合数据库存储任务信息才能完整实现
        目前返回示例数据
        """
        # 这里应该从数据库查询任务列表
        # 现在返回空列表作为示例
        return ExportTaskList(
            tasks=[],
            total_count=0,
            page=page,
            page_size=page_size
        )
    
    def cleanup_task_files(self, task_id: str) -> Dict[str, str]:
        """
        清理任务生成的文件
        
        Args:
            task_id: 任务ID
            
        Returns:
            清理结果
        """
        try:
            cleanup_task = self.celery_app.cleanup_export_files_task.delay(task_id)
            return {"message": f"Cleanup task started for {task_id}"}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start cleanup: {str(e)}"
            )
    
    def get_download_info(self, task_id: str) -> Dict[str, Any]:
        """
        获取下载信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            下载信息
        """
        async_result = AsyncResult(task_id)
        
        if async_result.state != "SUCCESS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task is not completed yet"
            )
        
        result = async_result.result or {}
        file_path = result.get("file_path")
        
        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export file not found"
            )
        
        return {
            "file_path": file_path,
            "file_size": result.get("file_size"),
            "filename": f"nuscenes_export_{task_id}.zip"
        }
    
    def _convert_celery_state(self, celery_state: str) -> ExportStatus:
        """
        将 Celery 状态转换为自定义状态
        
        Args:
            celery_state: Celery 任务状态
            
        Returns:
            自定义导出状态
        """
        state_mapping = {
            "PENDING": ExportStatus.PENDING,
            "STARTED": ExportStatus.PROCESSING,
            "PROGRESS": ExportStatus.PROCESSING,
            "SUCCESS": ExportStatus.COMPLETED,
            "FAILURE": ExportStatus.FAILED,
            "REVOKED": ExportStatus.CANCELLED,
        }
        
        return state_mapping.get(celery_state, ExportStatus.PENDING)



# 创建服务实例
export_service = ExportService()
