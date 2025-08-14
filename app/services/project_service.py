from sqlmodel import Session
from fastapi import APIRouter, HTTPException, Depends, status
from collections import defaultdict
import posixpath
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from botocore.exceptions import ClientError
from sqlmodel import select
import os
import redis
from celery.result import AsyncResult
from datetime import datetime


from app.services.s3_service import S3Service
from app.models.project_model import (
    Project,
    ProjectResponse,
    ProjectCreateResponse,
    ProjectCreateRequest,
    ProjectStatus,
    DataSourceType,
)
from app.models.annotation_model import AnnotationItem, FrameAnnotation
from app.models.status_model import TaskStatus

from app.database import get_session

from tools.check_label import LabelChecker

from app.tasks.project_tasks import create_project_task
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL)


def get_task_status(task_id: str, project_name: str) -> ProjectCreateResponse:
    """获取任务状态"""
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        return ProjectCreateResponse(
            project_name=project_name,
            status=task_result.state,
            message=task_result.info.get("description", "") if task_result.info else "",
        )
    except Exception as e:
        print(f"Error in get_task_status: {e}")
        return ProjectCreateResponse(
            project_name=project_name,
            status=TaskStatus.FAILED,
            message=f"获取任务状态失败: {str(e)}",
        )


def create_project(
    request: ProjectCreateRequest, session: Session = Depends(get_session)
) -> ProjectCreateResponse:
    """
    创建新项目并从 S3 同步帧和标定数据。
    (Creates a new project and syncs frame and calibration data from S3.)
    """
    project_name = request.project_name

    try:
        # 1. 验证项目是否存在
        project = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()
        if project:
            return ProjectCreateResponse(
                project_name=project_name,
                status=TaskStatus.COMPLETED,
                message=f"Project '{project_name}' already exists",
            )

        # 2. 检查是否有正在进行的导出任务
        redis_key = f"create_project_task:{project_name}"
        if redis_client.get(redis_key):
            task_id = redis_client.get(redis_key).decode("utf-8")
            return get_task_status(task_id, project_name)
        else:
            # debug
            print(
                f"Starting create project for project: {project_name}, request: {request}"
            )

            celery_task = create_project_task.delay(request.model_dump())
            success = redis_client.set(
                redis_key,
                celery_task.id,
                ex=30,
                nx=True,
            )
            if not success:
                return ProjectCreateResponse(
                    project_name=project_name,
                    status=TaskStatus.FAILED,
                    message=f"Export task for project '{project_name}' already exists",
                )

            # debug
            print(f"Celery task started with ID: {celery_task.id}")

            return ProjectCreateResponse(
                project_name=project_name,
                status=TaskStatus.PENDING,
                message=f"Create task created for project '{project_name}'",
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during project creation: {e}",
        )


def get_check_label(
    project_name: str, session: Session = Depends(get_session)
) -> List[Dict[str, Any]]:
    """
    获取项目的标注检查数据
    """
    try:
        # 1. 获取项目基本信息和状态
        project = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()

        # 2. build FrameAnnotation list from label files
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        s3_service = S3Service(
            access_key_id=project.access_key_id,
            secret_access_key=project.secret_access_key,
            endpoint_url=project.s3_endpoint,
            region_name=project.region_name,
        )
        label_key_prefix = str(Path(project.bucket_prefix or "") / "label")
        label_files = s3_service.list_objects(project.bucket_name, label_key_prefix)
        if not label_files:
            raise HTTPException(
                status_code=404, detail="No label files found for this project"
            )
        annotations = []
        for label_file in label_files:
            key = label_file
            relative_key = (
                key[len(label_key_prefix) :].lstrip("/") if label_key_prefix else key
            )
            frame_id = Path(relative_key).stem  # 获取帧ID

            try:
                annotation_data = s3_service.read_json_object(project.bucket_name, key)
                if not isinstance(annotation_data, list):
                    annotation_data = []  # 确保是列表格式
                annotations.append(
                    FrameAnnotation(
                        scene=project.name,
                        frame=frame_id,
                        annotation=[AnnotationItem(**item) for item in annotation_data],
                    )
                )
            except Exception as e:
                logger.error(f"Failed to read or parse label file {key}: {e}")
                continue

        # 3. use LabelChecker to validate annotations
        label_checker = LabelChecker(annotations)
        label_checker.check()
        return label_checker.messages

    except Exception as e:
        logger.error(f"Failed to get label check data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get label check data: {str(e)}",
        )


def save_world_list(
    request: List[FrameAnnotation], session: Session = Depends(get_session)
):
    """
    保存单个项目的多个世界帧的标注数据到S3存储
    """

    try:
        if not request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request data cannot be empty",
            )

        # 确保所有条目的 scene 一致
        scenes = set(item.scene for item in request)
        if len(scenes) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"All frames must belong to the same project. Found: {list(scenes)}",
            )

        project_name = request[0].scene

        # 获取项目信息
        project = session.exec(
            select(Project).where(Project.name == project_name)
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_name} not found",
            )

        # 初始化 S3 服务
        s3_service = S3Service(
            access_key_id=project.access_key_id,
            secret_access_key=project.secret_access_key,
            endpoint_url=project.s3_endpoint,
            region_name=project.region_name,
        )

        saved_count = 0

        # 保存每帧
        for item in request:
            try:
                prefix = project.bucket_prefix or ""
                if prefix and not prefix.endswith("/"):
                    prefix += "/"

                label_key = f"{prefix}label/{item.frame}.json"

                s3_service.upload_json_object(
                    bucket_name=project.bucket_name,
                    key=label_key,
                    data_dict=item.to_dict()["annotation"],
                )

                saved_count += 1

            except Exception as e:
                logger.error(
                    f"Failed to save annotation for {project_name}/{item.frame}: {e}"
                )
                logger.error(f"Annotation data: {item.annotation}")
                continue

        return {
            "message": f"Successfully saved {saved_count} annotations",
            "saved_count": saved_count,
            "total_requested": len(request),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save world list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save annotations: {str(e)}",
        )
