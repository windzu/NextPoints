# app/tasks/project_tasks.py
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import redis
from sqlmodel import select
from fastapi import HTTPException, status

# 注意：这里需要导入你实际的 celery_app
from app.celery_app import celery_app
from app.database import get_session

from app.services.s3_service import S3Service
from app.models.project_model import (
    Project,
    ProjectCreateRequest,
    ProjectStatus,
    DataSourceType,
)
from app.models.status_model import TaskStatus

from tools.export_tools.export_to_nuscenes import NextPointsToNuScenesConverter
from tools.import_tools.custom2nextpoints import custom2nextpoints
from tools.import_tools.sus2nextpoints import sus2nextpoints
from tools.project_metadata import get_project_metadata

redis_client = redis.Redis.from_url(celery_app.conf.broker_url)


@celery_app.task(bind=True)
def create_project_task(self, create_request: dict) -> Dict[str, Any]:
    """
    导出项目到 NuScenes 格式的异步任务

    Args:
        project_name: 项目名称
        export_request: 导出请求配置

    Returns:
        任务结果字典
    """
    request = ProjectCreateRequest.model_validate(create_request)
    project_name = request.project_name

    # 1. 初始化并测试 S3 连接
    # (Initialize and test S3 connection)
    s3_service = S3Service(
        access_key_id=request.access_key_id,
        secret_access_key=request.secret_access_key,
        endpoint_url=request.s3_endpoint,
        region_name=request.region_name,
    )

    success, message = s3_service.test_connection(request.bucket_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 connection failed: {message}",
        )

    with next(get_session()) as session:
        try:
            existing = session.exec(
                select(Project).where(Project.name == request.project_name)
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Project with name '{request.project_name}' already exists.",
                )

            # judge if data_source_type is custom or nextpoints
            # 判断数据源类型是 custom 还是 nextpoints
            bucket_prefix = os.path.join(request.project_name, "nextpoints")
            if request.data_source_type == DataSourceType.CUSTOM:
                print("Using custom2nextpoints to generate nextpoints...")
                self.update_state(
                    state=TaskStatus.PROCESSING,
                    meta={
                        "message": "Using custom2nextpoints to generate nextpoints..."
                    },
                )
                custom2nextpoints(
                    scene_name=request.project_name,
                    bucket=request.bucket_name,
                    s3_service=s3_service,
                    main_channel=request.main_channel,
                    time_interval_s=request.time_interval,
                )
            elif request.data_source_type == DataSourceType.SUS:
                print("Using sus2nextpoints to generate nextpoints...")
                self.update_state(
                    state=TaskStatus.PROCESSING,
                    meta={"message": "Using sus2nextpoints to generate nextpoints..."},
                )
                sus2nextpoints(
                    scene_name=request.project_name,
                    bucket=request.bucket_name,
                    s3_service=s3_service,
                )
            elif request.data_source_type == DataSourceType.NEXTPOINTS:
                self.update_state(
                    state=TaskStatus.PROCESSING,
                    meta={"message": "Direct using nextpoints..."},
                )
                print("Direct using nextpoints...")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported data source type: {request.data_source_type}",
                )
            # 2. 创建项目记录
            self.update_state(
                state=TaskStatus.PROCESSING,
                meta={"message": "Creating project record in database..."},
            )
            project = Project(
                name=request.project_name,
                description=request.description,
                storage_type=request.storage_type,
                bucket_name=request.bucket_name,
                bucket_prefix=bucket_prefix,
                region_name=request.region_name,
                s3_endpoint=request.s3_endpoint,
                access_key_id=request.access_key_id,
                secret_access_key=request.secret_access_key,
                use_presigned_urls=request.use_presigned_urls,
                expiration_minutes=request.expiration_minutes,
                status=ProjectStatus.unstarted,  # 初始状态为未开始
            )

            session.add(project)
            session.flush()  # 确保项目 ID 已生成

            # 3. use get_project_metadata to check project metadata
            self.update_state(
                state=TaskStatus.PROCESSING,
                meta={"message": "Fetching project metadata..."},
            )
            get_project_metadata(project.name, session)
            session.commit()
            session.refresh(project)

            # 4. return project response
            return {
                "status": TaskStatus.COMPLETED,
                "message": "Create project completed successfully",
            }
        except Exception as exc:
            session.rollback()
            self.update_state(state=TaskStatus.FAILED, meta={"message": str(exc)})
            raise exc
        finally:
            redis_key = f"create_project_task:{project_name}"
            if redis_client.exists(redis_key):
                try:
                    redis_client.delete(redis_key)
                except Exception:
                    # 如果无法获取任务状态，保守地设置过期时间
                    redis_client.expire(redis_key, 10)
