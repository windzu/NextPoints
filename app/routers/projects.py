from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
import logging

from nextpoints_sdk.models.project_metadata import ProjectMetadataResponse
from nextpoints_sdk.models.annotation import FrameAnnotation
from nextpoints_sdk.models.project import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectStatusUpdateRequest,
)
from nextpoints_sdk.models.enums import ProjectStatusEnum
from nextpoints_sdk.models.project import Project, ProjectCreateResponse

from app.database import get_session


from app.models.export_model import (
    NuScenesExportRequest,
    ExportTaskResponse,
)

from app.services import project_service
from app.services.export_service import export_service

import tools.project_metadata as pm


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ProjectCreateResponse)
async def create_project(
    request: ProjectCreateRequest, session: Session = Depends(get_session)
):
    """
    创建新项目并同步 S3 数据
    """
    try:
        project_response = project_service.create_project(
            request=request, session=session
        )

        if not project_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create project",
            )

        return project_response

    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}",
        )


@router.post("/save_world_list", status_code=status.HTTP_200_OK)
async def save_world_list(
    request: List[FrameAnnotation], session: Session = Depends(get_session)
):
    """
    保存世界帧的标注数据
    """
    try:
        saved_count = project_service.save_world_list(request, session)
        if saved_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No annotations were saved",
            )
        return {"message": f"Successfully saved {saved_count} annotations"}

    except Exception as e:
        logger.error(f"Failed to save world list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save world list: {str(e)}",
        )


@router.get("/list_projects", response_model=List[ProjectResponse])
async def list_projects(
    status_filter: Optional[ProjectStatusEnum] = None,
    session: Session = Depends(get_session),
):
    """
    获取项目列表，支持按状态过滤
    """
    try:
        query = select(Project)
        if status_filter:
            query = query.where(Project.status == status_filter)

        projects = session.exec(query).all()

        result = []
        for project in projects:
            result.append(
                ProjectResponse(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    status=project.status,
                    created_at=project.created_at.isoformat(),
                )
            )

        return result

    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{project_name}", response_model=ProjectResponse)
async def get_project(project_name: str, session: Session = Depends(get_session)):
    """
    获取单个项目详情
    """
    project = session.exec(select(Project).where(Project.name == project_name)).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at.isoformat(),
    )


@router.get("/{project_name}/metadata", response_model=ProjectMetadataResponse)
async def get_project_metadata(
    project_name: str, session: Session = Depends(get_session)
):
    """
    获取项目完整元数据,包括所有帧信息和预签名URL
    """
    try:
        project_metadata = pm.get_project_metadata(project_name, session)
        if not project_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project metadata not found",
            )
        return project_metadata
    except Exception as e:
        logger.error(f"Failed to get project metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project metadata: {str(e)}",
        )


@router.get("/{project_name}/check_label", response_model=List[Dict[str, Any]])
async def get_label_check(project_name: str, session: Session = Depends(get_session)):
    """
    获取项目的标注检查数据
    """
    try:
        annotations = project_service.get_check_label(project_name, session)
        if not annotations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No annotations found for this project",
            )
        return annotations
    except Exception as e:
        logger.error(f"Failed to get label check data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get label check data: {str(e)}",
        )


@router.put("/update_project_status", response_model=ProjectResponse)
async def update_project_status(
    request: ProjectStatusUpdateRequest,
    session: Session = Depends(get_session),
):
    """
    更新项目状态
    """
    project_name = request.project_name
    if not project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project name is required"
        )
    project = session.exec(select(Project).where(Project.name == project_name)).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    project.status = request.status
    session.add(project)
    session.commit()
    session.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at.isoformat(),
    )


@router.delete("/{project_name}")
async def delete_project(project_name: str, session: Session = Depends(get_session)):
    """
    删除项目及其所有相关数据
    """
    project = session.exec(select(Project).where(Project.name == project_name)).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # 删除项目（级联删除会自动删除相关的帧和标注数据）
    session.delete(project)
    session.commit()

    return {"message": f"Project {project_name} deleted successfully"}


# ==================== 导出相关路由 ====================


@router.post("/{project_name}/export/nuscenes", response_model=ExportTaskResponse)
async def start_nuscenes_export(
    project_name: str,
    request: NuScenesExportRequest,
    session: Session = Depends(get_session),
):
    """
    启动 NuScenes 格式导出任务
    """
    try:
        task_response = export_service.start_nuscenes_export(
            project_name=project_name, export_request=request, session=session
        )
        return task_response

    except Exception as e:
        logger.error(f"Failed to start NuScenes export for {project_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start export task: {str(e)}",
        )
