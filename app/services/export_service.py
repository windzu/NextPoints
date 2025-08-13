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
                status=self._convert_celery_state(task_result.state),
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
